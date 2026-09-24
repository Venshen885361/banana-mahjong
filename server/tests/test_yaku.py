"""以規則書《Banana英文字母麻將規則.docx》的牌型舉例為準做回歸測試。"""

from __future__ import annotations

import pytest

from banana.hand import is_tenpai, is_winning, waits
from banana.meld import Meld, MeldType
from banana.tiles import counts_of, parse, to_index
from banana.yaku import TSUMO_MODE_PLAIN, WinContext, evaluate


def ctx(hand: str, win: str, **kw) -> WinContext:
    """hand 含和了牌（14 張或扣除副露後的張數）。"""
    melds = kw.pop("melds", [])
    return WinContext(
        concealed=counts_of(parse(hand)),
        melds=list(melds),
        win_tile=to_index(win),
        is_tsumo=kw.pop("is_tsumo", True),
        **kw,
    )


def names(hand: str, win: str, **kw) -> dict[str, int]:
    r = evaluate(ctx(hand, win, **kw))
    assert r is not None, f"{hand} 不是和牌型"
    if r.multiplier:
        return {n: m for n, m in r.yakuman}
    return {n: h for n, h in r.yaku}


# ---------------------------------------------------------------- 基本和牌型
def test_basic_win_shapes():
    assert is_winning(counts_of(parse("ABCIIIMNOUVWYY")))
    assert is_winning(counts_of(parse("AACCHHJJNNSSVV")))       # 七對子
    assert is_winning(counts_of(parse("BCDEFGHIJKLMNO")))       # 一條龍
    assert not is_winning(counts_of(parse("ABCIIIMNOUVWYZ")))


def test_waits_and_tenpai():
    # ABC IJK MNO UVW + YY 聽 Y 單騎
    assert waits(counts_of(parse("ABCIJKMNOUVWY"))) == [to_index("Y")]
    assert is_tenpai(counts_of(parse("ABCIJKMNOUVYY")))


def test_kan_hand_size():
    melds = [Meld(MeldType.ANKAN, (to_index("I"),) * 4)]
    assert is_winning(counts_of(parse("ABCJKLMNOUU")), melds)


# ---------------------------------------------------------------- 一番
def test_menzen_tsumo():
    y = names("ABCIIIMNOUVWYY", "O")
    assert y["門前清自摸和"] == 1


def test_pinfu():
    y = names("ABCIJKMNOUVWYY", "W")
    assert y["平和"] == 1


def test_pinfu_rejects_penchan_tail():
    # XYZ 由 X 和牌 == 邊張，不成立平和
    y = names("ABCIJKMNOXYZYY", "X")
    assert "平和" not in y


def test_iipeiko():
    y = names("ABCABCEFGIIIOO", "O")
    assert y["一盃口"] == 1


def test_tail_sequence_and_triplet():
    y = names("ABCEEIJKNNNXYZ", "E")
    assert y["尾順"] == 1
    y2 = names("ABCMMTUVYYYZZZ", "M")
    assert y2["尾刻"] == 2


def test_juuni_ochi():
    melds = [
        Meld(MeldType.CHI, (0, 1, 2), from_seat=1),
        Meld(MeldType.PON, (8, 8, 8), from_seat=1),
        Meld(MeldType.CHI, (11, 12, 13), from_seat=1),
        Meld(MeldType.CHI, (20, 21, 22), from_seat=1),
    ]
    y = names("YY", "Y", melds=melds)
    assert y["十二落抬"] == 1


# ---------------------------------------------------------------- 二番
def test_chiitoi():
    y = names("AACCHHJJNNSSVV", "V")
    assert y["七對子"] == 2


def test_tanboin():
    y = names("BBBFGHLMNRSTVV", "V")
    assert y["斷母音"] == 2


def test_toitoi_and_sanankou():
    # 碰了 AAA 才不會變成四暗刻
    melds = [Meld(MeldType.PON, (0, 0, 0), from_seat=1)]
    y = names("DDDGGGJJJNN", "N", melds=melds)
    assert y["對對和"] == 2
    assert y["三暗刻"] == 2


def test_sanrenkou():
    y = names("ABCFFFGGGHHHZZ", "Z")
    assert y["三連刻"] == 2


def test_plain_tsumo_mode():
    y = names("ABCIIIMNOUVWYY", "O", tsumo_mode=TSUMO_MODE_PLAIN)
    assert y["自摸"] == 2
    melds = [Meld(MeldType.CHI, (0, 1, 2), from_seat=1)]
    y2 = names("IIIMNOUVWYY", "O", melds=melds, tsumo_mode=TSUMO_MODE_PLAIN)
    assert y2["自摸"] == 1  # 副露減一番


# ---------------------------------------------------------------- 三番
def test_ryanpeiko():
    y = names("ABCABCEFGEFGII", "I")
    assert y["二盃口"] == 3
    assert "七對子" not in y


def test_ittsu():
    y = names("BCDEFGHIJSSSTT", "T")
    assert y["一氣通貫"] == 3


def test_sandoujun():
    # FGH x3 一定也能讀成 FFF/GGG/HHH，所以直接驗證順子拆解那一支
    from banana.hand import winning_decompositions
    from banana.yaku import _eval_shape

    w = ctx("ABCFGHFGHFGHZZ", "Z")
    seen = False
    for d in winning_decompositions(w.concealed, []):
        if len(d.sequences) == 4:
            r = _eval_shape(w, d, d.blocks[0])
            assert dict(r.yaku)["三同順"] == 3
            seen = True
    assert seen


def test_sandoujun_vs_sanrenkou_no_stack():
    r = evaluate(ctx("ABCFGHFGHFGHZZ", "Z"))
    assert r is not None and r.han == 5
    got = {n for n, _ in r.yaku}
    assert not ("三同順" in got and "三連刻" in got)


def test_sankantsu():
    melds = [
        Meld(MeldType.ANKAN, (8,) * 4),
        Meld(MeldType.ANKAN, (13,) * 4),
        Meld(MeldType.ANKAN, (14,) * 4),
    ]
    y = names("ABCFF", "F", melds=melds)
    assert y["三槓子"] == 3


def test_nidoukan():
    melds = [Meld(MeldType.ANKAN, (8,) * 4), Meld(MeldType.ANKAN, (8,) * 4)]
    y = names("ABCDEFGG", "G", melds=melds)
    assert y["二同槓"] == 3


# ---------------------------------------------------------------- 六番
def test_boin_isshoku():
    # 榮和 E 讓其中一組 EEE 變明刻，否則會直接變四暗刻單騎
    y = names("AAAEEEEEEOOOUU", "E", is_tsumo=False)
    assert y["母一色"] == 6
    assert y["對對和"] == 2


def test_shirenkou():
    y = names("EEEFFFGGGHHHZZ", "E", is_tsumo=False)
    assert y["四連刻"] == 6


def test_zentai_az():
    y = names("AAAABCABCXYZZZ", "A", is_tsumo=False)
    assert y["全帶AZ"] == 6


# ---------------------------------------------------------------- 役滿
def test_suuankou():
    y = names("AAADDDGGGJJJNN", "J")
    assert y["四暗刻"] == 1


def test_suuankou_tanki():
    y = names("AAADDDGGGJJJNN", "N")
    assert y["四暗刻單騎"] == 2
    assert "四暗刻" not in y


def test_suukantsu():
    melds = [Meld(MeldType.ANKAN, (t,) * 4) for t in (0, 4, 8, 13)]
    y = names("ZZ", "Z", melds=melds)
    assert y["四槓子"] == 1


def test_sandoukan():
    melds = [Meld(MeldType.ANKAN, (8,) * 4) for _ in range(3)]
    y = names("ABCGG", "G", melds=melds)
    assert y["三同槓"] == 1


def test_yondoujun():
    y = names("FGHFGHFGHFGHZZ", "Z")
    assert y["四同順"] == 1


def test_kyuuren():
    y = names("HHHHIJKLMNOPPP", "P")
    assert y["九蓮寶燈"] == 1


def test_junsei_kyuuren():
    y = names("HHHIJKLLMNOPPP", "L")
    assert y["純正九蓮寶燈"] == 2
    assert "九蓮寶燈" not in y


def test_rokuroku():
    y = names("BCDEFGHIJKLMTT", "T")
    assert y["六六大順"] == 1


def test_ichijouryuu():
    y = names("BCDEFGHIJKLMNO", "O")
    assert y["一條龍"] == 2


def test_rush_e():
    y = names("E" * 14, "E")
    assert y["Rush E"] == 3
    assert "四暗刻" not in y and "四暗刻單騎" not in y


def test_tenhou():
    y = names("ABCIIIMNOUVWYY", "O", tenhou=True, is_dealer=True)
    assert y["天和"] == 1


def test_dora_isshoku():
    # 指示牌 A, B -> 寶牌 B, C；手牌全是 B/C
    y = names("BBBCCCBBBCCCBB", "B", dora_indicators=[0, 1])
    assert "寶一色" in y


# ---------------------------------------------------------------- 寶牌
def test_dora_counting():
    y = names("ABCABCEFGIIIOO", "O", dora_indicators=[to_index("H")])  # H -> I
    assert y["寶牌"] == 3


def test_ura_only_with_riichi():
    y = names("ABCIJKMNOUVWYY", "W", riichi=True, ura_indicators=[to_index("V")])
    assert y["裡寶牌"] == 1
    y2 = names("ABCIJKMNOUVWYY", "W", ura_indicators=[to_index("V")])
    assert "裡寶牌" not in y2


# ---------------------------------------------------------------- 無役
def test_no_yaku_open_hand():
    melds = [Meld(MeldType.CHI, (0, 1, 2), from_seat=1)]
    r = evaluate(ctx("IJKMNOUVWYY", "W", is_tsumo=False, melds=melds))
    assert r is None


@pytest.mark.parametrize("bad", ["ABCIIIMNOUVWYZ", "AABBCCDDEEFFGH"])
def test_not_a_win(bad):
    assert not is_winning(counts_of(parse(bad)))


# ---------------------------------------------------------------- 自訂特殊役
def test_banana():
    # AAA BBB NNN + IJK + ZZ
    y = names("AAABBBNNNIJKZZ", "Z")
    assert y["BANANA"] == 1


def test_banana_open():
    melds = [Meld(MeldType.PON, (1, 1, 1), from_seat=1)]   # 碰 BBB
    y = names("AAANNNIJKZZ", "Z", melds=melds)
    assert y["BANANA"] == 1


def test_rush_a():
    # 把牌山全部 13 張 A 收齊 + 任意 1 張
    y = names("A" * 13 + "Z", "Z")
    assert y["Rush A"] == 3


def test_rush_a_open():
    melds = [Meld(MeldType.PON, (0, 0, 0), from_seat=1)]
    y = names("A" * 10 + "Z", "Z", melds=melds)
    assert y["Rush A"] == 2      # 副露減一倍


def test_rush_a_needs_all_thirteen():
    r = evaluate(ctx("A" * 12 + "ZZ", "Z"))
    assert r is None or "Rush A" not in dict(r.yakuman)


def test_seven_consecutive_pairs():
    y = names("HHIIJJKKLLMMNN", "N")
    assert y["七連對"] == 2
    assert "七對子" not in y


def test_chiitoi_not_consecutive():
    y = names("AACCHHJJNNSSVV", "V")
    assert "七連對" not in y


def test_quiz():
    y = names("AAEEIIOOQQUUZZ", "Z")
    assert y["QUIZ"] == 2


def test_quiz_standard_shape():
    # QQ 當雀頭，XYZ 兩組吃掉兩張 Z，UU/II 用刻子湊
    y = names("QQUUUIIIXYZXYZ", "Q")
    assert y["QUIZ"] == 2


def test_rush_e_with_kan():
    melds = [Meld(MeldType.ANKAN, (4,) * 4)]
    y = names("E" * 10, "E", melds=melds)
    assert y["Rush E"] == 3
