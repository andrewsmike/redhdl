"""
Instances with underlying schematics / regions.

This doesn't know / care how the schematics or descriptions were created.
Simple patterns will, with luck, give way to more complicated stacking semantics.
"""
from abc import ABCMeta, abstractmethod
from dataclasses import dataclass, replace
from typing import Mapping

from redhdl.netlist import Instance, PortName
from redhdl.region import (
    Direction,
    Pos,
    PositionSequence,
    Region,
    xz_direction_y_rotated,
)
from redhdl.schematic import Schematic


class PortPlacement(metaclass=ABCMeta):
    """
    Any type of port interface placement.

    These may be repeaters, comparators, hard-powered-blocks, wires, etc.
    """

    @abstractmethod
    def y_rotated(self, quarter_turns: int = 1) -> "PortPlacement":
        ...

    @abstractmethod
    def shifted(self, offset: Pos) -> "PortPlacement":
        ...


@dataclass
class RepeaterPortPlacement(PortPlacement):
    """
    Simplest type of port: a repeater interface, all facing the same way.
    """

    positions: PositionSequence
    facing: Direction

    def y_rotated(self, quarter_turns: int = 1) -> "RepeaterPortPlacement":
        return replace(
            self,
            positions=self.positions.y_rotated(quarter_turns),
            facing=xz_direction_y_rotated(self.facing, quarter_turns),
        )

    def shifted(self, offset: Pos) -> "RepeaterPortPlacement":
        return replace(
            self,
            positions=self.positions + offset,
        )


@dataclass
class SchematicInstance(Instance):
    """
    An plain-old-data instance with an attached schematic.
    """

    name: str

    schematic: Schematic
    region: Region
    port_placement: Mapping[PortName, PortPlacement]
