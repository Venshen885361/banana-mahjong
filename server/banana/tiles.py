"""Tile primitives for Banana 英文字母麻將.

牌 = 字母 A..Z，內部一律用 index 0..25。
順子 = 連續三個字母（ABC .. XYZ，不環繞）。
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence

N_KINDS = 26

# 各字母張數，索引 0..25 對應 A..Z（來自 banana-majong/main.cpp 的 card_amount）
TILE_COUNTS: tuple[int, ...] = (
    13, 3, 3, 6, 18, 3, 4, 3, 12, 2, 2, 5, 3,
    8, 11, 3, 2, 9, 6, 9, 6, 3, 3, 2, 3, 2,
)
TOTAL_TILES = sum(TILE_COUNTS)  # 144

A, E, I, O, U = 0, 4, 8, 14, 20  # noqa: E741 —— 這些是牌名常數
X, Y, Z = 23, 24, 25
VOWELS: frozenset[int] = frozenset({A, E, I, O, U})  # 母音（斷母音 / 母一色用）
TERMINALS: frozenset[int] = frozenset({A, Z})  # 全帶 AZ 用


def to_index(ch: str) -> int:
    idx = ord(ch.upper()) - 65
    if not 0 <= idx < N_KINDS:
        raise ValueError(f"not a tile: {ch!r}")
    return idx


def to_char(idx: int) -> str:
    return chr(65 + idx)


def parse(text: str) -> list[int]:
    """'ABCIII' -> [0, 1, 2, 8, 8, 8]；忽略空白與底線。"""
    return [to_index(c) for c in text if c not in " \t\n_-"]


def fmt(tiles: Iterable[int]) -> str:
    return "".join(to_char(t) for t in tiles)


def counts_of(tiles: Iterable[int]) -> list[int]:
    c = [0] * N_KINDS
    for t in tiles:
        c[t] += 1
    return c


def counts_to_tiles(counts: Sequence[int]) -> list[int]:
    out: list[int] = []
    for i, n in enumerate(counts):
        out.extend([i] * n)
    return out


def next_tile(idx: int, wrap: bool = True) -> int | None:
    """寶牌指示牌的「下一張」。Z 的下一張規則書未定義，預設環繞回 A。"""
    if idx < N_KINDS - 1:
        return idx + 1
    return A if wrap else None


def full_wall() -> list[int]:
    wall: list[int] = []
    for i, n in enumerate(TILE_COUNTS):
        wall.extend([i] * n)
    return wall
