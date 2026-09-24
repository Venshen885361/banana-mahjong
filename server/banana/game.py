"""對局狀態機。

一個 Game 物件 = 一整場（東風戰 / 半莊 / 一局戰），內含多個「局」(hand)。
所有進行都由外部呼叫 submit() 推動，方便接 WebSocket 或 bot。
"""

from __future__ import annotations

import random
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from .hand import is_tenpai, waits
from .meld import Meld, MeldType
from .score import (
    MODE_HANCHAN,
    MODE_SINGLE,
    MODE_TONPUU,
    ScoreConfig,
    noten_payments,
    payments,
    total_points,
)
from .tiles import N_KINDS, TILE_COUNTS, full_wall, to_char
from .yaku import WinContext, YakuResult, evaluate

DEAD_WALL = 14   # 4 嶺上 + 5 寶牌指示 + 5 裡寶指示
MAX_KAN = 4


class Phase(str, Enum):
    WAITING = "waiting"
    ACT = "act"        # 當前玩家要行動（打牌 / 自摸 / 立直 / 槓）
    CLAIM = "claim"    # 其他玩家可鳴牌或榮和
    HAND_END = "hand_end"
    GAME_END = "game_end"


@dataclass(slots=True)
class Discard:
    tile: int
    tsumogiri: bool = False
    riichi: bool = False
    claimed: bool = False


@dataclass(slots=True)
class PlayerState:
    seat: int
    name: str = ""
    is_bot: bool = False
    points: int = 35000

    hand: list[int] = field(default_factory=lambda: [0] * N_KINDS)
    melds: list[Meld] = field(default_factory=list)
    river: list[Discard] = field(default_factory=list)
    drawn: int | None = None

    riichi: bool = False
    double_riichi: bool = False
    ippatsu: bool = False
    riichi_furiten: bool = False
    temp_furiten: bool = False
    declared_ready: bool = False   # 已完成配牌第一巡

    @property
    def menzen(self) -> bool:
        return all(not m.is_open for m in self.melds)

    @property
    def hand_tiles(self) -> list[int]:
        out: list[int] = []
        for i, c in enumerate(self.hand):
            out.extend([i] * c)
        return out

    def waits(self) -> list[int]:
        return waits(self.hand, self.melds)

    def is_furiten(self) -> bool:
        w = set(self.waits())
        if not w:
            return False
        if any(d.tile in w for d in self.river):
            return True
        return self.temp_furiten or self.riichi_furiten


@dataclass(slots=True)
class PendingClaim:
    seat: int
    options: list[dict[str, Any]]
    answer: dict[str, Any] | None = None


class Game:
    def __init__(
        self,
        names: Sequence[str],
        cfg: ScoreConfig | None = None,
        seed: int | None = None,
        bots: Iterable[int] = (),
    ) -> None:
        self.cfg = cfg or ScoreConfig()
        self.rng = random.Random(seed)
        self.n = len(names)
        if not 2 <= self.n <= 6:
            raise ValueError("人數需在 2~6 之間")
        bots_set = set(bots)
        self.players = [
            PlayerState(seat=i, name=nm, is_bot=i in bots_set, points=self.cfg.start_points)
            for i, nm in enumerate(names)
        ]
        self.dealer = 0
        self.hand_no = 0
        self.honba = 0
        self.riichi_sticks = 0
        self.phase = Phase.WAITING
        self.events: list[dict[str, Any]] = []
        self.result: dict[str, Any] | None = None

        # 一局內的狀態
        self.wall: list[int] = []
        self.rinshan: list[int] = []
        self.dora_ind: list[int] = []
        self.ura_ind: list[int] = []
        self.opened_dora = 1
        self.turn = 0
        self.kan_count = 0
        self.last_discard: tuple[int, int] | None = None
        self.claims: dict[int, PendingClaim] = {}
        self.after_kan_draw = False      # 剛從嶺上摸牌（嶺上開花判定）
        self.after_kan_discard = False   # 上一張打牌是槓後打出（槓振判定）
        self.riichi_declared_this_hand = False
        self.pending_kakan: tuple[int, int] | None = None  # (seat, tile) 等待搶槓
        self.first_turn = True           # 尚未有人鳴牌且第一巡未結束
        self.turn_index = 0
        self._tsubame_tile = False       # 上一張打牌是否為立直宣言牌
        self._next_dealer_keeps = False
        self._next_is_draw = False
        self.total_hands = self._total_hands()

    # ------------------------------------------------------------------
    def _total_hands(self) -> int:
        if self.cfg.mode == MODE_SINGLE:
            return 1
        if self.cfg.mode == MODE_TONPUU:
            return self.n
        return self.n * 2  # 半莊

    def log(self, **kw) -> None:
        self.events.append(kw)

    # ------------------------------------------------------------------
    def start_hand(self) -> None:
        self.events.clear()
        self.result = None
        wall = full_wall()
        self.rng.shuffle(wall)
        dead = wall[-DEAD_WALL:]
        self.wall = wall[:-DEAD_WALL]
        self.rinshan = dead[0:4]
        self.dora_ind = dead[4:9]
        self.ura_ind = dead[9:14]
        self.opened_dora = 1
        self.kan_count = 0
        self.last_discard = None
        self.claims = {}
        self.after_kan_draw = False
        self.after_kan_discard = False
        self.riichi_declared_this_hand = False
        self.pending_kakan = None
        self.first_turn = True
        self.turn_index = 0

        for p in self.players:
            p.hand = [0] * N_KINDS
            p.melds = []
            p.river = []
            p.drawn = None
            p.riichi = p.double_riichi = p.ippatsu = False
            p.riichi_furiten = p.temp_furiten = False
            for _ in range(13):
                p.hand[self.wall.pop(0)] += 1

        self.log(t="hand_start", dealer=self.dealer, hand_no=self.hand_no, honba=self.honba)
        self.log(t="dora", tile=self.dora_ind[0])
        self.turn = self.dealer
        self.phase = Phase.ACT
        self._draw(self.dealer, initial=True)

    # ------------------------------------------------------------------
    def _draw(self, seat: int, from_rinshan: bool = False, initial: bool = False) -> None:
        p = self.players[seat]
        if from_rinshan:
            if not self.rinshan:
                self._exhaustive_draw()
                return
            tile = self.rinshan.pop(0)
            self.after_kan_draw = True
        else:
            if not self.wall:
                self._exhaustive_draw()
                return
            tile = self.wall.pop(0)
            self.after_kan_draw = False
        p.hand[tile] += 1
        p.drawn = tile
        self.turn = seat
        self.phase = Phase.ACT
        self.log(t="draw", seat=seat, tile=tile, rinshan=from_rinshan, initial=initial)

    @property
    def haitei(self) -> bool:
        return not self.wall

    # ------------------------------------------------------------------
    # 合法動作
    # ------------------------------------------------------------------
    def legal_actions(self, seat: int) -> list[dict[str, Any]]:
        if self.phase is Phase.ACT and seat == self.turn:
            return self._act_options(seat)
        if self.phase is Phase.CLAIM and seat in self.claims:
            c = self.claims[seat]
            if c.answer is None:
                return c.options
        return []

    def _act_options(self, seat: int) -> list[dict[str, Any]]:
        p = self.players[seat]
        out: list[dict[str, Any]] = []

        # 自摸
        if p.drawn is not None:
            ctx = self._make_ctx(seat, p.drawn, is_tsumo=True)
            r = evaluate(ctx)
            if r and r.has_yaku and (r.multiplier or r.han >= self.cfg.min_han):
                out.append({"type": "tsumo"})

        # 暗槓 / 加槓
        if self.kan_count < MAX_KAN and self.wall:
            for t in range(N_KINDS):
                if p.hand[t] == 4:
                    if p.riichi and not self._ankan_keeps_wait(p, t):
                        continue
                    out.append({"type": "ankan", "tile": t})
            for m in p.melds:
                if m.type is MeldType.PON and p.hand[m.base] >= 1 and not p.riichi:
                    out.append({"type": "kakan", "tile": m.base})

        # 立直
        if (
            not p.riichi
            and p.menzen
            and p.points >= self.cfg.riichi_stick
            and len(self.wall) >= self.n
        ):
            tiles = self._riichi_discards(p)
            if tiles:
                out.append({"type": "riichi", "tiles": tiles})

        # 打牌
        if p.riichi:
            out.append({"type": "discard", "tiles": [p.drawn] if p.drawn is not None else []})
        else:
            out.append({"type": "discard", "tiles": [t for t in range(N_KINDS) if p.hand[t]]})
        return out

    def _riichi_discards(self, p: PlayerState) -> list[int]:
        out: list[int] = []
        for t in range(N_KINDS):
            if not p.hand[t]:
                continue
            p.hand[t] -= 1
            if is_tenpai(p.hand, p.melds):
                out.append(t)
            p.hand[t] += 1
        return out

    def _ankan_keeps_wait(self, p: PlayerState, tile: int) -> bool:
        before = set(p.waits())
        p.hand[tile] -= 4
        fake = Meld(MeldType.ANKAN, (tile,) * 4)
        after = set(waits(p.hand, [*p.melds, fake]))
        p.hand[tile] += 4
        return before == after

    # ------------------------------------------------------------------
    # 行動
    # ------------------------------------------------------------------
    def submit(self, seat: int, action: dict[str, Any]) -> None:
        if self.phase is Phase.ACT and seat == self.turn:
            self._do_act(seat, action)
        elif self.phase is Phase.CLAIM and seat in self.claims:
            c = self.claims[seat]
            if c.answer is None:
                c.answer = action
                self._maybe_resolve_claims()
        # 其餘情況直接忽略（不合法或過期的動作）

    def _do_act(self, seat: int, action: dict[str, Any]) -> None:
        p = self.players[seat]
        kind = action.get("type")

        if kind == "tsumo":
            self._win(seat, p.drawn, None, is_tsumo=True)
            return

        if kind == "ankan":
            tile = int(action["tile"])
            p.hand[tile] -= 4
            p.melds.append(Meld(MeldType.ANKAN, (tile,) * 4))
            p.drawn = None
            self.kan_count += 1
            self.first_turn = False
            self._clear_ippatsu()
            self.log(t="meld", seat=seat, kind="ankan", tile=tile)
            if self._offer_chankan(seat, tile, ankan=True):
                self.pending_kakan = (seat, tile)
                return
            self._reveal_dora()
            self._draw(seat, from_rinshan=True)
            return

        if kind == "kakan":
            tile = int(action["tile"])
            p.hand[tile] -= 1
            for i, m in enumerate(p.melds):
                if m.type is MeldType.PON and m.base == tile:
                    p.melds[i] = Meld(MeldType.KAKAN, (tile,) * 4, m.from_seat, tile)
                    break
            p.drawn = None
            self.kan_count += 1
            self._clear_ippatsu()
            self.log(t="meld", seat=seat, kind="kakan", tile=tile)
            if self._offer_chankan(seat, tile, ankan=False):
                self.pending_kakan = (seat, tile)
                return
            self._reveal_dora()
            self._draw(seat, from_rinshan=True)
            return

        if kind == "riichi":
            tile = int(action["tile"])
            p.riichi = True
            if self.first_turn:
                p.double_riichi = True
            p.ippatsu = True
            p.points -= self.cfg.riichi_stick
            self.riichi_sticks += 1
            self.log(t="riichi", seat=seat, double=p.double_riichi)
            self._discard(seat, tile, riichi=True)
            return

        if kind == "discard":
            self._discard(seat, int(action["tile"]))
            return

    # ------------------------------------------------------------------
    def _discard(self, seat: int, tile: int, riichi: bool = False) -> None:
        p = self.players[seat]
        if p.hand[tile] <= 0:
            tile = p.drawn if p.drawn is not None else next(
                t for t in range(N_KINDS) if p.hand[t]
            )
        tsumogiri = p.drawn == tile
        p.hand[tile] -= 1
        p.drawn = None
        p.river.append(Discard(tile, tsumogiri=tsumogiri, riichi=riichi))
        p.temp_furiten = False
        self.last_discard = (seat, tile)
        self.log(t="discard", seat=seat, tile=tile, tsumogiri=tsumogiri, riichi=riichi)

        was_after_kan = self.after_kan_draw
        self.after_kan_discard = was_after_kan
        self.after_kan_draw = False
        if riichi and not self.riichi_declared_this_hand:
            self._tsubame_tile = True
            self.riichi_declared_this_hand = True
        else:
            self._tsubame_tile = False

        self._open_claims(seat, tile)

    def _open_claims(self, from_seat: int, tile: int) -> None:
        self.claims = {}
        left = (from_seat + 1) % self.n
        for s in range(self.n):
            if s == from_seat:
                continue
            opts = self._claim_options(s, from_seat, tile, can_chi=(s == left))
            if opts:
                self.claims[s] = PendingClaim(seat=s, options=opts + [{"type": "pass"}])
        if self.claims:
            self.phase = Phase.CLAIM
        else:
            self._after_discard_no_claim()

    def _claim_options(
        self, seat: int, from_seat: int, tile: int, can_chi: bool
    ) -> list[dict[str, Any]]:
        p = self.players[seat]
        out: list[dict[str, Any]] = []

        # 榮和
        if not p.is_furiten():
            ctx = self._make_ctx(seat, tile, is_tsumo=False, from_seat=from_seat)
            r = evaluate(ctx)
            if r and r.has_yaku and (r.multiplier or r.han >= self.cfg.min_han):
                out.append({"type": "ron"})

        if p.riichi:
            return out  # 立直後不可鳴牌

        # 碰 / 大明槓
        if p.hand[tile] >= 2:
            out.append({"type": "pon", "tile": tile})
        if p.hand[tile] >= 3 and self.kan_count < MAX_KAN and self.wall:
            out.append({"type": "minkan", "tile": tile})

        # 吃（只能吃上家）
        if can_chi:
            starts = []
            for s in (tile - 2, tile - 1, tile):
                if s < 0 or s + 2 >= N_KINDS:
                    continue
                need = [x for x in (s, s + 1, s + 2) if x != tile]
                if all(p.hand[x] >= 1 for x in need):
                    starts.append(s)
            if starts:
                out.append({"type": "chi", "starts": starts})
        return out

    def _maybe_resolve_claims(self) -> None:
        if any(c.answer is None for c in self.claims.values()):
            return
        self._resolve_claims()

    def force_pass_remaining(self) -> None:
        """逾時：把尚未回應者視為 pass。"""
        if self.phase is not Phase.CLAIM:
            return
        for c in self.claims.values():
            if c.answer is None:
                c.answer = {"type": "pass"}
        self._resolve_claims()

    def _resolve_claims(self) -> None:
        claims = self.claims
        self.claims = {}
        rons = [c for c in claims.values() if c.answer and c.answer.get("type") == "ron"]

        # 搶槓
        if self.pending_kakan is not None:
            kan_seat, kan_tile = self.pending_kakan
            self.pending_kakan = None
            if rons:
                self._multi_ron(rons, kan_seat, kan_tile, chankan=True)
                return
            self._reveal_dora()
            self._draw(kan_seat, from_rinshan=True)
            return

        assert self.last_discard is not None
        from_seat, tile = self.last_discard

        if rons:
            self._multi_ron(rons, from_seat, tile, chankan=False)
            return

        # 沒和就記振聽（同巡內聽牌卻放過）
        for c in claims.values():
            if c.answer and c.answer.get("type") == "pass":
                p = self.players[c.seat]
                if tile in set(p.waits()):
                    p.temp_furiten = True
                    if p.riichi:
                        p.riichi_furiten = True

        # 鳴牌優先權：碰/槓 > 吃
        pon = next(
            (c for c in claims.values() if c.answer and c.answer["type"] in ("pon", "minkan")),
            None,
        )
        chi = next(
            (c for c in claims.values() if c.answer and c.answer["type"] == "chi"), None
        )
        take = pon or chi
        if take is None:
            self._after_discard_no_claim()
            return

        self.players[from_seat].river[-1].claimed = True
        self._apply_call(take.seat, from_seat, tile, take.answer)

    def _apply_call(
        self, seat: int, from_seat: int, tile: int, answer: dict[str, Any]
    ) -> None:
        p = self.players[seat]
        kind = answer["type"]
        self.first_turn = False
        self._clear_ippatsu()
        if kind == "pon":
            p.hand[tile] -= 2
            p.melds.append(Meld(MeldType.PON, (tile,) * 3, from_seat, tile))
            self.log(t="meld", seat=seat, kind="pon", tile=tile, from_seat=from_seat)
            self.turn = seat
            self.phase = Phase.ACT
            p.drawn = None
        elif kind == "minkan":
            p.hand[tile] -= 3
            p.melds.append(Meld(MeldType.MINKAN, (tile,) * 4, from_seat, tile))
            self.kan_count += 1
            self.log(t="meld", seat=seat, kind="minkan", tile=tile, from_seat=from_seat)
            self._reveal_dora()
            self._draw(seat, from_rinshan=True)
        elif kind == "chi":
            start = int(answer["start"])
            for x in (start, start + 1, start + 2):
                if x != tile:
                    p.hand[x] -= 1
            p.melds.append(Meld(MeldType.CHI, (start, start + 1, start + 2), from_seat, tile))
            self.log(t="meld", seat=seat, kind="chi", start=start, tile=tile, from_seat=from_seat)
            self.turn = seat
            self.phase = Phase.ACT
            p.drawn = None

    def _after_discard_no_claim(self) -> None:
        if not self.wall:
            self._exhaustive_draw()
            return
        assert self.last_discard is not None
        from_seat, _ = self.last_discard
        nxt = (from_seat + 1) % self.n
        self.turn_index += 1
        if self.turn_index >= self.n:
            self.first_turn = False
        self._draw(nxt)

    def _clear_ippatsu(self) -> None:
        for p in self.players:
            p.ippatsu = False

    def _reveal_dora(self) -> None:
        if self.opened_dora < 5:
            self.opened_dora += 1
            self.log(t="dora", tile=self.dora_ind[self.opened_dora - 1])

    def _offer_chankan(self, kan_seat: int, tile: int, ankan: bool) -> bool:
        """加槓可被任何人搶；暗槓只能被役滿牌型搶。"""
        self.claims = {}
        for s in range(self.n):
            if s == kan_seat:
                continue
            p = self.players[s]
            if p.is_furiten():
                continue
            ctx = self._make_ctx(s, tile, is_tsumo=False, from_seat=kan_seat, chankan=True)
            r = evaluate(ctx)
            if not r or not r.has_yaku:
                continue
            if ankan and not r.multiplier:
                continue
            if not r.multiplier and r.han < self.cfg.min_han:
                continue
            self.claims[s] = PendingClaim(
                seat=s, options=[{"type": "ron"}, {"type": "pass"}]
            )
        if self.claims:
            self.last_discard = (kan_seat, tile)
            self.phase = Phase.CLAIM
            return True
        return False

    # ------------------------------------------------------------------
    # 和牌 / 流局
    # ------------------------------------------------------------------
    def _make_ctx(
        self,
        seat: int,
        tile: int,
        is_tsumo: bool,
        from_seat: int | None = None,
        chankan: bool = False,
    ) -> WinContext:
        p = self.players[seat]
        concealed = list(p.hand)
        if not is_tsumo:
            concealed[tile] += 1
        return WinContext(
            concealed=concealed,
            melds=list(p.melds),
            win_tile=tile,
            is_tsumo=is_tsumo,
            is_dealer=seat == self.dealer,
            seat=seat,
            riichi=p.riichi,
            double_riichi=p.double_riichi,
            ippatsu=p.ippatsu,
            rinshan=is_tsumo and self.after_kan_draw,
            chankan=chankan,
            haitei=is_tsumo and not self.wall,
            houtei=(not is_tsumo) and (not self.wall) and not chankan,
            kanfuri=(not is_tsumo) and self.after_kan_discard and not chankan,
            tsubame=(not is_tsumo) and getattr(self, "_tsubame_tile", False),
            tenhou=is_tsumo and self.first_turn and seat == self.dealer and not p.river,
            chiihou=(
                is_tsumo
                and self.first_turn
                and seat != self.dealer
                and not p.river
                and not p.melds
            ),
            renhou=(
                (not is_tsumo)
                and self.first_turn
                and seat != self.dealer
                and not p.river
                and not p.melds
            ),
            dora_indicators=self.dora_ind[: self.opened_dora],
            ura_indicators=self.ura_ind[: self.opened_dora],
            dora_wrap=self.cfg.dora_wrap,
            tsumo_mode=self.cfg.tsumo_mode,
        )

    def _win(self, seat: int, tile: int, from_seat: int | None, is_tsumo: bool) -> None:
        ctx = self._make_ctx(seat, tile, is_tsumo=is_tsumo, from_seat=from_seat)
        r = evaluate(ctx)
        assert r is not None
        total = total_points(r, seat == self.dealer, self.cfg)
        delta = payments(
            total,
            winner=seat,
            loser=from_seat,
            seats=list(range(self.n)),
            dealer=self.dealer,
            cfg=self.cfg,
            honba=self.honba,
        )
        delta[seat] += self.riichi_sticks * self.cfg.riichi_stick
        self.riichi_sticks = 0
        for s, d in delta.items():
            self.players[s].points += d
        self._finish_hand(
            {
                "type": "win",
                "winner": seat,
                "from": from_seat,
                "tsumo": is_tsumo,
                "tile": tile,
                "yaku": [{"name": n, "han": h} for n, h in r.yaku],
                "yakuman": [{"name": n, "mult": m} for n, m in r.yakuman],
                "han": r.han,
                "multiplier": r.multiplier,
                "points": total,
                "delta": delta,
                "hand": self.players[seat].hand_tiles,
                "melds": [
                    {"type": m.type.value, "tiles": list(m.tiles), "from": m.from_seat}
                    for m in self.players[seat].melds
                ],
                "dora": self.dora_ind[: self.opened_dora],
                "ura": self.ura_ind[: self.opened_dora]
                if (self.players[seat].riichi or self.players[seat].double_riichi)
                else [],
            },
            dealer_keeps=(seat == self.dealer),
        )

    def _multi_ron(
        self, rons: list[PendingClaim], from_seat: int, tile: int, chankan: bool
    ) -> None:
        """多家榮和：依打者的下家順序逐一結算（頭跳制可自行改）。"""
        order = sorted(rons, key=lambda c: (c.seat - from_seat) % self.n)
        winners: list[dict[str, Any]] = []
        total_delta = {s: 0 for s in range(self.n)}
        for idx, c in enumerate(order):
            seat = c.seat
            ctx = self._make_ctx(seat, tile, is_tsumo=False, from_seat=from_seat, chankan=chankan)
            r = evaluate(ctx)
            if r is None:
                continue
            total = total_points(r, seat == self.dealer, self.cfg)
            d = payments(
                total,
                winner=seat,
                loser=from_seat,
                seats=list(range(self.n)),
                dealer=self.dealer,
                cfg=self.cfg,
                honba=self.honba if idx == 0 else 0,
            )
            if idx == 0:
                d[seat] += self.riichi_sticks * self.cfg.riichi_stick
                self.riichi_sticks = 0
            for s, v in d.items():
                total_delta[s] += v
            winners.append(
                {
                    "winner": seat,
                    "yaku": [{"name": n, "han": h} for n, h in r.yaku],
                    "yakuman": [{"name": n, "mult": m} for n, m in r.yakuman],
                    "han": r.han,
                    "multiplier": r.multiplier,
                    "points": total,
                    "hand": self.players[seat].hand_tiles,
                    "melds": [
                        {"type": m.type.value, "tiles": list(m.tiles), "from": m.from_seat}
                        for m in self.players[seat].melds
                    ],
                }
            )
        for s, v in total_delta.items():
            self.players[s].points += v
        self._finish_hand(
            {
                "type": "ron",
                "from": from_seat,
                "tile": tile,
                "chankan": chankan,
                "winners": winners,
                "delta": total_delta,
                "dora": self.dora_ind[: self.opened_dora],
            },
            dealer_keeps=any(w["winner"] == self.dealer for w in winners),
        )

    def _exhaustive_draw(self) -> None:
        tenpai = [p.seat for p in self.players if is_tenpai(p.hand, p.melds)]
        delta = noten_payments(tenpai, list(range(self.n)), self.cfg)
        for s, d in delta.items():
            self.players[s].points += d
        self._finish_hand(
            {
                "type": "draw",
                "tenpai": tenpai,
                "delta": delta,
                "hands": {
                    p.seat: p.hand_tiles for p in self.players if p.seat in tenpai
                },
            },
            dealer_keeps=(self.dealer in tenpai and self.cfg.renchan_on_dealer_tenpai),
            is_draw=True,
        )

    def _finish_hand(
        self, result: dict[str, Any], dealer_keeps: bool, is_draw: bool = False
    ) -> None:
        self.result = result
        self.log(t="hand_end", **{k: v for k, v in result.items() if k != "hands"})
        self.phase = Phase.HAND_END
        self._next_dealer_keeps = dealer_keeps
        self._next_is_draw = is_draw

    def next_hand(self) -> bool:
        """進入下一局。回傳 False 代表整場結束。"""
        if self.phase is not Phase.HAND_END:
            return self.phase is not Phase.GAME_END
        keeps = getattr(self, "_next_dealer_keeps", False)
        if keeps:
            self.honba += 1  # 連莊
        else:
            self.honba = 0
            self.dealer = (self.dealer + 1) % self.n
            self.hand_no += 1
        if self.hand_no >= self.total_hands or any(p.points < 0 for p in self.players):
            self.phase = Phase.GAME_END
            return False
        self.start_hand()
        return True

    # ------------------------------------------------------------------
    def standings(self) -> list[dict[str, Any]]:
        rows = sorted(self.players, key=lambda p: -p.points)
        return [
            {"rank": i + 1, "seat": p.seat, "name": p.name, "points": p.points}
            for i, p in enumerate(rows)
        ]

    def public_state(self) -> dict[str, Any]:
        return {
            "phase": self.phase.value,
            "dealer": self.dealer,
            "turn": self.turn,
            "handNo": self.hand_no,
            "totalHands": self.total_hands,
            "honba": self.honba,
            "riichiSticks": self.riichi_sticks,
            "wallLeft": len(self.wall),
            "dora": self.dora_ind[: self.opened_dora],
            "players": [
                {
                    "seat": p.seat,
                    "name": p.name,
                    "isBot": p.is_bot,
                    "points": p.points,
                    "riichi": p.riichi,
                    "handCount": sum(p.hand),
                    "melds": [
                        {
                            "type": m.type.value,
                            "tiles": list(m.tiles),
                            "from": m.from_seat,
                        }
                        for m in p.melds
                    ],
                    "river": [
                        {
                            "tile": d.tile,
                            "tsumogiri": d.tsumogiri,
                            "riichi": d.riichi,
                            "claimed": d.claimed,
                        }
                        for d in p.river
                    ],
                }
                for p in self.players
            ],
            "result": self.result,
        }

    def state_for(self, seat: int) -> dict[str, Any]:
        st = self.public_state()
        p = self.players[seat]
        st["you"] = {
            "seat": seat,
            "hand": p.hand_tiles,
            "drawn": p.drawn,
            "waits": p.waits(),
            "furiten": p.is_furiten(),
            "actions": self.legal_actions(seat),
        }
        return st

    def waiting_on(self) -> list[int]:
        if self.phase is Phase.ACT:
            return [self.turn]
        if self.phase is Phase.CLAIM:
            return [s for s, c in self.claims.items() if c.answer is None]
        return []


def describe_tiles(tiles: Iterable[int]) -> str:
    return "".join(to_char(t) for t in tiles)


__all__ = [
    "Game",
    "Phase",
    "PlayerState",
    "ScoreConfig",
    "MODE_HANCHAN",
    "MODE_TONPUU",
    "MODE_SINGLE",
    "describe_tiles",
    "TILE_COUNTS",
    "YakuResult",
]
