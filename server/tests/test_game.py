from __future__ import annotations

import pytest

from banana.bot import autoplay
from banana.game import Game, Phase
from banana.score import (
    MODE_HANCHAN,
    MODE_SINGLE,
    MODE_TONPUU,
    ScoreConfig,
    noten_payments,
    payments,
    total_points,
)
from banana.yaku import YakuResult


def _total(g: Game) -> int:
    return sum(p.points for p in g.players) + g.riichi_sticks * g.cfg.riichi_stick


@pytest.mark.parametrize("n", [2, 3, 4, 5, 6])
def test_selfplay_points_conserved(n):
    seats = [f"P{i+1}" for i in range(n)]
    for seed in range(4):
        g = Game(seats, ScoreConfig(mode=MODE_TONPUU), seed=seed, bots=range(n))
        start = n * g.cfg.start_points
        autoplay(g, seed=seed)
        assert _total(g) == start, (n, seed, [p.points for p in g.players])
        assert g.phase in (Phase.GAME_END, Phase.HAND_END)


def test_hanchan_length():
    g = Game(["A", "B", "C", "D"], ScoreConfig(mode=MODE_HANCHAN), seed=3, bots=range(4))
    autoplay(g, seed=3)
    assert g.hand_no >= g.total_hands or any(p.points < 0 for p in g.players)


def test_single_hand_mode():
    g = Game(["A", "B", "C", "D"], ScoreConfig(mode=MODE_SINGLE), seed=5, bots=range(4))
    autoplay(g, seed=5)
    assert g.total_hands == 1


def test_wall_sizes():
    g = Game(["A", "B", "C", "D"], seed=1)
    g.start_hand()
    # 144 - 14(王牌) - 13*4(配牌) - 1(莊家第一摸)
    assert len(g.wall) == 144 - 14 - 52 - 1
    assert len(g.rinshan) == 4 and len(g.dora_ind) == 5 and len(g.ura_ind) == 5


# ---------------------------------------------------------------- 計分
def _res(han=0, mult=0):
    return YakuResult(han=han, multiplier=mult)


def test_score_table_ranked():
    cfg = ScoreConfig(mode=MODE_HANCHAN)
    assert total_points(_res(1), False, cfg) == 1000
    assert total_points(_res(1), True, cfg) == 1500
    assert total_points(_res(4), True, cfg) == 9600
    assert total_points(_res(7), False, cfg) == 12000
    assert total_points(_res(12), True, cfg) == 36000
    assert total_points(_res(13), False, cfg) == 32000      # 累計役滿
    assert total_points(_res(26), False, cfg) == 64000      # 兩倍累計役滿
    assert total_points(_res(0, 3), False, cfg) == 96000    # 三倍役滿


def test_score_table_single():
    a = ScoreConfig(mode=MODE_SINGLE, single_table="a")
    b = ScoreConfig(mode=MODE_SINGLE, single_table="b")
    assert total_points(_res(6), False, a) == 12000
    assert total_points(_res(7), False, a) == 12000
    assert total_points(_res(7), False, b) == 15000
    assert total_points(_res(9), False, b) == 21000
    assert total_points(_res(0, 1), False, a) == 36000


def test_tsumo_split_dealer():
    cfg = ScoreConfig()
    d = payments(12000, winner=0, loser=None, seats=[0, 1, 2, 3], dealer=0, cfg=cfg)
    assert d[1] == d[2] == d[3] == -4000
    assert d[0] == 12000


def test_tsumo_split_non_dealer():
    cfg = ScoreConfig()
    d = payments(8000, winner=1, loser=None, seats=[0, 1, 2, 3], dealer=0, cfg=cfg)
    assert d[0] == -4000          # 莊家 1/2
    assert d[2] == d[3] == -2000  # 其餘各 1/4
    assert sum(d.values()) == 0


def test_single_mode_tsumo_split():
    cfg = ScoreConfig(mode=MODE_SINGLE)
    d = payments(3000, winner=1, loser=None, seats=[0, 1, 2, 3], dealer=0, cfg=cfg)
    assert d[0] == d[2] == d[3] == -1000   # 一局戰不分莊閒，三家各 1/3
    assert d[1] == 3000


def test_noten_conserved():
    cfg = ScoreConfig()
    for seats, tenpai in [
        ([0, 1, 2, 3], [0]),
        ([0, 1, 2, 3], [0, 1]),
        ([0, 1, 2, 3, 4, 5], [0, 1]),
        ([0, 1, 2, 3, 4, 5], [0, 1, 2, 3, 4]),
    ]:
        d = noten_payments(tenpai, seats, cfg)
        assert sum(d.values()) == 0
