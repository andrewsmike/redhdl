from functools import reduce
import operator

from frozendict import frozendict
from visualize_bussing import display_step

from redhdl.assembly.placement import (
    placement_region,
    source_dest_pin_pos_pairs,
)
from redhdl.bussing.naive_bussing import (
    PinBuses,
    bussed_placement_schematic,
)
from redhdl.bussing.redstone_bussing import (
    RedstoneBussing,
    redstone_bussing_details,
)
from redhdl.netlist.netlist_template import (
    example_instance_configs,
    example_port_slice_assignments,
    netlist_from_simple_spec,
)
from redhdl.voxel.region import PointRegion, Pos, display_regions
from redhdl.voxel.schematic import save_schem


def main():
    netlist = netlist_from_simple_spec(
        instance_config=example_instance_configs,
        example_port_slice_assignments=example_port_slice_assignments,
        output_port_bitwidths={"out": 8},
    )

    example_placements = {
        "square-ish": frozendict(
            {
                "not_a": (Pos(24, 20, 22), "north"),
                "not_b": (Pos(25, 15, 15), "north"),
                "and": (Pos(24, 15, 23), "north"),
                "not_out": (Pos(25, 17, 16), "north"),
            }
        ),
        "square": frozendict(
            {
                "not_a": (Pos(24, 20, 15), "north"),
                "not_b": (Pos(24, 15, 15), "north"),
                "and": (Pos(24, 15, 24), "north"),
                "not_out": (Pos(24, 17, 30), "north"),
            }
        ),
    }

    placement_name = "square"
    interesting_source_pin_id = (("not_a", "out"), 0)  # None

    placement = example_placements[placement_name]

    instances_region = placement_region(netlist, placement).xz_padded(1)

    display_regions(*instances_region.subregions)

    dest_pin_buses: PinBuses = {}
    for pin_pos_pair in source_dest_pin_pos_pairs(netlist, placement):
        other_buses = reduce(operator.or_, dest_pin_buses.values(), RedstoneBussing())
        (
            bussing,
            problem,
            states,
            steps,
            costs,
            algo_steps,
        ) = redstone_bussing_details(
            start_pos=pin_pos_pair.source_pin_pos,
            end_pos=pin_pos_pair.dest_pin_pos,
            start_xz_dir=pin_pos_pair.source_pin_facing,
            end_xz_dir=pin_pos_pair.dest_pin_facing,
            instance_points=instances_region.points,
            other_buses=other_buses,
            max_steps=2500,
        )

        expansion_steps = [
            step.step for step in algo_steps if step.algo_action == "expanding_step"
        ]

        debug = pin_pos_pair.source_pin_id == interesting_source_pin_id

        if debug:
            for expansion_step in expansion_steps:
                min_x, min_y, min_z = instances_region.min_pos
                max_x, max_y, max_z = instances_region.max_pos
                display_step(
                    expansion_step,
                    problem,
                    x_range=(min_x, max_x + 1),
                    y_range=(min_z, max_z + 1),
                )
                try:
                    input()
                except KeyboardInterrupt:
                    import pdb

                    pdb.set_trace()

            import pdb

            pdb.set_trace()

        if bussing is None:
            raise ValueError(f"Failed to bus {pin_pos_pair.dest_pin_id}.")

        dest_pin_buses[pin_pos_pair.dest_pin_id] = bussing

    display_regions(
        *instances_region.subregions,
        *(
            PointRegion(frozenset(bus.element_blocks))
            for bus in dest_pin_buses.values()
        ),
    )

    schem = bussed_placement_schematic(netlist, placement, dest_pin_buses)

    save_schem(
        schem,
        f"output_schems/bussed_{placement_name}_placement.schem",
    )

    import pdb

    pdb.set_trace()


if __name__ == "__main__":
    main()
