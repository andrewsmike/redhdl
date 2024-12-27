"""slice(), but hashable."""

from collections.abc import Iterator


class Slice:
    """
    Immutable / hashable slice type.

    The built-in slice() is unhashable to avoid accidental dict assignments.

    >>> Slice(4)
    Slice(0, 4, 1)

    >>> Slice(1, 3)
    Slice(1, 3, 1)

    >>> Slice(10, 0, -1)
    Slice(10, 0, -1)

    >>> Slice(4).values()
    [0, 1, 2, 3]

    >>> Slice(3, -1, -1).values()
    [3, 2, 1, 0]
    """

    start: int
    stop: int
    step: int

    def __init__(self, *args: int):
        if len(args) not in (1, 2, 3):
            raise ValueError("Slice usage: Slice(stop) or Slice(start, stop[, step]).")

        if len(args) == 1:
            self.stop = args[0]
            self.start = 0
            self.step = 1
        elif len(args) == 2:
            self.start = args[0]
            self.stop = args[1]
            self.step = 1
        elif len(args) == 3:
            self.start = args[0]
            self.stop = args[1]
            self.step = args[2]

    def values(self) -> list[int]:
        return list(range(self.start, self.stop, self.step))

    def __iter__(self) -> Iterator[int]:
        return iter(self.values())

    def __len__(self) -> int:
        return len(self.values())

    def __str__(self) -> str:
        return f"Slice({self.start}, {self.stop}, {self.step})"

    def __repr__(self) -> str:
        return f"Slice({self.start}, {self.stop}, {self.step})"

    def __hash__(self) -> int:
        return hash(repr(self))

    def __eq__(self, other) -> bool:
        return (
            self.start == other.start
            and self.stop == other.stop
            and self.step == other.step
        )
