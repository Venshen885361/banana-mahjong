"""全役種判定。

規則來源：banana-majong repo 內的《Banana英文字母麻將規則.docx》。
所有役種（1/2/3/6番、役滿、兩倍役滿、三倍役滿）都已實作。
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

from .hand import winning_decompositions
from .meld import Block, Decomposition, Meld, MeldType
from .tiles import N_KINDS, TERMINALS, VOWELS, E, X, Y, Z, next_tile

TSUMO_MODE_MENZEN = "menzen_tsumo"  # 使用 1番「門前清自摸和」
TSUMO_MODE_PLAIN = "tsumo"          # 使用 2番「自摸」（副露減一番）


@dataclass(slots=True)
class WinContext:
    """和牌當下的全部資訊。"""

    concealed: list[int]              # 26 長度的張數陣列，含和了牌，不含副露
    melds: list[Meld]
    win_tile: int
    is_tsumo: bool

    is_dealer: bool = False
    seat: int = 0

    # 立直系
    riichi: bool = False
    double_riichi: bool = False
    ippatsu: bool = False

    # 特殊和牌狀況
    rinshan: bool = False             # 嶺上開花
    chankan: bool = False             # 搶槓
    haitei: bool = False              # 海底（最後一張自摸）
    houtei: bool = False              # 河底（最後一張榮和）
    kanfuri: bool = False             # 槓振
    tsubame: bool = False             # 燕返
    tenhou: bool = False              # 天和
    chiihou: bool = False             # 地和
    renhou: bool = False              # 人和

    dora_indicators: list[int] = field(default_factory=list)
    ura_indicators: list[int] = field(default_factory=list)
    dora_wrap: bool = True            # Z 的下一張是否環繞回 A

    tsumo_mode: str = TSUMO_MODE_MENZEN

    # ---- 衍生 ----
    @property
    def menzen(self) -> bool:
        return all(not m.is_open for m in self.melds)

    @property
    def all_tiles(self) -> list[int]:
        c = list(self.concealed)
        for m in self.melds:
            for t in m.tiles:
                c[t] += 1
        return c

    def dora_tiles(self, include_ura: bool) -> set[int]:
        out: set[int] = set()
        for ind in self.dora_indicators:
            nxt = next_tile(ind, self.dora_wrap)
            if nxt is not None:
                out.add(nxt)
        if include_ura:
            for ind in self.ura_indicators:
                nxt = next_tile(ind, self.dora_wrap)
                if nxt is not None:
                    out.add(nxt)
        return out


@dataclass(slots=True)
class YakuResult:
    yaku: list[tuple[str, int]] = field(default_factory=list)       # (名稱, 番)
    yakuman: list[tuple[str, int]] = field(default_factory=list)    # (名稱, 倍數)
    han: int = 0
    multiplier: int = 0        # 役滿倍數；0 表示非役滿
    decomposition: Decomposition | None = None

    @property
    def has_yaku(self) -> bool:
        """是否有役（寶牌不算役）。"""
        if self.multiplier:
            return True
        return any(n not in ("寶牌", "裡寶牌") for n, _ in self.yaku)


# --------------------------------------------------------------------------


def _seq_starts(blocks: Sequence[Block]) -> list[int]:
    return sorted(b.start for b in blocks if b.kind == "chi")


def _is_ryanmen(seq_start: int, win_tile: int) -> bool:
    """順子由兩面聽完成？XYZ 用 X 和牌等同邊張，不算。"""
    if win_tile == seq_start:            # 由 (s+1, s+2) 等到 s，另一邊是 s+3
        return seq_start + 3 <= N_KINDS - 1
    if win_tile == seq_start + 2:        # 由 (s, s+1) 等到 s+2，另一邊是 s-1
        return seq_start - 1 >= 0
    return False


def _kyuuren_base(counts: Sequence[int]) -> int | None:
    """回傳九蓮寶燈的起始字母，不符合則 None。"""
    if sum(counts) != 14:
        return None
    idx = [i for i, c in enumerate(counts) if c]
    lo, hi = idx[0], idx[-1]
    if hi - lo != 8:
        return None
    base = [3] + [1] * 7 + [3]
    extra = [counts[lo + k] - base[k] for k in range(9)]
    if any(e < 0 for e in extra) or sum(extra) != 1:
        return None
    return lo


# --------------------------------------------------------------------------


def _eval_shape(ctx: WinContext, decomp: Decomposition, win_block: Block | None) -> YakuResult:
    res = YakuResult(decomposition=decomp)
    menzen = ctx.menzen
    open_hand = not menzen
    red = 1 if open_hand else 0  # 副露減一番

    all_counts = ctx.all_tiles
    n_tiles = sum(all_counts)

    # ================= 役滿 =================
    ym: list[tuple[str, int]] = []

    # --- 與牌型無關的役滿 ---
    if ctx.tenhou:
        ym.append(("天和", 1))
    if ctx.chiihou:
        ym.append(("地和", 1))
    if ctx.renhou:
        ym.append(("人和", 1))
    if ctx.double_riichi and (ctx.haitei or ctx.houtei):
        ym.append(("石上三年", 1))
    dora_set_all = ctx.dora_tiles(include_ura=ctx.riichi)
    if dora_set_all and all(
        (i in dora_set_all) for i, c in enumerate(all_counts) if c
    ):
        ym.append(("寶一色", 1))

    # --- Rush E：14 張 E ---
    rush_e = all_counts[E] >= 14 and n_tiles == all_counts[E]
    if rush_e:
        ym.append(("Rush E", 3 - (1 if open_hand else 0)))

    if decomp.form == "dragon":
        ym.append(("一條龍", 2))
        res.yakuman = ym
        res.multiplier = sum(m for _, m in ym)
        return res

    trips = decomp.triplets
    kans = decomp.kans
    seqs = _seq_starts(decomp.blocks)

    # 暗刻數：榮和完成的刻子視為明刻
    def concealed_trip_count() -> int:
        n = 0
        for b in trips:
            if not b.concealed:
                continue
            if (
                not ctx.is_tsumo
                and win_block is not None
                and b is win_block
                and b.kind == "pon"
            ):
                continue
            n += 1
        return n

    n_ankou = concealed_trip_count()
    tanki = win_block is not None and win_block.kind == "pair"

    if not rush_e:
        if n_ankou == 4 and menzen:
            if tanki:
                ym.append(("四暗刻單騎", 2))
            else:
                ym.append(("四暗刻", 1))
    if len(kans) == 4:
        ym.append(("四槓子", 1))
    if len(kans) >= 3:
        kan_tiles = [b.start for b in kans]
        for t in set(kan_tiles):
            if kan_tiles.count(t) >= 3:
                ym.append(("三同槓", 1))
                break
    if len(seqs) == 4 and len(set(seqs)) == 1:
        ym.append(("四同順", 1))
    if menzen and decomp.form == "standard":
        base = _kyuuren_base(ctx.concealed) if not ctx.melds else None
        if base is not None:
            pure = list(ctx.concealed)
            pure[ctx.win_tile] -= 1
            expect = [3] + [1] * 7 + [3]
            if all(pure[base + k] == expect[k] for k in range(9)) and sum(pure) == 13:
                ym.append(("純正九蓮寶燈", 2))
            else:
                ym.append(("九蓮寶燈", 1))
    if len(seqs) == 4:
        s0 = seqs[0]
        if seqs == [s0, s0 + 3, s0 + 6, s0 + 9] and not any(
            n == "一條龍" for n, _ in ym
        ):
            ym.append(("六六大順", 1))

    if ym:
        res.yakuman = ym
        res.multiplier = sum(m for _, m in ym)
        return res

    # ================= 一般役 =================
    y: list[tuple[str, int]] = []

    # ---- 1番 ----
    if ctx.riichi and not ctx.double_riichi and menzen:
        y.append(("立直", 1))
    if ctx.double_riichi and menzen:
        y.append(("兩立直", 2))
    if ctx.ippatsu and (ctx.riichi or ctx.double_riichi):
        y.append(("一發", 1))
    if ctx.is_tsumo:
        if ctx.tsumo_mode == TSUMO_MODE_MENZEN:
            if menzen:
                y.append(("門前清自摸和", 1))
        else:
            y.append(("自摸", 2 - red))
    if ctx.chankan:
        y.append(("搶槓", 1))
    if ctx.rinshan:
        y.append(("嶺上開花", 1))
    if ctx.kanfuri:
        y.append(("槓振", 1))
    if ctx.tsubame:
        y.append(("燕返", 1))
    if ctx.haitei and ctx.is_tsumo:
        y.append(("海底摸月", 1))
    if ctx.houtei and not ctx.is_tsumo:
        y.append(("河底撈魚", 1))

    n_open_melds = sum(1 for m in ctx.melds if m.is_open)
    n_ankan = sum(1 for m in ctx.melds if m.type is MeldType.ANKAN)
    if n_open_melds == 4 and n_ankan == 0:
        y.append(("十二落抬", 1))

    is_chiitoi = decomp.form == "chiitoi"

    # 平和
    if (
        menzen
        and not is_chiitoi
        and len(seqs) == 4
        and win_block is not None
        and win_block.kind == "chi"
        and _is_ryanmen(win_block.start, ctx.win_tile)
    ):
        y.append(("平和", 1))

    # 一盃口 / 二盃口
    if menzen and not is_chiitoi:
        dupes = sum(seqs.count(s) // 2 for s in set(seqs))
        if dupes >= 2:
            y.append(("二盃口", 3))
        elif dupes == 1:
            y.append(("一盃口", 1))
    else:
        dupes = 0

    # 尾順 / 尾刻（可疊加）
    n_tail_seq = seqs.count(X)          # XYZ
    if n_tail_seq:
        y.append(("尾順", n_tail_seq))
    n_tail_trip = sum(1 for b in trips if b.start in (X, Y, Z))
    if n_tail_trip:
        y.append(("尾刻", n_tail_trip))

    # ---- 2番 ----
    if is_chiitoi and dupes < 2:
        y.append(("七對子", 2))
    if all(all_counts[v] == 0 for v in VOWELS):
        y.append(("斷母音", 2))
    if not is_chiitoi:
        if len(trips) == 4:
            y.append(("對對和", 2))
        if n_ankou == 3:
            y.append(("三暗刻", 2))
        trip_tiles = sorted(b.start for b in trips)
        if _has_consecutive(trip_tiles, 4):
            y.append(("四連刻", 6 - red))
        elif _has_consecutive(trip_tiles, 3):
            y.append(("三連刻", 2 - red))

        # ---- 3番 ----
        if _has_ittsu(seqs):
            y.append(("一氣通貫", 3 - red))
        for s in set(seqs):
            if seqs.count(s) >= 3:
                y.append(("三同順", 3 - red))
                break
        if len(kans) == 3:
            y.append(("三槓子", 3 - red))
        kan_tiles = [b.start for b in kans]
        if any(kan_tiles.count(t) >= 2 for t in set(kan_tiles)):
            y.append(("二同槓", 3))

        # ---- 6番 ----
        if all(c == 0 or i in VOWELS for i, c in enumerate(all_counts)):
            y.append(("母一色", 6 - red))
        if _all_terminal_blocks(decomp):
            y.append(("全帶AZ", 6 - red))

    # ---- 寶牌 ----
    dora_set = ctx.dora_tiles(include_ura=False)
    n_dora = sum(all_counts[t] for t in dora_set)
    if n_dora:
        y.append(("寶牌", n_dora))
    if ctx.riichi or ctx.double_riichi:
        ura_set: set[int] = set()
        for ind in ctx.ura_indicators:
            nxt = next_tile(ind, ctx.dora_wrap)
            if nxt is not None:
                ura_set.add(nxt)
        n_ura = sum(all_counts[t] for t in ura_set)
        if n_ura:
            y.append(("裡寶牌", n_ura))

    res.yaku = y
    res.han = sum(h for _, h in y)
    return res


def _has_consecutive(trip_tiles: Sequence[int], n: int) -> bool:
    s = set(trip_tiles)
    return any(all((t + k) in s for k in range(n)) for t in s)


def _has_ittsu(seqs: Sequence[int]) -> bool:
    """連續且不重疊的三個順子：s, s+3, s+6。"""
    s = list(seqs)
    for start in set(s):
        need = [start, start + 3, start + 6]
        pool = list(s)
        ok = True
        for x in need:
            if x in pool:
                pool.remove(x)
            else:
                ok = False
                break
        if ok:
            return True
    return False


def _all_terminal_blocks(decomp: Decomposition) -> bool:
    """每一組面子與雀頭都含 A 或 Z。"""
    if decomp.form != "standard":
        return False
    for b in decomp.blocks:
        if b.kind == "chi":
            if not (set(b.tiles) & TERMINALS):
                return False
        else:
            if b.start not in TERMINALS:
                return False
    return True


# --------------------------------------------------------------------------


def evaluate(ctx: WinContext, score_fn=None) -> YakuResult | None:
    """列舉所有拆解與和了牌歸屬，取分數最高者。沒有和牌型則 None。"""
    decomps = winning_decompositions(ctx.concealed, ctx.melds)
    if not decomps:
        return None

    best: YakuResult | None = None
    best_key = (-1, -1)
    for d in decomps:
        candidates: list[Block | None]
        if d.form == "dragon":
            candidates = [None]
        else:
            hand_blocks = [b for b in d.blocks if not b.from_meld]
            candidates = [b for b in hand_blocks if ctx.win_tile in b.tiles] or [None]
        for wb in candidates:
            r = _eval_shape(ctx, d, wb)
            if not r.has_yaku:
                continue
            key = (r.multiplier, r.han)
            if key > best_key:
                best_key = key
                best = r
    return best


def can_win(ctx: WinContext) -> bool:
    """役滿/番縛檢查後是否真的能和（一番縛）。"""
    r = evaluate(ctx)
    return r is not None and r.has_yaku and (r.multiplier > 0 or r.han >= 1)
