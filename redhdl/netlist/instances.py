"""Concrete Netlist Instance (with Ports) with a backing Schematic."""

from abc import ABCMeta, abstractmethod
from dataclasses import dataclass, replace
from typing import Mapping

from redhdl.netlist.netlist import Instance, PortName, PortType
from redhdl.voxel.region import (
    Direction,
    Pos,
    PositionSequence,
    Region,
    direction_unit_pos,
    xz_direction_y_rotated,
)
from redhdl.voxel.schematic import Schematic


class PortInterface(metaclass=ABCMeta):
    """
    A redstone interface to an component.

    May be a repeater, comparator, wire, etc.

    Currently just used to determine the relative offset of the input/output wires,
    accounting for the port's relative orientation.
    """

    @abstractmethod
    def y_rotated(self, quarter_turns: int = 1) -> "PortInterface":
        ...

    @abstractmethod
    def wire_offset(self, port_type: PortType) -> Pos:
        ...


@dataclass
class RepeaterPortInterface(PortInterface):
    """Simplest type of port: a repeater interface, all facing the same way."""

    facing: Direction

    def y_rotated(self, quarter_turns: int = 1) -> "RepeaterPortInterface":
        return replace(
            self,
            facing=xz_direction_y_rotated(self.facing, quarter_turns),
        )

    def wire_offset(self, port_type: PortType) -> Pos:
        return {
            "out": direction_unit_pos[self.facing],
            "in": -direction_unit_pos[self.facing],
        }[port_type] + Pos(0, 1, 0)


@dataclass
class PortPlacement:
    positions: PositionSequence
    port_interface: PortInterface

    def y_rotated(self, quarter_turns: int = 1) -> "PortPlacement":
        return replace(
            self,
            positions=self.positions.y_rotated(quarter_turns),
            port_interface=self.port_interface.y_rotated(quarter_turns),
        )

    def shifted(self, offset: Pos) -> "PortPlacement":
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
