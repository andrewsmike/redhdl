"""
Simple 3d region representation and manipulation library.

Region types:
- Point prisms
- Rectangular prisms
- Composite regions
- TODO: Efficient diagonal polyhedra for diagonal circuits.

Example usages:
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
from abc import ABCMeta, abstractmethod
from dataclasses import dataclass
from functools import cache, cached_property
from pprint import pformat
from random import randint
from typing import (
    Any,
    Iterator,
    Literal,
    NamedTuple,
    TypeGuard,
    TypeVar,
    cast,
    overload,
)

from redhdl.slice import Slice

Axis = Literal[0, 1, 2]


X_AXIS, Y_AXIS, Z_AXIS = axes = cast(list[Axis], [0, 1, 2])


# Direction: Axis, is_positive
Direction = Literal["up", "down", "north", "east", "south", "west"]


directions: list[Direction] = ["up", "down", "north", "east", "south", "west"]


def is_direction(value: str) -> TypeGuard[Direction]:
    return value in directions


# Ordered by right-hand-rule rotations on the y axis.
xz_directions = [
    "north",
    "east",
    "south",
    "west",
]

direction_by_axis_ispos: dict[tuple[Axis, bool], Direction] = {
    (0, True): "east",
    (2, True): "south",
    (0, False): "west",
    (2, False): "north",
    (1, True): "up",
    (1, False): "down",
}

direction_axis_ispos = {
    direction: axis_is_pos for axis_is_pos, direction in direction_by_axis_ispos.items()
}


opposite_direction: dict[str, Direction] = {
    "north": "south",
    "south": "north",
    "up": "down",
    "down": "up",
    "east": "west",
    "west": "east",
}


def xz_direction_y_rotated(direction: Direction, quarter_turns: int = 1) -> Direction:
    for i in range(quarter_turns):
        direction = cast(
            Direction,
            {
                "north": "west",
                "west": "south",
                "south": "east",
                "east": "north",
            }[direction],
        )

    return direction


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
                [z, y, -x],
                [-x, y, -z],
                [-z, y, x],
            ][quarter_turns % 4]
        )

    def is_zero(self) -> bool:
        return self == Pos(0, 0, 0)

    def l1(self) -> int:
        return sum(abs(self))

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
    "west": Pos(-1, 0, 0),
    "down": Pos(0, -1, 0),
    "north": Pos(0, 0, -1),
    "east": Pos(1, 0, 0),
    "up": Pos(0, 1, 0),
    "south": Pos(0, 0, 1),
}


def random_pos(inclusive_max_pos: Pos) -> Pos:
    return Pos(
        randint(0, inclusive_max_pos.x),
        randint(0, inclusive_max_pos.y),
        randint(0, inclusive_max_pos.z),
    )


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

        max_step_count = max(abs(axis_step_counts))
        if not all(
            (step_count == 0) or (step_count == max_step_count)
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
        [Pos(3, 2, -1), Pos(4, 3, -2)]
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


class Region(metaclass=ABCMeta):
    min_pos: Pos
    max_pos: Pos

    @abstractmethod
    def xz_padded(self, padding_blocks: int = 1) -> "Region":
        pass

    @abstractmethod
    def y_rotated(self, quarter_turns: int) -> "Region":
        pass

    @abstractmethod
    def shifted(self, offset: Pos) -> "Region":
        pass

    @abstractmethod
    def __or__(self, other: "Region") -> Any:
        pass

    @abstractmethod
    def __and__(self, other: "Region") -> Any:
        pass

    def __len__(self) -> int:
        return len(list(self))

    @abstractmethod
    def __iter__(self) -> Iterator[Pos]:
        pass

    @cache
    def region_points(self) -> frozenset[Pos]:
        return frozenset(self)

    @abstractmethod
    def __contains__(self, point: Pos) -> bool:
        pass

    @abstractmethod
    def is_empty(self) -> bool:
        pass

    def intersects(self, other: "Region") -> bool:
        return not (self & other).is_empty()


@dataclass(frozen=True)
class PointRegion(Region):
    points: frozenset[Pos]

    def shifted(self, offset: Pos) -> Region:
        return PointRegion(frozenset(point + offset for point in self.points))

    def xz_padded(self, padding_blocks: int = 1) -> Region:
        """
        >>> region = PointRegion(frozenset({Pos(0, 0, 0)})).xz_padded(2)
        >>> Pos(2, 2, 2) in region
        True
        >>> Pos(3, 2, 2) in region
        False
        """
        return PointRegion(
            frozenset(
                point + Pos(dx, dy, dz)
                for point in self.points
                for dx in range(-padding_blocks, padding_blocks + 1)
                for dy in range(-padding_blocks, padding_blocks + 1)
                for dz in range(-padding_blocks, padding_blocks + 1)
            )
        )
        self.min_pos - Pos(padding_blocks, 0, padding_blocks),

    def y_rotated(self, quarter_turns: int) -> Region:
        return PointRegion(
            frozenset(point.y_rotated(quarter_turns) for point in self.points)
        )

    def __len__(self) -> int:
        return len(self.points)

    def __iter__(self) -> Iterator[Pos]:
        return iter(self.points)

    def __contains__(self, point: Pos) -> bool:
        return point in self.points

    def __and__(self, other: Region) -> Any:
        if isinstance(other, PointRegion):
            return PointRegion(self.points & other.points)
        elif isinstance(other, (RectangularPrism, CompositeRegion)):
            return PointRegion(
                frozenset(point for point in self.points if point in other)
            )
        else:
            return NotImplemented

    def __rand__(self, other: Region) -> Any:
        return self.__and__(other)

    def __or__(self, other: Region) -> Any:
        if isinstance(other, PointRegion):
            return PointRegion(
                self.points | other.points,
            )
        elif isinstance(other, RectangularPrism):
            return CompositeRegion(
                subregions=(self, other),
            )
        elif isinstance(other, CompositeRegion):
            return CompositeRegion(subregions=(*other.subregions, self))
        else:
            return NotImplemented

    def __ror__(self, other: Region) -> Any:
        return self.__or__(other)

    def is_empty(self) -> bool:
        return len(self.points) == 0

    def __str__(self) -> str:
        points_str = pformat(set(self.points))
        prefix = "PointRegion("
        points_str = points_str.replace("\n", "\n" + " " * len(prefix))
        return f"PointRegion({points_str})"

    def __repr__(self) -> str:
        return str(self)


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

        >>> RectangularPrism(Pos(20, 12, 11), Pos(34, 13, 14)).xz_padded()
        RectangularPrism(Pos(19, 12, 10), Pos(35, 13, 15))
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

    def __len__(self) -> int:
        """
        >>> len(RectangularPrism(Pos(0, 0, 0), Pos(1, 1, 1)))
        8
        """
        width, height, depth = self.max_pos - self.min_pos + Pos(1, 1, 1)
        return width * height * depth

    def __iter__(self) -> Iterator[Pos]:
        for x in range(self.min_pos.x, self.max_pos.x + 1):
            for y in range(self.min_pos.y, self.max_pos.y + 1):
                for z in range(self.min_pos.z, self.max_pos.z + 1):
                    yield Pos(x, y, z)

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

    @cached_property
    def min_pos(self) -> Pos:  # type: ignore
        return Pos.elem_min(*[region.min_pos for region in self.subregions])

    @cached_property
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

    @cache
    def __len__(self) -> int:
        """
        The area taken by a set of overlapping regions is a hard problem.
        This method will not scale gracefully to large numbers of subregions.
        """
        block_count = 0
        counted_regions = CompositeRegion(tuple())
        for subregion in self.subregions:
            # Invariant: len(counted_region.subregions) < len(self.subregions)
            # Base case: len(self.subregions) == 0, return 0.
            block_count += len(subregion) - len(subregion & counted_regions)
            counted_regions |= subregion

        return block_count

    def __iter__(self) -> Iterator[Pos]:
        return iter({point for region in self.subregions for point in region})

    def __contains__(self, point: Pos) -> bool:
        return any(point in region for region in self.subregions)

    def __or__(self, other: Region) -> Any:
        if isinstance(other, CompositeRegion):
            return CompositeRegion(
                subregions=(*self.subregions, *other.subregions),
            )

        if isinstance(other, PointRegion):
            for index, region in enumerate(self.subregions):
                if isinstance(region, PointRegion):
                    return CompositeRegion(
                        subregions=(
                            self.subregions[:index]
                            + (region | other,)
                            + self.subregions[index + 1 :]
                        )
                    )

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

    @cache
    def region_points(self) -> frozenset[Pos]:
        return frozenset.union(*(region.region_points() for region in self.subregions))


def any_overlap(regions: list[Region]) -> bool:
    """
    TODO: Use AABB bounds to speed this up.

    >>> any_overlap([
    ...     CompositeRegion((
    ...         RectangularPrism(Pos(10, 0, 0), Pos(15, 5, 5)),
    ...         RectangularPrism(Pos(10, 0, 0), Pos(10, 0, 0)),
    ...         RectangularPrism(Pos(0, 0, 10), Pos(5, 5, 15)),
    ...     )),
    ...     RectangularPrism(Pos(0, 10, 0), Pos(5, 15, 5)),
    ... ])
    False

    >>> any_overlap([
    ...     CompositeRegion((
    ...         RectangularPrism(Pos(10, 0, 0), Pos(15, 5, 5)),
    ...         RectangularPrism(Pos(0, 0, 10), Pos(5, 5, 15)),
    ...     )),
    ...     RectangularPrism(Pos(10, 0, 0), Pos(15, 5, 5)),
    ...     RectangularPrism(Pos(5, 0, 0), Pos(10, 5, 5)),
    ... ])
    True
    """
    return any(
        left.intersects(right)
        for left_index, left in enumerate(regions)
        for right in regions[left_index + 1 :]
    )


def point_ranges(points: set[int], min_gap_size: int = 3) -> list[tuple[int, int]]:
    """
    The minimal set of ranges completely covering a set of points, with gap sizes
    of at least min_gap_size.

    >>> point_ranges({8, 10, 11, 15, 16, 19, 20}, min_gap_size=1)
    [(8, 8), (10, 11), (15, 16), (19, 20)]

    >>> point_ranges({8, 10, 11, 15, 16, 19, 20}, min_gap_size=3)
    [(8, 11), (15, 20)]

    >>> point_ranges({8, 10, 11, 15, 16, 19, 20}, min_gap_size=4)
    [(8, 20)]
    """
    lower_bound, upper_bound = min(points), max(points)

    ranges: list[tuple[int, int]] = []

    # Track the current distance to the last block (moving towards higher
    # numbers) in gap_count and the current range's lower bound (reset to None
    # once we get min_gap_size away from the current ranges and we carve it
    # out).
    gap_count = 0
    current_lower_bound: int | None = None
    for i in range(lower_bound, upper_bound + 1):
        if i in points:
            # current_lower_bound is None: New range!
            # current_lower_bound is not None: Continue range, reset gap count
            gap_count = 0
            if current_lower_bound is None:
                current_lower_bound = i
        else:
            # current_lower_bound is None: Not in a range, continue onwards.
            # current_lower_bound is not None: In a range, end range and reset iff
            # gap_count is >= min_gap_size.
            gap_count += 1
            if gap_count == min_gap_size:
                assert current_lower_bound is not None  # For MyPy.
                ranges.append((current_lower_bound, i - min_gap_size))
                current_lower_bound = None

    if current_lower_bound is not None:
        return ranges + [(current_lower_bound, i)]
    else:
        return ranges


AxisData = TypeVar("AxisData")


@overload
def partial_coord(
    values: tuple[AxisData, AxisData], axis_index: int
) -> tuple[AxisData]:
    ...


@overload
def partial_coord(
    values: tuple[AxisData, AxisData, AxisData], axis_index: int
) -> tuple[AxisData, AxisData]:
    ...


def partial_coord(values, axis_index):
    if len(values) == 3:
        x, y, z = values
        return [
            (z, y),  # Prefer that 'Y' stay vertical when possible.
            (x, z),
            (x, y),
        ][axis_index]
    else:
        x, y = values
        return [
            (y,),
            (x,),
        ][axis_index]


def display_regions_orthographic(regions: list[Region], axis: Axis) -> None:
    """
    "Compactly" display a list of regions in ASCII using an axis-aligned
    orthographic projection, removing empty space.

    >>> display_regions_orthographic(  # doctest: +NORMALIZE_WHITESPACE
    ...     regions=[
    ...         RectangularPrism(Pos(0, 0, 0), Pos(4, 8, 4)),
    ...         RectangularPrism(Pos(6, -1, 6), Pos(10, 4, 10)),
    ...         RectangularPrism(Pos(20, 15, 20), Pos(28, 20, 28)),
    ...     ],
    ...     axis=0,
    ... )
    Y
                 .
                 . 333333333
                 . 333333333
                 . 333333333
                 . 333333333
                 . 333333333
                 . 333333333
                 .
    .........................
                 .
     11111       .
     11111       .
     11111       .
     11111       .
     11111 22222 .
     11111 22222 .
     11111 22222 .
     11111 22222 .
     11111 22222 .
           22222 .
                 .           Z
    """
    axis_names = partial_coord(("X", "Y", "Z"), axis)

    assert len(regions) < 10
    region_symbol = dict(zip(regions, "1234567890"))
    region_all_points = {
        region: {partial_coord(pos, axis) for pos in region} for region in regions
    }
    all_points = set.union(*region_all_points.values())

    # Handle overlaps gracefully: If point is already assigned a different
    # region's symbol, assign it to '*'.
    point_symbol = {}
    for region, region_points in region_all_points.items():
        for point in region_points:
            if point in point_symbol:
                point_symbol[point] = "*"
            else:
                point_symbol[point] = region_symbol[region]

    x_filled_ranges = point_ranges({partial_coord(point, 1)[0] for point in all_points})
    y_filled_ranges = point_ranges({partial_coord(point, 0)[0] for point in all_points})

    total_height = (
        sum(ymax - ymin + 1 + 2 for ymin, ymax in y_filled_ranges)
        + len(y_filled_ranges)
        - 1
    )
    total_width = (
        sum(xmax - xmin + 1 + 2 for xmin, xmax in x_filled_ranges)
        + len(x_filled_ranges)
        - 1
    )

    spacing_line = ""
    for index, (xmin, xmax) in enumerate(x_filled_ranges):
        if index > 0:
            spacing_line += "."
        spacing_line += " " + " " * (xmax - xmin + 1) + " "

    # Reversed order.
    result_lines = []

    xmin, xmax = x_filled_ranges[0][0], x_filled_ranges[-1][1]
    ymin, ymax = y_filled_ranges[0][0], y_filled_ranges[-1][1]
    for y_index, (range_y_min, range_y_max) in enumerate(y_filled_ranges):
        if y_index > 0:
            result_lines.append("." * total_width)

        if y_index == 0:
            result_lines.append(spacing_line + axis_names[0])
        else:
            result_lines.append(spacing_line)

        for y in range(range_y_min, range_y_max + 1):
            line = ""
            for x_index, (range_x_min, range_x_max) in enumerate(x_filled_ranges):
                if x_index > 0:
                    line += "."
                content = "".join(
                    [
                        point_symbol.get((x, y), " ")
                        for x in range(range_x_min, range_x_max + 1)
                    ]
                )
                line += " " + content + " "

            result_lines.append(line)

        result_lines.append(spacing_line)

    result_lines.append(axis_names[1])

    for line in reversed(result_lines):
        print(line)


def display_regions(regions: list[Region]) -> None:
    for perspective_axis in (X_AXIS, Y_AXIS, Z_AXIS):
        display_regions_orthographic(regions, perspective_axis)
        print()
