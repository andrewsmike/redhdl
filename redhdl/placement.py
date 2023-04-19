"""
Placement tools and bussing-naive search methods.

Placements are mappings from InstanceIds to (Position, Direction).
Bussing-naive placement search is a first-past heuristic search that's useful in the construction of
more advanced and adaptive bussing-aware search.

Placement is SchematicInstance specific and provides schematic-specific helpers.
"""
from dataclasses import dataclass
from functools import reduce
from itertools import combinations
from operator import or_
from random import choice, random, sample
from typing import Iterable, cast

from frozendict import frozendict
from tqdm import tqdm

from redhdl.instances import SchematicInstance
from redhdl.local_search import LocalSearchProblem, sim_annealing_searched_solution
from redhdl.netlist import InstanceId, Netlist, PinId, PinIdSequence
from redhdl.region import (
    CompositeRegion,
    Direction,
    Pos,
    PositionSequence,
    any_overlap,
    direction_unit_pos,
    display_regions,
    is_direction,
    random_pos,
    xz_directions,
)
from redhdl.schematic import Schematic

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


def placement_schematic(netlist: Netlist, placement: InstancePlacement) -> Schematic:
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
    dest_pin_id: PinId
    dest_pin_pos: Pos


def source_dest_pin_pos_pairs(
    netlist: Netlist,
    placement: InstancePlacement,
) -> Iterable[PinPosPair]:
    """The pin@pos -> pin@pos pairs of a network + placement."""
    for network_id, network in netlist.networks.items():
        source_pin_points = placement_pin_seq_points(
            netlist, network.input_pin_id_seq, placement
        )

        for dest_pin_id_seq in network.output_pin_id_seqs:
            dest_pin_points = placement_pin_seq_points(
                netlist, dest_pin_id_seq, placement
            )

            yield from (
                PinPosPair(
                    source_pin_id=source_pin_id,
                    source_pin_pos=source_pin_pos,
                    dest_pin_id=dest_pin_id,
                    dest_pin_pos=dest_pin_pos,
                )
                for source_pin_id, source_pin_pos, dest_pin_id, dest_pin_pos in zip(
                    network.input_pin_id_seq.pin_ids,
                    source_pin_points,
                    dest_pin_id_seq.pin_ids,
                    dest_pin_points,
                )
            )


def display_placement(netlist: Netlist, placement: InstancePlacement):
    display_regions(*list(placement_region(netlist, placement).subregions))


MAX_PLACEMENT_ATTEMPTS = 40


def netlist_random_placement(netlist: Netlist) -> InstancePlacement:
    assert all(
        isinstance(instance, SchematicInstance)
        for instance in netlist.instances.values()
    )

    instances: dict[str, SchematicInstance] = cast(
        dict[str, SchematicInstance],
        {name: instance for name, instance in netlist.instances.items()},
    )

    max_area: Pos = sum(
        (instance.region.max_pos + Pos(1, 1, 1) for instance in instances.values()),
        start=Pos(0, 0, 0),
    ) + Pos(
        8, 8, 8
    )  # TODO: Make less arbitrary.

    placement: InstancePlacement = frozendict()
    for instance_name, instance in instances.items():
        for i in range(MAX_PLACEMENT_ATTEMPTS):
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


MAX_PADDING = 4


def instance_buffer_blocks(netlist: Netlist, placement: InstancePlacement) -> float:
    region = placement_region(netlist, placement)
    for padding in range(1, MAX_PADDING):
        padded_regions = [
            subregion.xz_padded(padding) for subregion in region.subregions
        ]
        collision_count = sum(
            left.intersects(right) for left, right in combinations(padded_regions, 2)
        )
        if collision_count > 0:
            return (
                padding
                - 1
                + collision_count / len(list(combinations(padded_regions, 2)))
            )

    return MAX_PADDING


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
    placement: tuple[Pos, Direction]
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


@dataclass
class PlacementProblem(LocalSearchProblem[InstancePlacement]):
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
    placement_problem = PlacementProblem(netlist)
    return sim_annealing_searched_solution(
        placement_problem, total_rounds=max_iterations
    )
