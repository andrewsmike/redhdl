"""
Positional data: 3d cell (meta)data manipulations.
"""
from dataclasses import dataclass
from typing import Iterator, TypeVar

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


@dataclass(frozen=True)
class PositionSequence:
    """
    Linear 3d sequence of positions.
    Defined by start (inclusive), stop (inclusive), and either an offset
    step Position, or a (total) target number of Positions to linearly space between
    the start/stop.

    >>> list(PositionSequence(Pos(0, 0, 0), Pos(2, 2, 0), count=3))
    [Pos(0, 0, 0), Pos(1, 1, 0), Pos(2, 2, 0)]

    >>> list(PositionSequence(Pos(-1, -1, 1), Pos(-5, -5, -3), count=3))
    [Pos(-1, -1, 1), Pos(-3, -3, -1), Pos(-5, -5, -3)]


    Start, step, and stop must _cleanly_ align into each other:
    >>> PositionSequence(Pos(0, 0, 0), Pos(3, 2, 1), count=3)
    Traceback (most recent call last):
      ...
    ValueError: Position Pos(3, 2, 1) doesn't divide cleanly by Pos(2, 2, 2).
    """

    start: Pos
    stop: Pos
    count: int

    def __post_init__(self):
        axis_step_counts = (self.stop - self.start) / self.step

        x_step_count = axis_step_counts[0]
        if not all(
            (step_count == 0) or (step_count == x_step_count)
            for step_count in axis_step_counts
        ):
            raise ValueError(
                f"Step {self.step} doesn't cleanly divide {self.start} => {self.stop}."
            )

    @property
    def step(self) -> Pos:
        return (self.stop - self.start) / (self.count - 1)

    def values(self) -> list[Pos]:
        return list(self)

    def __iter__(self) -> Iterator[Pos]:
        for i in range(self.count):
            yield self.start + (self.step * i)

    def __len__(self) -> int:
        return self.count

    def __str__(self) -> str:
        return f"PositionSequence({self.start}, {self.stop}, count={self.count})"

    def __repr__(self) -> str:
        return f"PositionSequence({self.start}, {self.stop}, count={self.count})"
