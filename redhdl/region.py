"""
Simple 3d region representation and manipulation library.

Region types:
- Rectangular prisms
- Composite regions
- TODO: Efficient diagonal polyhedra for diagonal circuits.


>>> from pprint import pprint
>>> from redhdl.region import CompositeRegion, RectangularPrism

>>> example = RectangularPrism(Pos(0, 0, 0), Pos(2, 3, 4))
>>> continuing_with_overlap = RectangularPrism(Pos(2, 3, 4), Pos(3, 4, 5))

>>> example & continuing_with_overlap
RectangularPrism(Pos(2, 3, 4), Pos(2, 3, 4))

>>> example.intersects(continuing_with_overlap)
True

>>> just_beyond = RectangularPrism(Pos(3, 4, 5), Pos(8, 8, 8))

>>> example.intersects(just_beyond)
False
>>> just_beyond.intersects(continuing_with_overlap)
True

>>> example.intersects(RectangularPrism(Pos(-2, -2, -2), Pos(-1, -1, -1)))
False
>>> example.intersects(RectangularPrism(Pos(-1, -1, -1), Pos(8, 8, 8)))
True


>>> composite_w_big_boi = CompositeRegion(subregions=(
...     RectangularPrism(Pos(0, 0, 0), Pos(2, 3, 4)),
...     RectangularPrism(Pos(-1, -1, -1), Pos(8, 8, 8)),
... ))

>>> composite_just_beyond = CompositeRegion(subregions=(
...     RectangularPrism(Pos(3, 4, 5), Pos(8, 8, 8)),
...     RectangularPrism(Pos(-2, -2, -2), Pos(-1, -1, -1)),
... ))

>>> pprint(composite_w_big_boi & composite_just_beyond)
CompositeRegion(subregions=(RectangularPrism(Pos(3, 4, 5), Pos(8, 8, 8)),
                            RectangularPrism(Pos(-1, -1, -1), Pos(-1, -1, -1))))

>>> composite_example = CompositeRegion((RectangularPrism(Pos(0, 0, 0), Pos(2, 3, 4)),))
>>> composite_example.intersects(just_beyond)
False
>>> example.intersects(composite_just_beyond)
False
>>> composite_w_big_boi.intersects(composite_just_beyond)
True
>>> composite_w_big_boi.intersects(just_beyond)
True
"""

from dataclasses import dataclass
from functools import cache
from typing import Any, Iterator, Literal, NamedTuple, cast

from redhdl.slice import Slice

Axis = Literal[0, 1, 2]


X_AXIS, Y_AXIS, Z_AXIS = axes = cast(list[Axis], [0, 1, 2])


# Direction: Axis, is_positive
Direction = tuple[Axis, bool]


# Ordered by right-hand-rule rotations on the y axis.
xz_directions = [
    (0, True),
    (2, True),
    (0, False),
    (2, False),
]

direction_name: dict[Direction, str] = {
    (0, True): "east",
    (2, True): "south",
    (0, False): "west",
    (2, False): "north",
    (1, True): "up",
    (1, False): "down",
}

direction_by_name = {name: direction for direction, name in direction_name.items()}


def xz_direction_y_rotated(direction: Direction, quarter_turns: int = 1) -> Direction:
    return cast(
        Direction,
        {
            (0, True): (2, True),
            (2, True): (0, False),
            (0, False): (2, False),
            (2, False): (0, True),
        }[direction],
    )


class Pos(NamedTuple):
    x: int
    y: int
    z: int

    def __add__(self, other) -> "Pos":
        return Pos(
            self.x + other.x,
            self.y + other.y,
            self.z + other.z,
        )

    def __sub__(self, other) -> "Pos":
        return Pos(
            self.x - other.x,
            self.y - other.y,
            self.z - other.z,
        )

    def __neg__(self) -> "Pos":
        return Pos(-self.x, -self.y, -self.z)

    def __abs__(self) -> "Pos":
        return Pos(abs(self.x), abs(self.y), abs(self.z))

    def __mul__(self, value) -> "Pos":
        """
        TODO: Factor vector-or-scalar operations into a common pattern.

        >>> Pos(2, 3, 4) * Pos(1, 2, -1)
        Pos(2, 6, -4)

        >>> Pos(2, -3, 4) * -2
        Pos(-4, 6, -8)
        """
        if isinstance(value, int):
            right = Pos(value, value, value)
        else:
            right = value

        return Pos(
            self.x * right.x,
            self.y * right.y,
            self.z * right.z,
        )

    def __truediv__(self, value) -> "Pos":
        """
        >>> Pos(2, 3, 4) / Pos(2, -1, 2)
        Pos(1, -3, 2)

        >>> Pos(2, 3, 4) / -1
        Pos(-2, -3, -4)

        Note: For block stacking logic, we treat 0/0 as 0.
        >>> Pos(2, 2, 0) / Pos(1, 1, 0)
        Pos(2, 2, 0)

        >>> Pos(2, 3, 3) / Pos(2, -1, 2)
        Traceback (most recent call last):
          ...
        ValueError: Position Pos(2, 3, 3) doesn't divide cleanly by Pos(2, -1, 2).
        """
        if isinstance(value, int):
            divisor = Pos(value, value, value)
        else:
            divisor = value

        assert isinstance(divisor, Pos)

        if not all((a == b == 0) or ((a % b) == 0) for a, b in zip(self, divisor)):
            raise ValueError(f"Position {self} doesn't divide cleanly by {divisor}.")

        return Pos(
            0 if self.x == divisor.x == 0 else self.x // divisor.x,
            0 if self.y == divisor.y == 0 else self.y // divisor.y,
            0 if self.z == divisor.z == 0 else self.z // divisor.z,
        )

    def __mod__(self, value) -> "Pos":
        """
        >>> (Pos(2, 4, -6) % 2).is_zero()
        True

        >>> Pos(2, 3, 4) % Pos(2, -1, 2)
        Pos(0, 0, 0)

        >>> Pos(3, 0, 3) % Pos(2, -1, 2)
        Pos(1, 0, 1)

        Note: For block stacking logic, we treat 0 % 0 as 0.
        >>> Pos(2, 2, 0) % Pos(1, 1, 0)
        Pos(0, 0, 0)
        """
        if isinstance(value, int):
            base = Pos(value, value, value)
        else:
            base = value

        assert isinstance(base, Pos)

        return Pos(
            0 if (self.x == base.x == 0) else self.x % base.x,
            0 if (self.y == base.y == 0) else self.y % base.y,
            0 if (self.z == base.z == 0) else self.z % base.z,
        )

    @classmethod
    def elem_min(cls, *points: "Pos") -> "Pos":
        xs, ys, zs = zip(*points)
        return cls(min(xs), min(ys), min(zs))

    @classmethod
    def elem_max(cls, *points: "Pos") -> "Pos":
        xs, ys, zs = zip(*points)
        return cls(max(xs), max(ys), max(zs))

    def y_rotated(self, quarter_turns: int) -> "Pos":
        x, y, z = self
        return Pos(
            *[
                [x, y, z],
                [-z, y, x],
                [-x, y, -z],
                [z, y, -x],
            ][quarter_turns % 4]
        )

    def is_zero(self) -> bool:
        return self == Pos(0, 0, 0)

    def __ge__(self, other) -> bool:
        return all(left >= right for left, right in zip(self, other))

    def __gt__(self, other) -> bool:
        return all(left > right for left, right in zip(self, other))

    def __le__(self, other) -> bool:
        return all(left <= right for left, right in zip(self, other))

    def __lt__(self, other) -> bool:
        return all(left < right for left, right in zip(self, other))

    def __str__(self: "Pos") -> str:
        return f"Pos({self.x}, {self.y}, {self.z})"

    def __repr__(self: "Pos") -> str:
        return str(self)


direction_unit_pos = {
    (0, False): Pos(-1, 0, 0),
    (1, False): Pos(0, -1, 0),
    (2, False): Pos(0, 0, -1),
    (0, True): Pos(1, 0, 0),
    (1, True): Pos(0, 1, 0),
    (2, True): Pos(0, 0, 1),
}


def opposite_direction(direction: Direction) -> Direction:
    axis, is_pos = direction
    return (axis, not is_pos)


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

    def y_rotated(self, quarter_turns: int) -> "PositionSequence":
        """
        >>> list(PositionSequence(Pos(1, 2, 3), Pos(2, 3, 4), count=2).y_rotated(1))
        [Pos(-3, 2, 1), Pos(-4, 3, 2)]
        """
        return PositionSequence(
            start=self.start.y_rotated(quarter_turns),
            stop=self.stop.y_rotated(quarter_turns),
            count=self.count,
        )

    def __add__(self, other) -> "PositionSequence":
        if not isinstance(other, Pos):
            raise TypeError(f"Expected Pos, found {type(other)}")

        return PositionSequence(
            start=self.start + other,
            stop=self.stop + other,
            count=self.count,
        )

    def __sub__(self, other) -> "PositionSequence":
        if not isinstance(other, Pos):
            raise TypeError(f"Expected Pos, found {type(other)}")

        return PositionSequence(
            start=self.start - other,
            stop=self.stop - other,
            count=self.count,
        )

    def __neg__(self, other) -> "PositionSequence":
        if not isinstance(other, Pos):
            raise TypeError(f"Expected Pos, found {type(other)}")

        return PositionSequence(
            start=-self.start,
            stop=-self.stop,
            count=self.count,
        )

    def __and__(self, other) -> "PositionSequence":
        """
        Subselect a sequence using a Slice().
        """
        if not isinstance(other, Slice):
            raise TypeError(
                f"PositionSequence.__and__ expected Slice, got {type(other)}."
            )

        assert isinstance(other, Slice)

        desired_indices = list(other.values())

        positions = self.values()

        return PositionSequence(
            start=positions[desired_indices[0]],
            stop=positions[desired_indices[-1]],
            count=len(desired_indices),
        )

    def __iter__(self) -> Iterator[Pos]:
        for i in range(self.count):
            yield self.start + (self.step * i)

    def __len__(self) -> int:
        return self.count

    def __str__(self) -> str:
        return f"PositionSequence({self.start}, {self.stop}, count={self.count})"

    def __repr__(self) -> str:
        return f"PositionSequence({self.start}, {self.stop}, count={self.count})"


class Region:
    min_pos: Pos
    max_pos: Pos

    def xz_padded(self, padding_blocks: int = 1) -> "Region":
        pass

    def y_rotated(self, quarter_turns: int) -> "Region":
        pass

    def shifted(self, offset: Pos) -> "Region":
        pass

    def __or__(self, other: "Region") -> Any:
        return NotImplemented

    def __and__(self, other: "Region") -> Any:
        return NotImplemented

    def __contains__(self, point: Pos) -> bool:
        raise NotImplementedError

    def is_empty(self) -> bool:
        raise NotImplementedError

    def intersects(self, other: "Region") -> bool:
        return not (self & other).is_empty()


@dataclass(frozen=True)
class RectangularPrism(Region):
    """
    Inclusive on all edges.
    """

    min_pos: Pos
    max_pos: Pos

    def shifted(self, offset: Pos) -> Region:
        return RectangularPrism(
            min_pos=self.min_pos + offset,
            max_pos=self.max_pos + offset,
        )

    def xz_padded(self, padding_blocks: int = 1) -> Region:
        """
        >>> RectangularPrism(Pos(0, 0, 0), Pos(1, 2, 3)).xz_padded()
        RectangularPrism(Pos(-1, 0, -1), Pos(2, 2, 4))
        """
        return RectangularPrism(
            min_pos=self.min_pos - Pos(padding_blocks, 0, padding_blocks),
            max_pos=self.max_pos + Pos(padding_blocks, 0, padding_blocks),
        )

    def y_rotated(self, quarter_turns: int) -> Region:
        a = self.min_pos.y_rotated(quarter_turns)
        b = self.max_pos.y_rotated(quarter_turns)

        return RectangularPrism(
            min_pos=Pos.elem_min(a, b),
            max_pos=Pos.elem_max(a, b),
        )

    def __contains__(self, point: Pos) -> bool:
        return self.min_pos <= point <= self.max_pos

    def __and__(self, other: Region) -> Any:
        if isinstance(other, RectangularPrism):
            return RectangularPrism(
                min_pos=Pos.elem_max(self.min_pos, other.min_pos),
                max_pos=Pos.elem_min(self.max_pos, other.max_pos),
            )
        else:
            return NotImplemented

    def __rand__(self, other: Region) -> Any:
        return self.__and__(other)

    def __or__(self, other: Region) -> Any:
        if isinstance(other, RectangularPrism):
            return CompositeRegion(
                subregions=(self, other),
            )
        else:
            return NotImplemented

    def __ror__(self, other: Region) -> Any:
        return self.__or__(other)

    def is_empty(self) -> bool:
        return not (self.min_pos <= self.max_pos)

    def __str__(self) -> str:
        return f"RectangularPrism({self.min_pos}, {self.max_pos})"

    def __repr__(self) -> str:
        return str(self)


@dataclass(frozen=True)
class CompositeRegion(Region):
    """
    Note: Not necessarily minimal.
    May contain exclusively empty regions, or have completely overlapping regions.
    """

    subregions: tuple[Region, ...]

    @property  # type: ignore
    @cache
    def min_pos(self) -> Pos:  # type: ignore
        return Pos.elem_min(*[region.min_pos for region in self.subregions])

    @property  # type: ignore
    @cache
    def max_pos(self) -> Pos:  # type: ignore
        return Pos.elem_max(*[region.max_pos for region in self.subregions])

    def shifted(self, offset: Pos) -> Region:
        return CompositeRegion(
            subregions=tuple(region.shifted(offset) for region in self.subregions),
        )

    def xz_padded(self, padding_blocks: int = 1) -> Region:
        return CompositeRegion(
            tuple(region.xz_padded(padding_blocks) for region in self.subregions)
        )

    def y_rotated(self, quarter_turns: int) -> Region:
        return CompositeRegion(
            subregions=tuple(
                region.y_rotated(quarter_turns) for region in self.subregions
            )
        )

    def __contains__(self, point: Pos) -> bool:
        return any(point in region for region in self.subregions)

    def __or__(self, other: Region) -> Any:
        if isinstance(other, CompositeRegion):
            return CompositeRegion(
                subregions=(*self.subregions, *other.subregions),
            )
        else:
            return CompositeRegion(
                subregions=(*self.subregions, other),
            )

    def __ror__(self, other: Region) -> Any:
        return self.__or__(other)

    def __and__(self, other: Region) -> Any:
        if isinstance(other, CompositeRegion):
            # When combining composite regions, flatten.
            regions = [
                combined_region
                for self_subregion in self.subregions
                for other_subregion in other.subregions
                if not (combined_region := self_subregion & other_subregion).is_empty()
            ]
        else:
            regions = [
                combined_region
                for region in self.subregions
                if not (combined_region := region & other).is_empty()
            ]

        return CompositeRegion(subregions=tuple(regions))

    def __rand__(self, other: Region) -> Any:
        return self.__and__(other)

    def is_empty(self) -> bool:
        return all(region.is_empty() for region in self.subregions)


def any_overlap(regions: set[Region]) -> bool:
    """
    TODO: Use AABB bounds to speed this up.

    >>> any_overlap({
    ...     CompositeRegion((
    ...         RectangularPrism(Pos(10, 0, 0), Pos(15, 5, 5)),
    ...         RectangularPrism(Pos(10, 0, 0), Pos(10, 0, 0)),
    ...         RectangularPrism(Pos(0, 0, 10), Pos(5, 5, 15)),
    ...     )),
    ...     RectangularPrism(Pos(0, 10, 0), Pos(5, 15, 5)),
    ... })
    False

    >>> any_overlap({
    ...     CompositeRegion((
    ...         RectangularPrism(Pos(10, 0, 0), Pos(15, 5, 5)),
    ...         RectangularPrism(Pos(0, 0, 10), Pos(5, 5, 15)),
    ...     )),
    ...     RectangularPrism(Pos(10, 0, 0), Pos(15, 5, 5)),
    ...     RectangularPrism(Pos(5, 0, 0), Pos(10, 5, 5)),
    ... })
    True
    """
    ordered_regions = list(regions)

    return any(
        left.intersects(right)
        for left_index, left in enumerate(ordered_regions)
        for right in ordered_regions[left_index + 1 :]
    )
