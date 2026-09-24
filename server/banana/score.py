"""計分表與付點分攤（不計符）。"""

from __future__ import annotations

from dataclasses import dataclass

from .yaku import TSUMO_MODE_MENZEN, YakuResult

# ---- 東風 / 半莊：(番區間下限, 上限, (閒家點, 莊家點)) ----
TABLE_RANKED: list[tuple[int, int, tuple[int, int]]] = [
    (1, 1, (1000, 1500)),
    (2, 2, (2000, 3000)),
    (3, 3, (4000, 6000)),
    (4, 4, (6400, 9600)),
    (5, 5, (8000, 12000)),
    (6, 7, (12000, 18000)),
    (8, 10, (16000, 24000)),
    (11, 12, (24000, 36000)),
]
YAKUMAN_RANKED = (32000, 48000)

# ---- 一局戰 方法一（與日麻較相近） ----
TABLE_SINGLE_A: list[tuple[int, int, int]] = [
    (1, 1, 1500), (2, 2, 3000), (3, 3, 4500), (4, 4, 6000), (5, 5, 9000),
    (6, 7, 12000), (8, 10, 18000), (11, 12, 24000),
]
# ---- 一局戰 方法二（六番以上分段細化） ----
TABLE_SINGLE_B: list[tuple[int, int, int]] = [
    (1, 1, 1500), (2, 2, 3000), (3, 3, 4500), (4, 4, 6000), (5, 5, 9000),
    (6, 6, 12000), (7, 7, 15000), (8, 8, 18000), (9, 10, 21000), (11, 12, 24000),
]
YAKUMAN_SINGLE = 36000

MODE_HANCHAN = "hanchan"   # 半莊（東+南）
MODE_TONPUU = "tonpuu"     # 東風戰
MODE_SINGLE = "single"     # 一局戰


@dataclass(slots=True)
class ScoreConfig:
    mode: str = MODE_HANCHAN
    single_table: str = "a"            # 一局戰計分法 'a' 或 'b'
    start_points: int = 35000          # 規則書建議
    target_points: int = 40000         # 一位必要點數（建議）
    min_han: int = 1                   # 番縛
    tsumo_mode: str = TSUMO_MODE_MENZEN
    dora_wrap: bool = True             # Z 的下一張是否為 A（規則書未定義，預設環繞）
    # 以下規則書未載明，採日麻慣例，可自行調整
    riichi_stick: int = 1000
    honba_bonus: int = 0
    noten_penalty: int = 3000
    renchan_on_dealer_tenpai: bool = True


def _lookup(table, han: int):
    for lo, hi, val in table:
        if lo <= han <= hi:
            return val
    return None


def total_points(result: YakuResult, is_dealer: bool, cfg: ScoreConfig) -> int:
    """和牌的總得點（尚未分攤）。"""
    if cfg.mode == MODE_SINGLE:
        base = YAKUMAN_SINGLE
        if result.multiplier:
            return base * result.multiplier
        han = result.han
        if han >= 26:
            return base * 2
        if han >= 13:
            return base
        table = TABLE_SINGLE_A if cfg.single_table == "a" else TABLE_SINGLE_B
        val = _lookup(table, han)
        return val if val is not None else base
    # 東風 / 半莊
    idx = 1 if is_dealer else 0
    if result.multiplier:
        return YAKUMAN_RANKED[idx] * result.multiplier
    han = result.han
    if han >= 26:
        return YAKUMAN_RANKED[idx] * 2
    if han >= 13:
        return YAKUMAN_RANKED[idx]
    val = _lookup(TABLE_RANKED, han)
    return val[idx] if val is not None else YAKUMAN_RANKED[idx]


def _ceil100(x: float) -> int:
    return int(-(-x // 100) * 100)


def payments(
    total: int,
    winner: int,
    loser: int | None,
    seats: list[int],
    dealer: int,
    cfg: ScoreConfig,
    honba: int = 0,
) -> dict[int, int]:
    """回傳 {座位: 點數增減}，總和為 0。

    loser=None 代表自摸。
    莊家自摸：三家（其餘所有閒家）各賠 1/n。
    閒家自摸：莊家賠 1/2，其餘各家均分另外 1/2。
    """
    delta = {s: 0 for s in seats}
    bonus = cfg.honba_bonus * honba
    others = [s for s in seats if s != winner]

    if loser is not None:
        pay = total + bonus
        delta[loser] -= pay
        delta[winner] += pay
        return delta

    # 一局戰不分莊閒：自摸時其餘各家均分
    if cfg.mode == MODE_SINGLE or winner == dealer:
        each = _ceil100(total / len(others)) + (bonus // max(len(others), 1))
        for s in others:
            delta[s] -= each
            delta[winner] += each
    else:
        dealer_pay = _ceil100(total / 2)
        rest = [s for s in others if s != dealer]
        each = _ceil100(total / 2 / len(rest)) if rest else 0
        delta[dealer] -= dealer_pay
        delta[winner] += dealer_pay
        for s in rest:
            delta[s] -= each
            delta[winner] += each
    return delta


def noten_payments(
    tenpai: list[int], seats: list[int], cfg: ScoreConfig
) -> dict[int, int]:
    """流局聽牌罰符（規則書未載明，採日麻 3000 總額慣例）。"""
    delta = {s: 0 for s in seats}
    noten = [s for s in seats if s not in tenpai]
    if not tenpai or not noten:
        return delta
    pay = _ceil100(cfg.noten_penalty / len(noten))
    pot = pay * len(noten)
    share = (pot // len(tenpai) // 100) * 100
    for s in noten:
        delta[s] -= pay
    for s in tenpai:
        delta[s] += share
    # 除不盡的零頭給離莊最近的聽牌者，確保總和為 0
    delta[tenpai[0]] += pot - share * len(tenpai)
    return delta
