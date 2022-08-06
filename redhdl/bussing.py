from dataclasses import dataclass
from functools import wraps
from typing import Iterable

from frozendict import frozendict

from redhdl.instances import RepeaterPort
from redhdl.netlist import Netlist, PinId, PinIdSequence
from redhdl.path_search import (
    PathSearchProblem,
    SearchError,
    a_star_iddfs_searched_solution,
)
from redhdl.placement import InstancePlacement, placement_region, placement_schematic
from redhdl.positional_data import PositionalData
from redhdl.region import (
    PointRegion,
    Pos,
    PositionSequence,
    Region,
    direction_unit_pos,
    xz_directions,
)
from redhdl.schematic import Block, Schematic


@dataclass
class PathFindingProblem(PathSearchProblem[Pos, Pos]):
    start_point: Pos
    stop_point: Pos
    blocked_regions: Region

    def initial_state(self) -> Pos:
        return self.start_point

    def state_actions(self, state: Pos) -> list[Pos]:
        return [
            next_pos
            for unit_pos in direction_unit_pos.values()
            if (
                ((next_pos := unit_pos + state) == self.stop_point)
                or (next_pos not in self.blocked_regions)
            )
        ]

    def state_action_result(self, state: Pos, action: Pos) -> Pos:
        return action

    def state_action_cost(self, state: Pos, action: Pos) -> float:
        return 1

    def is_goal_state(self, state: Pos) -> bool:
        return state == self.stop_point

    def min_distance(self, state: Pos) -> float:
        return (state - self.stop_point).l1()


class BussingError(BaseException):
    pass


def bus_path(
    blocked_regions: Region,
    source_port: Pos,
    dest_port: Pos,
) -> list[Pos]:
    problem = PathFindingProblem(
        start_point=source_port,
        stop_point=dest_port,
        blocked_regions=blocked_regions,
    )

    try:
        return [source_port] + a_star_iddfs_searched_solution(problem, max_steps=4_000)
    except SearchError as e:
        raise BussingError(str(e))


def placement_pin_seq_points(
    netlist: Netlist,
    pin_id_seq: PinIdSequence,
    placement: InstancePlacement,
) -> PositionSequence:
    """The position sequence corresponding to the given PinIdSequence in a given placement."""
    port = netlist.port(pin_id_seq.port_id)

    if not isinstance(port, RepeaterPort):
        raise ValueError(
            "pin_id_seq_points() doesn't support anything but RepeaterPorts."
        )

    base_pin_points = (port.positions & pin_id_seq.slice) + Pos(0, 1, 0)

    # Offset back/forward for inputs/outputs.
    pin_points = {
        "output": base_pin_points + direction_unit_pos[port.facing],
        "input": base_pin_points - direction_unit_pos[port.facing],
    }[port.port_type]

    instance_id, _ = pin_id_seq.port_id
    instance_pos, instance_dir = placement[instance_id]

    return pin_points.y_rotated(xz_directions.index(instance_dir)) + instance_pos


@dataclass
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

            for (source_pin_id, source_pin_pos), (dest_pin_id, dest_pin_pos) in zip(
                zip(network.input_pin_id_seq.slice, source_pin_points),
                zip(dest_pin_id_seq.slice, dest_pin_points),
            ):

                yield PinPosPair(
                    source_pin_id=(network.input_pin_id_seq.port_id, source_pin_id),
                    source_pin_pos=source_pin_pos,
                    dest_pin_id=(dest_pin_id_seq.port_id, dest_pin_id),
                    dest_pin_pos=dest_pin_pos,
                )


def first_id_cached(func):
    func._cache = {}

    @wraps(func)
    def wrapper(id_obj, *args, **kwargs):
        key = (id(id_obj), tuple(args), tuple(sorted(kwargs.items())))
        if key not in func._cache:
            func._cache[key] = func(id_obj, *args, **kwargs)
        return func._cache[key]

    return wrapper


@first_id_cached
def dest_pin_bus_path(
    netlist: Netlist,
    placement: InstancePlacement,
) -> dict[PinId, list[Pos]]:
    blocks_region = placement_region(netlist, placement).xz_padded(1)

    dest_pin_bus_path: dict[PinId, list[Pos]] = {}
    for pin_pos_pair in source_dest_pin_pos_pairs(netlist, placement):
        path = bus_path(
            blocked_regions=blocks_region,
            source_port=pin_pos_pair.source_pin_pos,
            dest_port=pin_pos_pair.dest_pin_pos,
        )
        dest_pin_bus_path[pin_pos_pair.dest_pin_id] = path
        blocks_region = blocks_region | PointRegion(
            frozenset(
                point  # + direction_unit_pos[xz_dir] + y_offset
                for point in path
                # for xz_dir in xz_directions
                # for y_offset in (Pos(0, 0, 0), Pos(0, 1, 0))
            )
        )

    return dest_pin_bus_path


def bus_trace_pos_blocks(bus_paths: dict[PinId, list[Pos]]) -> PositionalData[Block]:
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
    bus_paths: dict[PinId, list[Pos]],
) -> Schematic:
    schem = placement_schematic(netlist, placement)
    schem.pos_blocks |= bus_trace_pos_blocks(bus_paths)
    return schem


def bussing_cost(bus_paths: dict[PinId, list[Pos]]) -> float:
    return (
        sum(len(bus_points) for bus_points in bus_paths.values()) / len(bus_paths) / 3
    )


def bussing_min_cost(netlist: Netlist, placement: InstancePlacement) -> float:
    l1s = [
        (pin_pos_pair.dest_pin_pos - pin_pos_pair.source_pin_pos).l1()
        for pin_pos_pair in source_dest_pin_pos_pairs(netlist, placement)
    ]
    return sum(l1s) / len(l1s) / 3
