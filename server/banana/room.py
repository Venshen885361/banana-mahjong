"""房間管理：連線、座位、bot 補位、逾時自動 pass、斷線重連。"""

from __future__ import annotations

import asyncio
import secrets
import time
from dataclasses import dataclass
from typing import Any

from fastapi import WebSocket

from .bot import Bot
from .game import Game, Phase
from .score import MODE_HANCHAN, ScoreConfig
from .yaku import TSUMO_MODE_MENZEN

ACT_TIMEOUT = 30.0      # 打牌思考時間（秒）
CLAIM_TIMEOUT = 10.0    # 鳴牌 / 榮和回應時間
BOT_DELAY = 0.45        # bot 假思考，讓畫面看得出節奏
NEXT_HAND_DELAY = 10.0  # 結算畫面停留時間


@dataclass
class Seat:
    index: int
    name: str
    token: str
    is_bot: bool = False
    ws: WebSocket | None = None
    connected: bool = False


@dataclass
class RoomConfig:
    mode: str = MODE_HANCHAN
    single_table: str = "a"
    max_players: int = 4
    min_han: int = 1
    tsumo_mode: str = TSUMO_MODE_MENZEN
    dora_wrap: bool = True
    start_points: int = 35000

    def to_score(self) -> ScoreConfig:
        return ScoreConfig(
            mode=self.mode,
            single_table=self.single_table,
            min_han=self.min_han,
            tsumo_mode=self.tsumo_mode,
            dora_wrap=self.dora_wrap,
            start_points=self.start_points,
        )


class Room:
    def __init__(self, room_id: str, name: str, cfg: RoomConfig | None = None) -> None:
        self.id = room_id
        self.name = name
        self.cfg = cfg or RoomConfig()
        self.seats: list[Seat] = []
        self.host_token: str | None = None
        self.game: Game | None = None
        self.bots: dict[int, Bot] = {}
        self.chat: list[dict[str, Any]] = []
        self.deadline: float | None = None
        self._lock = asyncio.Lock()
        self._task: asyncio.Task | None = None
        self._event_cursor = 0
        self.created = time.time()

    # ------------------------------------------------------------------
    @property
    def started(self) -> bool:
        return self.game is not None

    def summary(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "players": len([s for s in self.seats if not s.is_bot]),
            "seats": len(self.seats),
            "maxPlayers": self.cfg.max_players,
            "started": self.started,
            "mode": self.cfg.mode,
        }

    def room_state(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "config": {
                "mode": self.cfg.mode,
                "singleTable": self.cfg.single_table,
                "maxPlayers": self.cfg.max_players,
                "minHan": self.cfg.min_han,
                "tsumoMode": self.cfg.tsumo_mode,
                "doraWrap": self.cfg.dora_wrap,
                "startPoints": self.cfg.start_points,
            },
            "started": self.started,
            "hostSeat": next(
                (s.index for s in self.seats if s.token == self.host_token), None
            ),
            "seats": [
                {
                    "index": s.index,
                    "name": s.name,
                    "isBot": s.is_bot,
                    "connected": s.connected,
                }
                for s in self.seats
            ],
            "chat": self.chat[-50:],
        }

    # ------------------------------------------------------------------
    def join(self, name: str, token: str | None) -> Seat | None:
        if token:
            for s in self.seats:
                if s.token == token:
                    s.name = name or s.name
                    return s
        if self.started:
            return None
        if len(self.seats) >= self.cfg.max_players:
            return None
        seat = Seat(index=len(self.seats), name=name, token=secrets.token_urlsafe(16))
        self.seats.append(seat)
        if self.host_token is None:
            self.host_token = seat.token
        return seat

    def add_bot(self) -> bool:
        if self.started or len(self.seats) >= self.cfg.max_players:
            return False
        idx = len(self.seats)
        self.seats.append(
            Seat(index=idx, name=f"Bot {idx + 1}", token=secrets.token_urlsafe(8), is_bot=True)
        )
        return True

    def remove_seat(self, index: int) -> bool:
        if self.started:
            return False
        self.seats = [s for s in self.seats if s.index != index]
        for i, s in enumerate(self.seats):
            s.index = i
        return True

    def is_host(self, token: str) -> bool:
        return token == self.host_token

    # ------------------------------------------------------------------
    def start(self) -> str | None:
        if self.started:
            return "已經開始了"
        if len(self.seats) < 2:
            return "至少需要 2 位玩家（可加 bot）"
        self.game = Game(
            [s.name for s in self.seats],
            cfg=self.cfg.to_score(),
            bots=[s.index for s in self.seats if s.is_bot],
        )
        self.bots = {s.index: Bot(s.index) for s in self.seats if s.is_bot}
        self.game.start_hand()
        self._event_cursor = 0
        return None

    # ------------------------------------------------------------------
    async def broadcast(self) -> None:
        if self.game is None:
            payload = {"t": "room", "room": self.room_state()}
            await self._send_all(payload)
            return
        events = self.game.events[self._event_cursor :]
        self._event_cursor = len(self.game.events)
        for s in self.seats:
            if s.ws is None or not s.connected:
                continue
            msg = {
                "t": "state",
                "room": self.room_state(),
                "state": self.game.state_for(s.index),
                "events": events,
                "deadline": self.deadline,
            }
            await self._safe_send(s, msg)

    async def _send_all(self, payload: dict[str, Any]) -> None:
        for s in self.seats:
            if s.ws is not None and s.connected:
                await self._safe_send(s, payload)

    async def _safe_send(self, seat: Seat, payload: dict[str, Any]) -> None:
        try:
            await seat.ws.send_json(payload)  # type: ignore[union-attr]
        except Exception:
            seat.connected = False

    # ------------------------------------------------------------------
    async def submit(self, seat_index: int, action: dict[str, Any]) -> None:
        async with self._lock:
            if self.game is None:
                return
            self.game.submit(seat_index, action)
            await self._advance()

    async def _advance(self) -> None:
        """推進到下一個需要人類輸入的點。"""
        g = self.game
        assert g is not None
        guard = 0
        while guard < 500:
            guard += 1
            if g.phase is Phase.HAND_END:
                self.deadline = time.time() + NEXT_HAND_DELAY
                await self.broadcast()
                self._schedule(self._auto_next_hand, NEXT_HAND_DELAY)
                return
            if g.phase is Phase.GAME_END:
                self.deadline = None
                await self.broadcast()
                return
            waiting = g.waiting_on()
            bot_seats = [s for s in waiting if s in self.bots]
            human_seats = [s for s in waiting if s not in self.bots]
            if bot_seats and not human_seats:
                await self.broadcast()
                await asyncio.sleep(BOT_DELAY)
            for s in bot_seats:
                opts = g.legal_actions(s)
                if opts:
                    g.submit(s, self.bots[s].choose(g, opts))
            if bot_seats:
                continue
            break
        timeout = CLAIM_TIMEOUT if g.phase is Phase.CLAIM else ACT_TIMEOUT
        self.deadline = time.time() + timeout
        await self.broadcast()
        self._schedule(self._on_timeout, timeout)

    def _schedule(self, fn, delay: float) -> None:
        if self._task and not self._task.done():
            self._task.cancel()
        self._task = asyncio.create_task(self._delayed(fn, delay))

    async def _delayed(self, fn, delay: float) -> None:
        try:
            await asyncio.sleep(delay)
        except asyncio.CancelledError:
            return
        await fn()

    async def _on_timeout(self) -> None:
        async with self._lock:
            g = self.game
            if g is None:
                return
            if g.phase is Phase.CLAIM:
                g.force_pass_remaining()
            elif g.phase is Phase.ACT:
                # 逾時自動切牌
                opts = g.legal_actions(g.turn)
                disc = next((o for o in opts if o["type"] == "discard"), None)
                if disc and disc["tiles"]:
                    p = g.players[g.turn]
                    tile = p.drawn if p.drawn in disc["tiles"] else disc["tiles"][0]
                    g.submit(g.turn, {"type": "discard", "tile": tile})
            await self._advance()

    async def _auto_next_hand(self) -> None:
        async with self._lock:
            g = self.game
            if g is None or g.phase is not Phase.HAND_END:
                return
            g.next_hand()
            await self._advance()

    async def kick_off(self) -> None:
        async with self._lock:
            await self._advance()
