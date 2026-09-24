"""副露（鳴牌）與手牌內部面子的表示。"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from .tiles import fmt, to_char


class MeldType(str, Enum):
    CHI = "chi"            # 吃：順子，只能吃上家
    PON = "pon"            # 碰
    ANKAN = "ankan"        # 暗槓（不破門前清）
    MINKAN = "minkan"      # 大明槓
    KAKAN = "kakan"        # 加槓（碰 -> 槓）


@dataclass(frozen=True, slots=True)
class Meld:
    type: MeldType
    tiles: tuple[int, ...]       # CHI 為 (s, s+1, s+2)，其餘為同一張重複
    from_seat: int | None = None  # 餵牌者座位；ANKAN 為 None
    called_tile: int | None = None

    @property
    def is_kan(self) -> bool:
        return self.type in (MeldType.ANKAN, MeldType.MINKAN, MeldType.KAKAN)

    @property
    def is_open(self) -> bool:
        """是否破壞門前清。暗槓不破。"""
        return self.type is not MeldType.ANKAN

    @property
    def is_concealed_triplet(self) -> bool:
        """計算暗刻數時是否算作暗刻（暗槓算）。"""
        return self.type is MeldType.ANKAN

    @property
    def base(self) -> int:
        return self.tiles[0]

    def as_block(self) -> Block:
        if self.type is MeldType.CHI:
            return Block("chi", self.base, concealed=False, from_meld=True)
        if self.type is MeldType.PON:
            return Block("pon", self.base, concealed=False, from_meld=True)
        return Block(
            "kan", self.base, concealed=self.type is MeldType.ANKAN, from_meld=True
        )

    def __str__(self) -> str:
        return f"{self.type.value}:{fmt(self.tiles)}"


@dataclass(frozen=True, slots=True)
class Block:
    """和牌拆解後的一個區塊。

    kind: 'pair' | 'chi' | 'pon' | 'kan'
    start: chi 為最小字母，其餘為該字母
    """

    kind: str
    start: int
    concealed: bool = True
    from_meld: bool = False  # 來自副露（含暗槓）而非手牌拆解

    @property
    def tiles(self) -> tuple[int, ...]:
        if self.kind == "chi":
            return (self.start, self.start + 1, self.start + 2)
        n = {"pair": 2, "pon": 3, "kan": 4}[self.kind]
        return (self.start,) * n

    @property
    def is_set(self) -> bool:
        """是否為面子（非雀頭）。"""
        return self.kind != "pair"

    def __str__(self) -> str:
        mark = "" if self.concealed else "*"
        return f"{self.kind}{to_char(self.start)}{mark}"


@dataclass(slots=True)
class Decomposition:
    """一種和牌拆解方式。"""

    pair: int | None                      # 雀頭字母；一條龍型為 None
    blocks: list[Block] = field(default_factory=list)  # 含雀頭與所有面子（含副露）
    form: str = "standard"                # 'standard' | 'chiitoi' | 'dragon'

    @property
    def sets(self) -> list[Block]:
        return [b for b in self.blocks if b.is_set]

    @property
    def sequences(self) -> list[Block]:
        return [b for b in self.blocks if b.kind == "chi"]

    @property
    def triplets(self) -> list[Block]:
        """刻子 + 槓。"""
        return [b for b in self.blocks if b.kind in ("pon", "kan")]

    @property
    def kans(self) -> list[Block]:
        return [b for b in self.blocks if b.kind == "kan"]
