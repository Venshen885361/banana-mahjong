"""簡易 AI：向聽數貪心 + 保守鳴牌。人數不足時補位、也用來跑自我對局測試。"""

from __future__ import annotations

import random
from typing import Any

from .game import Game
from .hand import shanten
from .meld import Meld, MeldType
from .tiles import N_KINDS


class Bot:
    def __init__(self, seat: int, seed: int | None = None, aggression: float = 0.5):
        self.seat = seat
        self.rng = random.Random(seed)
        self.aggression = aggression

    # ------------------------------------------------------------------
    def choose(self, game: Game, options: list[dict[str, Any]]) -> dict[str, Any]:
        types = {o["type"]: o for o in options}

        if "tsumo" in types:
            return {"type": "tsumo"}
        if "ron" in types:
            return {"type": "ron"}

        # 立直：聽牌就立（簡單策略）
        if "riichi" in types and self.rng.random() < 0.85:
            tiles = types["riichi"]["tiles"]
            best = min(tiles, key=lambda t: self._safety(game, t))
            return {"type": "riichi", "tile": best}

        if "ankan" in types and self.rng.random() < 0.7:
            return {"type": "ankan", "tile": types["ankan"]["tile"]}

        if "discard" in types:
            return {"type": "discard", "tile": self._best_discard(game, types["discard"])}

        # 鳴牌：只在能明顯推進向聽時
        for kind in ("minkan", "pon", "chi"):
            if kind not in types:
                continue
            if self._call_improves(game, kind, types[kind]):
                if kind == "chi":
                    return {"type": "chi", "start": types["chi"]["starts"][0]}
                return {"type": kind, "tile": types[kind]["tile"]}
        return {"type": "pass"}

    # ------------------------------------------------------------------
    def _best_discard(self, game: Game, opt: dict[str, Any]) -> int:
        p = game.players[self.seat]
        candidates = [t for t in opt["tiles"] if p.hand[t] > 0]
        if not candidates:
            return next(t for t in range(N_KINDS) if p.hand[t])
        if len(candidates) == 1:
            return candidates[0]
        scored: list[tuple[int, float, int]] = []
        for t in candidates:
            p.hand[t] -= 1
            sh = shanten(p.hand, p.melds)
            p.hand[t] += 1
            scored.append((sh, self._safety(game, t), t))
        scored.sort(key=lambda x: (x[0], x[1], self.rng.random()))
        return scored[0][2]

    def _safety(self, game: Game, tile: int) -> float:
        """越小越安全。有人立直時避開生張。"""
        danger = 0.0
        for q in game.players:
            if q.seat == self.seat or not q.riichi:
                continue
            if any(d.tile == tile for d in q.river):
                continue  # 現物
            danger += 1.0
        return danger * (1.0 - self.aggression)

    def _call_improves(self, game: Game, kind: str, opt: dict[str, Any]) -> bool:
        p = game.players[self.seat]
        before = shanten(p.hand, p.melds)
        assert game.last_discard is not None
        tile = game.last_discard[1]
        hand = list(p.hand)
        melds = list(p.melds)
        if kind == "pon":
            hand[tile] -= 2
            melds.append(Meld(MeldType.PON, (tile,) * 3, 0, tile))
        elif kind == "minkan":
            hand[tile] -= 3
            melds.append(Meld(MeldType.MINKAN, (tile,) * 4, 0, tile))
        else:
            start = opt["starts"][0]
            for x in (start, start + 1, start + 2):
                if x != tile:
                    hand[x] -= 1
            melds.append(Meld(MeldType.CHI, (start, start + 1, start + 2), 0, tile))
        if any(c < 0 for c in hand):
            return False
        after = shanten(hand, melds)
        # 只在能推進向聽、且不會把門前清役全部打掉時才鳴
        return after < before and (after <= 1 or not p.menzen)


def autoplay(game: Game, max_steps: int = 20000, seed: int | None = None) -> None:
    """讓所有座位都由 bot 操作，跑完整場。測試用。"""
    rng = random.Random(seed)
    bots = {p.seat: Bot(p.seat, seed=rng.randrange(1 << 30)) for p in game.players}
    steps = 0
    from .game import Phase

    if game.phase is Phase.WAITING:
        game.start_hand()
    while steps < max_steps:
        steps += 1
        if game.phase is Phase.HAND_END:
            if not game.next_hand():
                return
            continue
        if game.phase is Phase.GAME_END:
            return
        waiting = game.waiting_on()
        if not waiting:
            raise RuntimeError(f"卡住了：phase={game.phase}")
        for seat in list(waiting):
            opts = game.legal_actions(seat)
            if not opts:
                continue
            game.submit(seat, bots[seat].choose(game, opts))
    raise RuntimeError("超過最大步數，可能有無限迴圈")
