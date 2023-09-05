"""
Bitrange: Handling (inclusive) sets of (start_index, end_index) integer ranges.

Largely used to handle vHDL bitarray index slice logic.
"""
from redhdl.netlist import Port  # To support Port pin_count => BitRange.

BitRange = tuple[int, int]


def flattened_bitranges(bitranges: set[tuple[int, int]]) -> set[int]:
    return set.union(*(set(range(start, end + 1)) for (start, end) in bitranges))


def bitranges_valid(bitranges: set[tuple[int, int]]) -> bool:
    return len(flattened_bitranges(bitranges)) == sum(
        end - start + 1 for start, end in bitranges
    )


def bitranges_equal(a: set[tuple[int, int]], b: set[tuple[int, int]]) -> bool:
    """
    >>> bitranges_equal({(0, 7)}, {(3, 7), (0, 2)})
    True
    >>> bitranges_equal({(0, 7)}, {(3, 7), (0, 1)})
    False
    """
    return flattened_bitranges(a) == flattened_bitranges(b)


def bitrange_width(bitrange: BitRange) -> int:
    start, stop = bitrange
    return stop - start + 1


def port_bitrange(port: Port) -> BitRange:
    return (0, port.pin_count - 1)
