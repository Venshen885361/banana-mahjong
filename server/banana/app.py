"""FastAPI + WebSocket 伺服器。

啟動：
    uv run uvicorn banana.app:app --host 0.0.0.0 --port 8000
或：
    python -m banana.app
"""

from __future__ import annotations

import os
import secrets
import time
from contextlib import suppress
from pathlib import Path
from typing import Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .room import Room, RoomConfig
from .score import MODE_HANCHAN
from .tiles import TILE_COUNTS, TOTAL_TILES

app = FastAPI(title="Banana 英文字母麻將")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

ROOMS: dict[str, Room] = {}
ROOM_TTL = 60 * 60 * 6


class CreateRoom(BaseModel):
    name: str = Field(default="新房間", max_length=32)
    mode: str = MODE_HANCHAN
    singleTable: str = "a"
    maxPlayers: int = Field(default=4, ge=2, le=6)
    minHan: int = Field(default=1, ge=0, le=5)
    tsumoMode: str = "menzen_tsumo"
    doraWrap: bool = True


def _gc() -> None:
    now = time.time()
    for rid in [r.id for r in ROOMS.values() if now - r.created > ROOM_TTL and not r.started]:
        ROOMS.pop(rid, None)


@app.get("/api/meta")
def meta() -> dict[str, Any]:
    return {
        "tileCounts": list(TILE_COUNTS),
        "totalTiles": TOTAL_TILES,
        "modes": ["hanchan", "tonpuu", "single"],
    }


@app.get("/api/rooms")
def list_rooms() -> list[dict[str, Any]]:
    _gc()
    return [r.summary() for r in ROOMS.values()]


@app.post("/api/rooms")
def create_room(body: CreateRoom) -> dict[str, Any]:
    _gc()
    rid = secrets.token_hex(3).upper()
    while rid in ROOMS:
        rid = secrets.token_hex(3).upper()
    cfg = RoomConfig(
        mode=body.mode,
        single_table=body.singleTable,
        max_players=body.maxPlayers,
        min_han=body.minHan,
        tsumo_mode=body.tsumoMode,
        dora_wrap=body.doraWrap,
    )
    ROOMS[rid] = Room(rid, body.name, cfg)
    return {"id": rid}


@app.websocket("/ws/{room_id}")
async def ws_endpoint(ws: WebSocket, room_id: str) -> None:
    await ws.accept()
    room = ROOMS.get(room_id.upper())
    if room is None:
        await ws.send_json({"t": "error", "msg": "找不到房間"})
        await ws.close()
        return

    name = ws.query_params.get("name") or "玩家"
    token = ws.query_params.get("token") or None
    seat = room.join(name[:16], token)
    if seat is None:
        await ws.send_json({"t": "error", "msg": "房間已滿或已開始"})
        await ws.close()
        return

    seat.ws = ws
    seat.connected = True
    await ws.send_json(
        {"t": "hello", "seat": seat.index, "token": seat.token, "room": room.room_state()}
    )
    await room.broadcast()

    try:
        while True:
            msg = await ws.receive_json()
            await _handle(room, seat.index, seat.token, msg)
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        seat.connected = False
        seat.ws = None
        with suppress(Exception):
            await room.broadcast()


async def _handle(room: Room, seat_index: int, token: str, msg: dict[str, Any]) -> None:
    kind = msg.get("t")
    if kind == "action":
        await room.submit(seat_index, msg.get("action") or {})
    elif kind == "chat":
        text = str(msg.get("text", ""))[:200]
        if text:
            room.chat.append({"seat": seat_index, "text": text, "ts": time.time()})
            await room.broadcast()
    elif kind == "addBot" and room.is_host(token):
        room.add_bot()
        await room.broadcast()
    elif kind == "removeSeat" and room.is_host(token):
        room.remove_seat(int(msg.get("seat", -1)))
        await room.broadcast()
    elif kind == "config" and room.is_host(token) and not room.started:
        c = msg.get("config") or {}
        room.cfg.mode = c.get("mode", room.cfg.mode)
        room.cfg.single_table = c.get("singleTable", room.cfg.single_table)
        room.cfg.max_players = max(2, min(6, int(c.get("maxPlayers", room.cfg.max_players))))
        room.cfg.min_han = int(c.get("minHan", room.cfg.min_han))
        room.cfg.tsumo_mode = c.get("tsumoMode", room.cfg.tsumo_mode)
        room.cfg.dora_wrap = bool(c.get("doraWrap", room.cfg.dora_wrap))
        await room.broadcast()
    elif kind == "start" and room.is_host(token):
        err = room.start()
        if err:
            await room._safe_send(room.seats[seat_index], {"t": "error", "msg": err})
        else:
            await room.kick_off()
    elif kind == "nextHand" and room.is_host(token):
        await room._auto_next_hand()


# ---- 生產環境：直接吐出前端打包結果 ----
_WEB = Path(os.environ.get("BANANA_WEB_DIST", Path(__file__).resolve().parents[2] / "web" / "dist"))
if _WEB.is_dir():
    app.mount("/assets", StaticFiles(directory=_WEB / "assets"), name="assets")

    @app.get("/{full_path:path}")
    def spa(full_path: str) -> FileResponse:
        target = _WEB / full_path
        if full_path and target.is_file():
            return FileResponse(target)
        return FileResponse(_WEB / "index.html")


def main() -> None:
    import uvicorn

    uvicorn.run(
        "banana.app:app",
        host=os.environ.get("HOST", "0.0.0.0"),
        port=int(os.environ.get("PORT", 8000)),
        reload=bool(os.environ.get("RELOAD")),
    )


if __name__ == "__main__":
    main()
