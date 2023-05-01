from collections import Counter
from dataclasses import dataclass
from functools import reduce, wraps
import operator
from random import choice

from frozendict import frozendict

from redhdl.bussing import BussingError, BussingImpossibleError, BussingTimeoutError
from redhdl.local_search import LocalSearchProblem, sim_annealing_searched_solution
from redhdl.netlist import Netlist, PinId
from redhdl.path_search import (
    NoSolutionError,
    PathSearchProblem,
    SearchTimeoutError,
    a_star_bfs_searched_solution,
)
from redhdl.placement import (
    InstancePlacement,
    PinPosPair,
    placement_region,
    placement_schematic,
    source_dest_pin_pos_pairs,
)
from redhdl.positional_data import PositionalData
from redhdl.region import (
    PointRegion,
    Pos,
    RectangularPrism,
    Region,
    direction_unit_pos,
    xz_directions,
)
from redhdl.schematic import Block, Schematic


@dataclass
class PathFindingProblem(PathSearchProblem[Pos, Pos]):
    start_point: Pos
    stop_point: Pos
    blocked_points: frozenset[Pos]

    def initial_state(self) -> Pos:
        return self.start_point

    def state_actions(self, state: Pos) -> list[Pos]:
        return [
            next_pos
            for unit_pos in direction_unit_pos.values()
            if (
                ((next_pos := unit_pos + state) == self.stop_point)
                or (next_pos not in self.blocked_points)
            )
        ]

    def state_action_result(self, state: Pos, action: Pos) -> Pos:
        return action

    def state_action_cost(self, state: Pos, action: Pos) -> float:
        return 1

    def is_goal_state(self, state: Pos) -> bool:
        return state == self.stop_point

    def min_cost(self, state: Pos) -> float:
        return (state - self.stop_point).l1()


def bus_path(
    blocked_regions: Region,
    source_point: Pos,
    dest_point: Pos,
) -> list[Pos]:
    problem = PathFindingProblem(
        start_point=source_point,
        stop_point=dest_point,
        blocked_points=blocked_regions.region_points(),
    )

    try:
        return [source_point] + a_star_bfs_searched_solution(problem, max_steps=4_000)
    except SearchTimeoutError as e:
        raise BussingTimeoutError(f"Failed to find A* bus route: {e}")
    except NoSolutionError:
        raise BussingImpossibleError(
            f"No way to bus between {dest_point} and {source_point}."
        )


def first_id_cached(func):
    func._cache = {}

    @wraps(func)
    def wrapper(id_obj, *args, **kwargs):
        key = (id(id_obj), tuple(args), tuple(sorted(kwargs.items())))
        if key not in func._cache:
            try:
                func._cache[key] = (True, func(id_obj, *args, **kwargs))
            except BaseException as e:
                func._cache[key] = (False, e)

        success, result = func._cache[key]
        if success:
            return result
        else:
            raise result

    return wrapper


def wire_region(path: list[Pos]) -> Region:
    return PointRegion(
        frozenset(
            point + direction_unit_pos[xz_dir] + y_offset
            for point in path
            for xz_dir in xz_directions
            for y_offset in (Pos(0, -1, 0), Pos(0, 0, 0), Pos(0, 1, 0))
        )
    )


BusPaths = dict[PinId, list[Pos]]
PartialBusPaths = dict[PinId, list[Pos] | None]


@first_id_cached
def dest_pin_bus_path(
    netlist: Netlist,
    placement: InstancePlacement,
) -> BusPaths:
    blocks_region = placement_region(netlist, placement).xz_padded(1)

    dest_pin_bus_path: dict[PinId, list[Pos]] = {}
    for pin_pos_pair in source_dest_pin_pos_pairs(netlist, placement):
        path = bus_path(
            blocked_regions=blocks_region,
            source_point=pin_pos_pair.source_pin_pos,
            dest_point=pin_pos_pair.dest_pin_pos,
        )
        dest_pin_bus_path[pin_pos_pair.dest_pin_id] = path
        blocks_region = blocks_region | wire_region(path)

    return dest_pin_bus_path


def bus_trace_pos_blocks(bus_paths: BusPaths) -> PositionalData[Block]:
    return PositionalData(
        {
            bus_point: Block("minecraft:blue_wool", frozendict())
            for pin_id, bus_points in bus_paths.items()
            for bus_point in bus_points
        }
    )


def bussed_placement_schematic(
    netlist: Netlist,
    placement: InstancePlacement,
    bus_paths: BusPaths,
) -> Schematic:
    schem = placement_schematic(netlist, placement)
    schem.pos_blocks |= bus_trace_pos_blocks(bus_paths)
    return schem


def bussing_avg_length(bus_paths: PartialBusPaths) -> float:
    successful_bus_path_lengths = [
        len(bus_points) for bus_points in bus_paths.values() if bus_points is not None
    ]
    return sum(successful_bus_path_lengths) / len(successful_bus_path_lengths)


def bussing_max_length(bus_paths: PartialBusPaths) -> float:
    successful_bus_path_lengths = [
        len(bus_points) for bus_points in bus_paths.values() if bus_points is not None
    ]
    return max(successful_bus_path_lengths)


def bussing_min_avg_length(netlist: Netlist, placement: InstancePlacement) -> float:
    l1s = [
        (pin_pos_pair.dest_pin_pos - pin_pos_pair.source_pin_pos).l1()
        for pin_pos_pair in source_dest_pin_pos_pairs(netlist, placement)
    ]
    return sum(l1s) / len(l1s)


def bussing_min_max_length(netlist: Netlist, placement: InstancePlacement) -> float:
    l1s = [
        (pin_pos_pair.dest_pin_pos - pin_pos_pair.source_pin_pos).l1()
        for pin_pos_pair in source_dest_pin_pos_pairs(netlist, placement)
    ]
    return max(l1s)


def interrupted_pin_line_of_sight_count(
    netlist: Netlist, placement: InstancePlacement
) -> float:
    instance_regions = placement_region(netlist, placement)
    return sum(
        1
        for pin_pos_pair in source_dest_pin_pos_pairs(netlist, placement)
        if RectangularPrism(
            pin_pos_pair.source_pin_pos, pin_pos_pair.dest_pin_pos
        ).intersects(instance_regions)
    )


@dataclass
class RelaxedPathFindingProblem(PathSearchProblem[Pos, Pos]):
    start_point: Pos
    stop_point: Pos
    instance_points: frozenset[Pos]
    wire_points: frozenset[Pos]
    collision_cost: float = 6

    def initial_state(self) -> Pos:
        return self.start_point

    def state_actions(self, state: Pos) -> list[Pos]:
        return [
            next_pos
            for unit_pos in direction_unit_pos.values()
            if (
                (next_pos := unit_pos + state) == self.stop_point
                or next_pos not in self.instance_points
            )
        ]

    def state_action_result(self, state: Pos, action: Pos) -> Pos:
        return action

    def state_action_cost(self, state: Pos, action: Pos) -> float:
        return 1 if (action not in self.wire_points) else self.collision_cost

    def is_goal_state(self, state: Pos) -> bool:
        return state == self.stop_point

    def min_cost(self, state: Pos) -> float:
        return (state - self.stop_point).l1()


def relaxed_bus_path(
    instance_regions: Region,
    wire_regions: Region,
    source_point: Pos,
    dest_point: Pos,
    collision_cost: float,
) -> list[Pos]:
    problem = RelaxedPathFindingProblem(
        start_point=source_point,
        stop_point=dest_point,
        instance_points=instance_regions.region_points(),
        wire_points=wire_regions.region_points(),
        collision_cost=collision_cost,
    )

    try:
        return [source_point] + a_star_bfs_searched_solution(problem, max_steps=18_000)
    except SearchTimeoutError as e:
        raise BussingTimeoutError(f"Failed to find A* bus route: {e}")
    except NoSolutionError:
        raise BussingImpossibleError(
            f"No way to bus between {dest_point} and {source_point}."
        )


@first_id_cached
def collision_count(bus_paths: PartialBusPaths) -> int:
    taken_points = PointRegion(frozenset())

    collision_count = 0
    for path in bus_paths.values():
        if path is None:
            continue
        bus_points = wire_region(path)
        collision_count += len(bus_points & taken_points)
        taken_points |= bus_points

    return collision_count


@first_id_cached
def too_far_to_bus_count(bus_paths: PartialBusPaths) -> int:
    return sum(path is None for path in bus_paths.values())


MAX_RECENT_FAILURES = 64
_recent_dest_pin_bus_failures: list[PinId] = []


def recent_dest_pin_bus_failure_count() -> dict[PinId, int]:
    return Counter(_recent_dest_pin_bus_failures)


def record_dest_pin_bus_failure(pin_id: PinId) -> None:
    global _recent_dest_pin_bus_failures
    _recent_dest_pin_bus_failures = _recent_dest_pin_bus_failures[
        -(MAX_RECENT_FAILURES - 1) :
    ] + [pin_id]


def random_relaxed_bus_paths(
    instance_regions: Region,
    pin_pos_pairs: set[PinPosPair],
    collision_cost: float,
) -> PartialBusPaths:
    wire_regions: Region = PointRegion(frozenset())

    ordered_pin_pos_pairs = sorted(
        pin_pos_pairs,
        key=lambda pin_pos_pair: (
            -recent_dest_pin_bus_failure_count()[pin_pos_pair.dest_pin_id],
            pin_pos_pair,
        ),
    )

    bus_path: PartialBusPaths = {
        pin_pos_pair.dest_pin_id: None for pin_pos_pair in ordered_pin_pos_pairs
    }
    for pin_pos_pair in ordered_pin_pos_pairs:
        try:
            path = relaxed_bus_path(
                instance_regions=instance_regions,
                wire_regions=wire_regions,
                source_point=pin_pos_pair.source_pin_pos,
                dest_point=pin_pos_pair.dest_pin_pos,
                collision_cost=collision_cost,
            )
        except BussingError:
            record_dest_pin_bus_failure(pin_pos_pair.dest_pin_id)
            path = None
            # raise
            # No more paths will be attempted.
            # break

        bus_path[pin_pos_pair.dest_pin_id] = path
        if path is not None:
            wire_regions = wire_regions | wire_region(path)

    return bus_path


def mutated_relaxed_bus_paths(
    instance_regions: Region,
    pin_pos_pairs: set[PinPosPair],
    bus_paths: PartialBusPaths,
    collision_cost: float,
) -> PartialBusPaths:
    pin_pos_pair_to_update = choice(sorted(pin_pos_pairs))

    wire_regions = reduce(
        operator.or_,
        (
            wire_region(path)
            for dest_pin_id, path in bus_paths.items()
            if dest_pin_id != pin_pos_pair_to_update.dest_pin_id
            if path is not None
        ),
    )

    try:
        new_path = relaxed_bus_path(
            instance_regions=instance_regions,
            wire_regions=wire_regions,
            source_point=pin_pos_pair_to_update.source_pin_pos,
            dest_point=pin_pos_pair_to_update.dest_pin_pos,
            collision_cost=collision_cost,
        )
    except BussingError:
        # raise
        new_path = None

    return {**bus_paths, pin_pos_pair_to_update.dest_pin_id: new_path}


@dataclass
class HerdPathFindingProblem(LocalSearchProblem[PartialBusPaths]):
    netlist: Netlist
    placement: InstancePlacement
    collision_cost: float = 3

    @property  # type: ignore
    @first_id_cached
    def instance_regions(self) -> Region:
        return placement_region(self.netlist, self.placement).xz_padded(1)

    @property  # type: ignore
    @first_id_cached
    def pin_pos_pairs(self) -> set[PinPosPair]:
        return set(source_dest_pin_pos_pairs(self.netlist, self.placement))

    def random_solution(self) -> PartialBusPaths:
        return random_relaxed_bus_paths(
            self.instance_regions,
            self.pin_pos_pairs,
            collision_cost=self.collision_cost,
        )

    def mutated_solution(self, solution: PartialBusPaths) -> PartialBusPaths:
        return mutated_relaxed_bus_paths(
            self.instance_regions,
            self.pin_pos_pairs,
            solution,
            collision_cost=self.collision_cost,
        )

    def solution_cost(self, solution: PartialBusPaths) -> float:
        return collision_count(solution) + 1 + 8 * too_far_to_bus_count(solution)

    def good_enough(self, solution: PartialBusPaths) -> bool:
        return collision_count(solution) == 0


@first_id_cached
def dest_pin_relaxed_bus_path(
    netlist: Netlist,
    placement: InstancePlacement,
) -> PartialBusPaths:

    problem = HerdPathFindingProblem(
        netlist=netlist,
        placement=placement,
        collision_cost=3,
    )

    return sim_annealing_searched_solution(problem, total_rounds=150, restarts=1)
