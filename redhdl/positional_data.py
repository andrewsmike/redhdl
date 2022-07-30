"""
Positional data: 3d cell (meta)data manipulations.
"""
from typing import TypeVar

from redhdl.region import Pos, RectangularPrism, Region

BlockData = TypeVar("BlockData")
PositionMask = set[Pos]


class PositionalData(dict[Pos, BlockData]):
    def __or__(self, other):
        if len(self.mask() & other.mask()) != 0:
            raise ValueError("Attempted to union overlapping positional data.")

        return PositionalData(super().__or__(other))

    def shifted(self, shift: Pos) -> "PositionalData[BlockData]":
        return PositionalData((pos + shift, block) for pos, block in self.items())

    def min_pos(self) -> Pos:
        """
        >>> PositionalData({
        ...     Pos(1, 1, 4): None, Pos(1, 0, 2): None, Pos(0, 3, 0): None,
        ... }).min_pos()
        Pos(0, 0, 0)
        """
        return Pos.elem_min(*self.keys())

    def max_pos(self) -> Pos:
        """
        >>> PositionalData({
        ...     Pos(0, 0, 2): None, Pos(1, 1, 1): None, Pos(0, 3, 2): None,
        ... }).max_pos()
        Pos(1, 3, 2)
        """
        return Pos.elem_max(*self.keys())

    def rect_region(self) -> Region:
        return RectangularPrism(
            min_pos=self.min_pos(),
            max_pos=self.max_pos(),
        )

    def shift_normalized(self) -> "PositionalData[BlockData]":
        min_pos = self.min_pos() if len(self) > 0 else Pos(0, 0, 0)
        return PositionalData(self.shifted(-min_pos))

    def masked(self, mask: PositionMask) -> "PositionalData[BlockData]":
        return PositionalData(
            (pos, data) for pos, data in self.items() if pos not in mask
        )

    def mask(self) -> PositionMask:
        return set(self.keys())
