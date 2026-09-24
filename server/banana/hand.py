"""手牌拆解、聽牌判定、待張計算。

和牌型態共三種：
  1. standard —— 4 面子 + 1 雀頭
  2. chiitoi  —— 七組不同對子（門前清限定）
  3. dragon   —— 一條龍：連續的 14 張牌（每張各一）
"""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from functools import lru_cache

from .meld import Block, Decomposition, Meld
from .tiles import N_KINDS, A, E, counts_of

# --------------------------------------------------------------------------
# 基本拆解
# --------------------------------------------------------------------------


def _melds_from(counts: list[int], need: int, start: int) -> Iterator[tuple[Block, ...]]:
    """把 counts 完整拆成 need 個面子。以「最小未用字母必須被使用」剪枝，保證不重複列舉。"""
    if need == 0:
        if not any(counts):
            yield ()
        return
    i = start
    while i < N_KINDS and counts[i] == 0:
        i += 1
    if i >= N_KINDS:
        return
    # 刻子
    if counts[i] >= 3:
        counts[i] -= 3
        for rest in _melds_from(counts, need - 1, i):
            yield (Block("pon", i),) + rest
        counts[i] += 3
    # 順子
    if i + 2 < N_KINDS and counts[i + 1] > 0 and counts[i + 2] > 0:
        counts[i] -= 1
        counts[i + 1] -= 1
        counts[i + 2] -= 1
        for rest in _melds_from(counts, need - 1, i):
            yield (Block("chi", i),) + rest
        counts[i] += 1
        counts[i + 1] += 1
        counts[i + 2] += 1


def standard_decompositions(
    counts: Sequence[int], n_sets_needed: int
) -> list[tuple[int, tuple[Block, ...]]]:
    """回傳所有 (雀頭字母, 面子tuple) 的拆解方式。"""
    work = list(counts)
    out: list[tuple[int, tuple[Block, ...]]] = []
    for p in range(N_KINDS):
        if work[p] < 2:
            continue
        work[p] -= 2
        for melds in _melds_from(work, n_sets_needed, 0):
            out.append((p, melds))
        work[p] += 2
    return out


def is_chiitoi(counts: Sequence[int]) -> bool:
    """七組『不同』的對子。"""
    return sum(1 for c in counts if c == 2) == 7 and sum(counts) == 14


def is_dragon(counts: Sequence[int]) -> bool:
    """一條龍：連續 14 張不同字母各一張。"""
    if sum(counts) != 14:
        return False
    idx = [i for i, c in enumerate(counts) if c]
    if len(idx) != 14 or any(c != 1 for c in counts if c):
        return False
    return idx[-1] - idx[0] == 13


# --------------------------------------------------------------------------
# 和牌判定
# --------------------------------------------------------------------------


def winning_decompositions(
    concealed: Sequence[int], melds: Sequence[Meld]
) -> list[Decomposition]:
    """列出所有合法的和牌拆解；空 list 代表沒和。

    concealed: 長度 26 的張數陣列，**含和了牌**，不含副露。
    """
    results: list[Decomposition] = []

    all_counts = list(concealed)
    for m in melds:
        for t in m.tiles:
            all_counts[t] += 1
    total_all = sum(all_counts)

    # 這兩型不走「4 面子 + 1 雀頭」，所以要在張數檢查之前判（含槓的情況）
    if total_all == 14:
        # Rush A：把牌山全部 13 張 A 收齊 + 任意 1 張。13 張 A 湊不出雀頭，故為獨立型
        if all_counts[A] == 13:
            results.append(Decomposition(pair=None, blocks=[], form="rush_a"))
        # Rush E：14 張 E（含被槓走的）
        if all_counts[E] == 14:
            results.append(Decomposition(pair=None, blocks=[], form="rush_e"))

    total = sum(concealed)
    n_called = len(melds)
    need = 4 - n_called
    if need < 0 or total != 2 + 3 * need:
        return results

    called_blocks = [m.as_block() for m in melds]

    for pair, sets in standard_decompositions(concealed, need):
        blocks = [Block("pair", pair), *sets, *called_blocks]
        results.append(Decomposition(pair=pair, blocks=blocks, form="standard"))

    if n_called == 0:
        if is_chiitoi(concealed):
            pairs = [i for i, c in enumerate(concealed) if c == 2]
            results.append(
                Decomposition(
                    pair=None,
                    blocks=[Block("pair", p) for p in pairs],
                    form="chiitoi",
                )
            )

    # 一條龍：14 張連續。允許有副露（總張數仍須為 14 張連續不同字母）
    if is_dragon(all_counts):
        idx = [i for i, c in enumerate(all_counts) if c]
        results.append(
            Decomposition(
                pair=None,
                blocks=[Block("pair", i) for i in idx],  # 佔位用，一條龍不再細分
                form="dragon",
            )
        )
    return results


def is_winning(concealed: Sequence[int], melds: Sequence[Meld] = ()) -> bool:
    return bool(winning_decompositions(concealed, melds))


# --------------------------------------------------------------------------
# 聽牌 / 待張
# --------------------------------------------------------------------------

from .tiles import TILE_COUNTS  # noqa: E402


def waits(concealed: Sequence[int], melds: Sequence[Meld] = ()) -> list[int]:
    """回傳所有能讓此手牌和牌的字母（不檢查剩餘張數，但排除自己已持有 4 張以上者）。"""
    work = list(concealed)
    used_total = list(work)
    for m in melds:
        for t in m.tiles:
            used_total[t] += 1
    out: list[int] = []
    for t in range(N_KINDS):
        if used_total[t] >= TILE_COUNTS[t]:
            continue
        work[t] += 1
        if is_winning(work, melds):
            out.append(t)
        work[t] -= 1
    return out


def is_tenpai(concealed: Sequence[int], melds: Sequence[Meld] = ()) -> bool:
    return bool(waits(concealed, melds))


def shanten(concealed: Sequence[int], melds: Sequence[Meld] = ()) -> int:
    """粗略向聽數（-1 = 已和）。標準型 + 七對子取小。給 bot 用，非嚴格最佳化實作。"""
    if is_winning(concealed, melds):
        return -1
    n_called = len(melds)
    need = 4 - n_called
    best = _standard_shanten(list(concealed), need)
    if n_called == 0:
        pairs = sum(1 for c in concealed if c >= 2)
        kinds = sum(1 for c in concealed if c >= 1)
        chiitoi = 6 - pairs + max(0, 7 - kinds)
        best = min(best, chiitoi)
    return best


def _standard_shanten(counts: list[int], need: int) -> int:
    """need = 還要從手牌湊出的面子數（4 - 副露數）。

    向聽公式：8 - 2*面子 - min(搭子, 4-面子) - (有雀頭 ? 1 : 0)
    以「位置 i 及其後兩張的剩餘量」為狀態做記憶化 DP，回傳所有可達的
    (面子, 搭子, 雀頭) 組合（已上限截斷），再套公式取最小值。
    """
    return _shanten_from_counts(tuple(counts), need)


def _bump(states: frozenset, ds: int, dp: int, dh: int) -> set:
    out = set()
    for s, p, h in states:
        ns = min(s + ds, 4)
        np_ = min(p + dp, 4)
        nh = min(h + dh, 1)
        if dh and h:
            continue  # 只留一個雀頭
        out.add((ns, np_, nh))
    return out


@lru_cache(maxsize=200_000)
def _shanten_from_counts(counts: tuple[int, ...], need: int) -> int:
    called = 4 - need
    memo: dict[tuple[int, int, int, int], frozenset] = {}
    BASE = frozenset({(0, 0, 0)})

    def at(i: int) -> int:
        return counts[i] if 0 <= i < N_KINDS else 0

    def rec(i: int, c0: int, c1: int, c2: int) -> frozenset:
        if i >= N_KINDS:
            return BASE
        key = (i, c0, c1, c2)
        cached = memo.get(key)
        if cached is not None:
            return cached
        if c0 == 0:
            res = rec(i + 1, c1, c2, at(i + 3))
            memo[key] = res
            return res
        out: set = set()
        if c0 >= 3:
            out |= _bump(rec(i, c0 - 3, c1, c2), 1, 0, 0)
        if c1 > 0 and c2 > 0:
            out |= _bump(rec(i, c0 - 1, c1 - 1, c2 - 1), 1, 0, 0)
        if c0 >= 2:
            sub = rec(i, c0 - 2, c1, c2)
            out |= _bump(sub, 0, 0, 1)
            out |= _bump(sub, 0, 1, 0)
        if c1 > 0:
            out |= _bump(rec(i, c0 - 1, c1 - 1, c2), 0, 1, 0)
        if c2 > 0:
            out |= _bump(rec(i, c0 - 1, c1, c2 - 1), 0, 1, 0)
        out |= rec(i, c0 - 1, c1, c2)  # 孤張捨棄
        res = frozenset(out)
        memo[key] = res
        return res

    best = 8
    for s, p, h in rec(0, at(0), at(1), at(2)):
        total_sets = min(s + called, 4)
        usable = min(p, max(0, 4 - total_sets))
        best = min(best, 8 - 2 * total_sets - usable - h)
    return max(best, 0)


def tiles_to_counts(tiles: Sequence[int]) -> list[int]:
    return counts_of(tiles)
