from typing import cast

from redhdl.instances import SchematicInstance
from redhdl.netlist import InstanceId, Netlist
from redhdl.region import Direction, Pos, any_overlap, xz_directions

InstancePlacement = dict[InstanceId, tuple[Pos, Direction]]


def placement_valid(netlist: Netlist, placement: InstancePlacement) -> bool:
    """
    Determine if a placement of netlist components is valid.

    This relies on any_overlap. Until extremely intelligent caching is added, this
    is likely very inefficient for large placements.
    """
    instance_regions = {
        cast(SchematicInstance, netlist.instances[instance_id])
        .region.y_rotated(xz_directions.index(direction))
        .shifted(pos)
        .xz_padded()  # Components need in-between space.
        for instance_id, (pos, direction) in placement.items()
    }

    return not any_overlap(instance_regions)
