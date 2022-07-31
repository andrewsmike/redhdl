"""
Instances with underlying schematics / regions.

This doesn't know / care how the schematics or descriptions were created.
Simple patterns will, with luck, give way to more complicated stacking semantics.
"""
from dataclasses import dataclass, replace

from redhdl.netlist import Instance, Port
from redhdl.region import (
    Direction,
    Pos,
    PositionSequence,
    Region,
    xz_direction_y_rotated,
)
from redhdl.schematic import Schematic


@dataclass
class RepeaterPort(Port):
    positions: PositionSequence
    facing: Direction

    def y_rotated(self, quarter_turns: int = 1) -> "RepeaterPort":
        return replace(
            self,
            positions=self.positions.y_rotated(quarter_turns),
            facing=xz_direction_y_rotated(self.facing, quarter_turns),
        )

    def shifted(self, offset: Pos) -> "RepeaterPort":
        return replace(
            self,
            positions=self.positions + offset,
        )


@dataclass
class SchematicInstance(Instance):
    """
    Instances are attached to a particular netlist and aren't easily mutable.
    For routing logic, prefer compiling to a different datatype for manipulations.
    """

    name: str

    schematic: Schematic
    region: Region
