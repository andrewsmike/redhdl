"""
Placement tools and bussing-naive search methods.

Placements are mappings from InstanceIds to (Position, Direction).
Bussing-naive placement search is a first-pass heuristic search that's useful in the construction of
more advanced and adaptive bussing-aware search.

Placement is SchematicInstance specific and provides schematic-specific helpers.
"""

from dataclasses import dataclass
from functools import reduce
from operator import or_
from pprint import pprint
from random import choice, random, sample
from typing import cast

from frozendict import frozendict
from tqdm import tqdm

from redhdl.misc.caching import first_id_cached
from redhdl.netlist.instances import SchematicInstance
from redhdl.netlist.netlist import InstanceId, Netlist, PinId, PinIdSequence
from redhdl.search.local_search import (
    LocalSearchProblem,
    sim_annealing_searched_solution,
)
from redhdl.voxel.region import (
    CompositeRegion,
    Direction,
    PointRegion,
    Pos,
    PositionSequence,
    Region,
    any_overlap,
    direction_unit_pos,
    display_regions,
    is_direction,
    random_pos,
    xz_directions,
)
from redhdl.voxel.schematic import Schematic

InstancePlacement = frozendict[InstanceId, tuple[Pos, Direction]]


@first_id_cached
def placement_instance_region(
    netlist: Netlist,
    placement: InstancePlacement,
    instance_id: InstanceId,
) -> Region:
    pos, direction = placement[instance_id]

    return (
        cast(SchematicInstance, netlist.instances[instance_id])
        .region.y_rotated(xz_directions.index(direction))
        .shifted(pos)
    )


@first_id_cached
def placement_region(netlist: Netlist, placement: InstancePlacement) -> CompositeRegion:
    return CompositeRegion(
        tuple(
            placement_instance_region(netlist, placement, instance_id)
            for instance_id in placement.keys()
        )
    )


@first_id_cached
def placement_valid(
    netlist: Netlist, placement: InstancePlacement, xz_padding: int = 1
) -> bool:
    """
    Determine if a placement of netlist components is valid.

    This relies on any_overlap. Until extremely intelligent caching is added, this
    is likely very inefficient for large placements.
    """
    padded_instance_regions = [
        region.xz_padded(xz_padding)
        for region in placement_region(netlist, placement).subregions
    ]

    return not any_overlap(padded_instance_regions)


@first_id_cached
def placement_pin_seq_points(
    netlist: Netlist,
    pin_id_seq: PinIdSequence,
    placement: InstancePlacement,
) -> PositionSequence:
    """
    The position sequence corresponding to the given PinIdSequence in a given placement.
    """
    instance_id, port_name = pin_id_seq.port_id
    instance = netlist.instances[instance_id]
    port = instance.ports[port_name]

    if not isinstance(instance, SchematicInstance):
        raise ValueError(
            "Attempted to find pin position sequence for an Instance that wasn't a "
            + "SchematicInstance."
        )

    port_placement = instance.port_placement[port_name]

    wire_points = (
        port_placement.positions & pin_id_seq.slice
    ) + port_placement.port_interface.wire_offset(port.port_type)

    instance_id, _ = pin_id_seq.port_id
    instance_pos, instance_dir = placement[instance_id]

    return wire_points.y_rotated(xz_directions.index(instance_dir)) + instance_pos


@dataclass(frozen=True, order=True)
class PinPosPair:
    source_pin_id: PinId
    source_pin_pos: Pos
    source_pin_facing: Direction | None
    source_port_stride: Pos

    dest_pin_id: PinId
    dest_pin_pos: Pos
    dest_pin_facing: Direction | None
    dest_port_stride: Pos


@first_id_cached
def source_dest_pin_pos_pairs(
    netlist: Netlist,
    placement: InstancePlacement,
) -> list[PinPosPair]:
    """The pin@pos -> pin@pos pairs of a network + placement."""
    results: list[PinPosPair] = []

    for source_pin_id_seq, dest_pin_id_seq in netlist.source_dest_pin_id_seq_pairs():
        source_pin_points = placement_pin_seq_points(
            netlist, source_pin_id_seq, placement
        )

        dest_pin_points = placement_pin_seq_points(netlist, dest_pin_id_seq, placement)

        results.extend(
            PinPosPair(
                source_pin_id=source_pin_id,
                source_pin_pos=source_pin_pos,
                source_pin_facing=None,  # TODO: Specify this.
                source_port_stride=source_pin_points.step,
                dest_pin_id=dest_pin_id,
                dest_pin_pos=dest_pin_pos,
                dest_pin_facing=None,
                dest_port_stride=dest_pin_points.step,
            )
            for source_pin_id, source_pin_pos, dest_pin_id, dest_pin_pos in zip(
                source_pin_id_seq.pin_ids,
                source_pin_points,
                dest_pin_id_seq.pin_ids,
                dest_pin_points,
            )
        )

    return results


class OverlappingPlacementError(Exception):
    pass


def placement_schematic(netlist: Netlist, placement: InstancePlacement) -> Schematic:
    instance_schematics = [
        cast(SchematicInstance, netlist.instances[instance_id])
        .schematic.y_rotated(xz_directions.index(direction))
        .shifted(pos)
        for instance_id, (pos, direction) in placement.items()
    ]

    if any_overlap([schematic.mask() for schematic in instance_schematics]):
        raise OverlappingPlacementError(
            "Cannot generate schematic; placement has overlapping instances."
        )

    return reduce(or_, instance_schematics)


def display_placement(netlist: Netlist, placement: InstancePlacement):
    regions = {
        instance_id: placement_instance_region(
            netlist,
            placement,
            instance_id,
        )
        for instance_id in placement.keys()
    }

    pin_pos_pairs = source_dest_pin_pos_pairs(netlist, placement)
    source_poses = frozenset(
        pin_pos_pair.source_pin_pos for pin_pos_pair in pin_pos_pairs
    )
    dest_poses = frozenset(pin_pos_pair.dest_pin_pos for pin_pos_pair in pin_pos_pairs)

    ordered_instance_ids = sorted(placement.keys())
    display_regions(
        *(
            placement_instance_region(netlist, placement, instance_id)
            for instance_id in ordered_instance_ids
        ),
        PointRegion(source_poses),
        PointRegion(dest_poses),
    )
    ordered_instance_ids += ["outputs", "inputs"]
    pprint(dict(zip(range(1, len(ordered_instance_ids) + 1), ordered_instance_ids)))


MAX_PLACEMENT_ATTEMPTS = 40


def netlist_random_placement(netlist: Netlist) -> InstancePlacement:
    assert all(
        isinstance(instance, SchematicInstance)
        for name, instance in netlist.instances.items()
        if name not in ["input", "output"]
    )

    instances: dict[str, SchematicInstance] = cast(
        dict[str, SchematicInstance],
        {
            name: instance
            for name, instance in netlist.instances.items()
            if name not in ["input", "output"]
        },
    )

    max_area: Pos = sum(
        (instance.region.max_pos + Pos(1, 1, 1) for instance in instances.values()),
        start=Pos(0, 0, 0),
    ) + Pos(8, 8, 8)  # TODO: Make less arbitrary.

    placement: InstancePlacement = frozendict()
    for instance_name, instance in instances.items():
        for _attempt_index in range(MAX_PLACEMENT_ATTEMPTS):
            pos = random_pos(max_area - instance.region.max_pos - Pos(1, 1, 1))
            direction = choice(xz_directions)
            assert is_direction(direction)  # For MyPy.
            suggested_placement: InstancePlacement = frozendict(
                {**placement, instance_name: (pos, direction)}
            )
            if placement_valid(netlist, suggested_placement, xz_padding=3):
                placement = suggested_placement
                break
        else:
            raise TimeoutError(
                "Couldn't find an appropriate placement for a component "
                + f"({MAX_PLACEMENT_ATTEMPTS} attempts)."
            )

    return placement


def placement_compactness_score(
    netlist: Netlist, placement: InstancePlacement
) -> float:
    region = placement_region(netlist, placement)
    return -sum(region.max_pos - region.min_pos)  # type: ignore


MAX_PADDING = 5


def avg_instance_padding_blocks(
    netlist: Netlist, placement: InstancePlacement
) -> float:
    """
    The average minimum padding space around each instance.

    Only considers up to 5 spaces - enough for two busses to fit between.

    Returns values in the range [0, 5], with 0 being "all instances have immediate neighbors"
    and 5 being "all instances have 5 blocks of space around them".
    """

    composite_region = placement_region(netlist, placement)

    padding_blocks = 0
    instance_count = len(composite_region.subregions)  # Denominator

    for instance_region in composite_region.subregions:
        other_regions = CompositeRegion(
            tuple(
                subregion
                for subregion in composite_region.subregions
                if subregion != instance_region
            )
        )

        for padding in range(1, MAX_PADDING + 1):
            if instance_region.xz_padded(padding).intersects(other_regions):
                break

        padding_blocks += padding - 1

    return padding_blocks / instance_count


def random_searched_compact_placement(
    netlist: Netlist,
    max_iterations: int = 60_000,
    show_progressbar: bool = True,
) -> InstancePlacement:
    """Brute-force random search for compact placements."""

    if show_progressbar:
        it = tqdm(range(max_iterations))
    else:
        it = range(max_iterations)

    best_cost = None
    best_placement = None
    for i in it:
        if i % (max_iterations // 12) == 0:
            print(f"Best cost: {best_cost}")

        next_placement = netlist_random_placement(netlist)
        next_cost = -placement_compactness_score(netlist, next_placement)
        if best_cost is None or next_cost < best_cost:
            best_cost, best_placement = next_cost, next_placement

    print(f"Best cost: {best_cost}")

    assert best_placement is not None  # For MyPy.
    return best_placement


direction_unit_poses = list(direction_unit_pos.values())


def mutated_individual_placement(
    placement: tuple[Pos, Direction],
) -> tuple[Pos, Direction]:
    direction: str | Direction
    pos, direction = placement
    if random() < 0.1:
        direction = choice(xz_directions)

    pos += choice(direction_unit_poses)

    assert is_direction(direction)

    return (pos, direction)


def mutated_placement(placement: InstancePlacement) -> InstancePlacement:
    instances_to_tweak_count = max(len(placement) // 3, 2)
    instances_to_tweak = sample(list(placement.keys()), k=instances_to_tweak_count)

    tweaked_placement = {
        instance_id: (
            mutated_individual_placement(placement)
            if instance_id in instances_to_tweak
            else placement
        )
        for instance_id, placement in placement.items()
    }

    # Occasionally swap two instances entirely.
    if len(placement) > 1 and random() < 0.1:
        first_instance_id, second_instance_id = sample(list(placement.keys()), k=2)

        tweaked_placement = {
            **tweaked_placement,
            first_instance_id: tweaked_placement[second_instance_id],
            second_instance_id: tweaked_placement[first_instance_id],
        }

    return frozendict(tweaked_placement)


@dataclass
class CompactPlacementProblem(LocalSearchProblem[InstancePlacement]):
    netlist: Netlist

    def random_solution(self) -> InstancePlacement:
        return netlist_random_placement(self.netlist)

    def mutated_solution(self, solution: InstancePlacement) -> InstancePlacement:
        return mutated_placement(solution)

    def solution_cost(self, solution: InstancePlacement) -> float:
        if not placement_valid(self.netlist, solution):
            return 10000

        return -placement_compactness_score(self.netlist, solution)


def sim_annealing_searched_compact_placement(
    netlist: Netlist,
    max_iterations: int = 60_000,
) -> InstancePlacement:
    placement_problem = CompactPlacementProblem(netlist)
    return sim_annealing_searched_solution(
        placement_problem, total_rounds=max_iterations
    )
