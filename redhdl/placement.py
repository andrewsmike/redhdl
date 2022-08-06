from functools import reduce
from operator import or_
from random import choice, random, sample
from typing import cast

from frozendict import frozendict

from redhdl.instances import SchematicInstance
from redhdl.netlist import InstanceId, Netlist
from redhdl.region import (
    CompositeRegion,
    Direction,
    Pos,
    any_overlap,
    direction_unit_pos,
    is_direction,
    xz_directions,
)

InstancePlacement = frozendict[InstanceId, tuple[Pos, Direction]]


def placement_valid(
    netlist: Netlist, placement: InstancePlacement, xz_padding: int = 1
) -> bool:
    """
    Determine if a placement of netlist components is valid.

    This relies on any_overlap. Until extremely intelligent caching is added, this
    is likely very inefficient for large placements.
    """
    instance_regions = [
        cast(SchematicInstance, netlist.instances[instance_id])
        .region.y_rotated(xz_directions.index(direction))
        .shifted(pos)
        .xz_padded(xz_padding)  # Components need in-between space.
        for instance_id, (pos, direction) in placement.items()
    ]

    return not any_overlap(instance_regions)


def placement_schematic(netlist: Netlist, placement: InstancePlacement):
    instance_schematics = [
        cast(SchematicInstance, netlist.instances[instance_id])
        .schematic.y_rotated(xz_directions.index(direction))
        .shifted(pos)
        for instance_id, (pos, direction) in placement.items()
    ]

    return reduce(or_, instance_schematics)


def placement_region(netlist: Netlist, placement: InstancePlacement) -> CompositeRegion:
    return CompositeRegion(
        tuple(
            cast(SchematicInstance, netlist.instances[instance_id])
            .region.y_rotated(xz_directions.index(direction))
            .shifted(pos)
            for instance_id, (pos, direction) in placement.items()
        )
    )


direction_unit_poses = list(direction_unit_pos.values())


def mutated_individual_placement(
    placement: tuple[Pos, Direction]
) -> tuple[Pos, Direction]:
    direction: str | Direction
    pos, direction = placement
    if random() < 0.25:
        direction = choice(xz_directions)

    if random() < 0.8:
        pos += choice(direction_unit_poses)

    assert is_direction(direction)

    return (pos, direction)


def mutated_placement(
    netlist: Netlist, placement: InstancePlacement
) -> InstancePlacement:
    instances_to_tweak_count = max(len(placement) // 3, 2)
    instances_to_tweak = sample(list(placement.keys()), k=instances_to_tweak_count)

    return frozendict(
        {
            instance_id: (
                mutated_individual_placement(placement)
                if instance_id in instances_to_tweak
                else placement
            )
            for instance_id, placement in placement.items()
        }
    )
