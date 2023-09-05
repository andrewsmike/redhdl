from functools import reduce
from math import log2
import operator

from redhdl.assembly.placement import (
    InstancePlacement,
    placement_pin_seq_points,
    placement_region,
    placement_schematic,
    source_dest_pin_id_seq_pairs,
    source_dest_pin_pos_pairs,
)
from redhdl.assembly.redstone_bussing import (
    RedstoneBussing,
    min_redstone_bussing_cost,
    redstone_bussing,
)
from redhdl.misc.caching import first_id_cached
from redhdl.netlist.netlist import Netlist, PinId
from redhdl.voxel.region import CompositeRegion, Pos, RectangularPrism
from redhdl.voxel.schematic import Schematic

PinBuses = dict[PinId, RedstoneBussing]
PartialPinBuses = dict[PinId, RedstoneBussing | None]


@first_id_cached
def dest_pin_buses(
    netlist: Netlist,
    placement: InstancePlacement,
) -> PinBuses:
    instances_region = placement_region(netlist, placement).xz_padded(1)
    instance_region_points = instances_region.region_points()

    dest_pin_buses: PinBuses = {}
    for pin_pos_pair in source_dest_pin_pos_pairs(netlist, placement):
        other_buses = reduce(operator.or_, dest_pin_buses.values(), RedstoneBussing())
        try:
            bussing = redstone_bussing(
                start_pos=pin_pos_pair.source_pin_pos,
                end_pos=pin_pos_pair.dest_pin_pos,
                start_xz_dir=pin_pos_pair.source_pin_facing,
                end_xz_dir=pin_pos_pair.dest_pin_facing,
                instance_points=instance_region_points,
                other_buses=other_buses,
                max_steps=2_048,
            )
        except BaseException:
            from time import time

            from redhdl.schematic import save_schem

            save_schem(
                bussed_placement_schematic(netlist, placement, dest_pin_buses),
                f"checkpoints/failed_{time()}.schem",
            )
            raise

        dest_pin_buses[pin_pos_pair.dest_pin_id] = bussing

    return dest_pin_buses


def bussed_placement_schematic(
    netlist: Netlist,
    placement: InstancePlacement,
    pin_buses: PinBuses,
) -> Schematic:
    schem = placement_schematic(netlist, placement)
    for bus in pin_buses.values():
        schem |= bus.schem()

    return schem


def bussing_avg_length(pin_buses: PartialPinBuses) -> float:
    successful_bus_path_lengths = [
        len(bus.element_sig_strengths) for bus in pin_buses.values() if bus is not None
    ]
    return sum(successful_bus_path_lengths) / len(successful_bus_path_lengths)


def bussing_max_length(pin_buses: PartialPinBuses) -> float:
    successful_bus_path_lengths = [
        len(bus.element_sig_strengths) for bus in pin_buses.values() if bus is not None
    ]
    return max(successful_bus_path_lengths)


def bussing_avg_min_length(netlist: Netlist, placement: InstancePlacement) -> float:
    l1s = [
        (pin_pos_pair.dest_pin_pos - pin_pos_pair.source_pin_pos).l1()
        for pin_pos_pair in source_dest_pin_pos_pairs(netlist, placement)
    ]
    return sum(l1s) / len(l1s)


def bussing_max_min_length(netlist: Netlist, placement: InstancePlacement) -> float:
    l1s = [
        (pin_pos_pair.dest_pin_pos - pin_pos_pair.source_pin_pos).l1()
        for pin_pos_pair in source_dest_pin_pos_pairs(netlist, placement)
    ]
    return max(l1s)


def pin_pair_interrupted_line_of_sight_pct(
    netlist: Netlist, placement: InstancePlacement
) -> float:
    instance_regions = placement_region(netlist, placement)

    return sum(
        1
        for pin_pos_pair in source_dest_pin_pos_pairs(netlist, placement)
        if RectangularPrism(
            pin_pos_pair.source_pin_pos, pin_pos_pair.dest_pin_pos
        ).intersects(instance_regions)
    ) / len(list(source_dest_pin_pos_pairs(netlist, placement)))


def pin_pair_excessive_downwards_pct(
    netlist: Netlist, placement: InstancePlacement
) -> float:
    excessively_downwards_pins = 0.0
    denom = 0.0
    for pin_pos_pair in source_dest_pin_pos_pairs(netlist, placement):
        denom += 1
        delta = pin_pos_pair.dest_pin_pos - pin_pos_pair.source_pin_pos
        delta_horiz_dist = abs(delta).xz_pos().l1()
        if delta.y < 0 and delta_horiz_dist < abs(delta.y):
            excessively_downwards_pins += 0.2
        elif delta.y < 0 and delta_horiz_dist < abs(delta.y):
            excessively_downwards_pins += 1

    return excessively_downwards_pins / denom


def pin_pair_straight_up_pct(netlist: Netlist, placement: InstancePlacement) -> float:
    straight_up_pins = 0.0
    denom = 0.0
    for pin_pos_pair in source_dest_pin_pos_pairs(netlist, placement):
        denom += 1
        delta = pin_pos_pair.dest_pin_pos - pin_pos_pair.source_pin_pos
        delta_horiz_dist = abs(delta).xz_pos().l1()
        if delta.y > 0 and delta_horiz_dist == 0:
            straight_up_pins += 1

    return straight_up_pins / denom


def misaligned_bus_pct(netlist: Netlist, placement: InstancePlacement) -> float:
    """
    The percent of port pairs that are shift-misaligned with each other.

    Shifting as an expensive and complicated operation. If ports have the same
    alignment, reward placements that exactly align them.

    Output range [0, 1], with 1 being "all _very_ misaligned" and 0 being "none misaligned".
    """
    misaligned_bus_count = 0.0
    bus_count = 0

    for source_pin_id_seq, dest_pin_id_seq in source_dest_pin_id_seq_pairs(netlist):
        bus_count += 1  # Denominator.

        source_pin_points = placement_pin_seq_points(
            netlist, source_pin_id_seq, placement
        )
        dest_pin_points = placement_pin_seq_points(netlist, dest_pin_id_seq, placement)

        if source_pin_points.step != dest_pin_points.step:
            continue

        delta = dest_pin_points[0] - source_pin_points[0]

        stride_direction_error = (delta * source_pin_points.step).l1()

        misaligned_bus_count += (min(log2(stride_direction_error + 1), 8)) / 8

    return misaligned_bus_count / bus_count


def stride_aligned_bus_pct(netlist: Netlist, placement: InstancePlacement) -> float:
    """
    The percent of buses that have the same input/output strides.

    This is a pretty decent metric of whether two buses are facing each other nicely.

    Output range [0, 1], where 0 is "no bus pairs are stride-aligned" and 1 is
    "all bus pairs are stride-aligned".
    """
    stride_aligned_bus_count = 0
    bus_count = 0

    for source_pin_id_seq, dest_pin_id_seq in source_dest_pin_id_seq_pairs(netlist):
        bus_count += 1  # Denominator.

        source_pin_points = placement_pin_seq_points(
            netlist, source_pin_id_seq, placement
        )
        dest_pin_points = placement_pin_seq_points(netlist, dest_pin_id_seq, placement)

        stride_aligned_bus_count += source_pin_points.step == dest_pin_points.step

    return stride_aligned_bus_count / bus_count


def crossed_bus_pct(netlist: Netlist, placement: InstancePlacement) -> float:
    """
    The percent of buses whose line-of-sight crosess through other buses' lines-of-sight.

    This placement would have a 50% crossed_bus_pct:

    A-` /-C--E
       X
    B-/ `-D--F

    This is a heurisic measure today, based on bounding boxes.
    A real version would be more precise.

    Output range is [0, 1], where 0 is "no buses' lines-of-sight collide", and 1 is
    "all buses' lines-of-sight collide with at least one other bus's line-of-sight".
    """
    port_pair_region = {}

    for source_pin_id_seq, dest_pin_id_seq in source_dest_pin_id_seq_pairs(netlist):
        source_pin_points = placement_pin_seq_points(
            netlist, source_pin_id_seq, placement
        )
        dest_pin_points = placement_pin_seq_points(netlist, dest_pin_id_seq, placement)

        relevant_points = {
            source_pin_points.start,
            dest_pin_points.stop,
            source_pin_points.start,
            dest_pin_points.stop,
        }

        source_port_id = source_pin_id_seq.port_id
        dest_port_id = dest_pin_id_seq.port_id

        port_pair_region[(source_port_id, dest_port_id)] = RectangularPrism(
            Pos.elem_min(*relevant_points),
            Pos.elem_max(*relevant_points),
        )

    return sum(
        region.intersects(
            other_regions := CompositeRegion(
                tuple(
                    other_region
                    for other_port_pair, other_region in port_pair_region.items()
                    if other_port_pair != port_pair
                )
            )
        )
        for port_pair, region in port_pair_region.items()
    ) / len(port_pair_region)


@first_id_cached
def too_far_to_bus_count(pin_buses: PartialPinBuses) -> int:
    return sum(bus is None for bus in pin_buses.values())


@first_id_cached
def avg_min_redstone_bus_len_score(
    netlist: Netlist, placement: InstancePlacement
) -> float:
    """
    Output range [0, 1], where 0 is "buses literally go one space" and 1 is
    "buses require >=128 cost on average".
    """
    min_costs = [
        min_redstone_bussing_cost(
            start_pos=pin_pos_pair.source_pin_pos,
            end_pos=pin_pos_pair.dest_pin_pos,
            start_xz_dir=pin_pos_pair.source_pin_facing,
            end_xz_dir=pin_pos_pair.dest_pin_facing,
        )
        for pin_pos_pair in source_dest_pin_pos_pairs(netlist, placement)
    ]
    avg_min_cost = sum(min_costs) / len(min_costs) if min_costs else 0

    return min(
        1,
        log2(avg_min_cost + 1) / 7,
    )
