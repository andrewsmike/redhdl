from pprint import pprint

from frozendict import frozendict
from pytest import mark

from redhdl.assembly.assembly import (
    _unbussable_placement_heuristic_weights,
    _weighted_costs,
    unbussable_placement_heuristic_costs,
)
from redhdl.assembly.placement import display_placement
from redhdl.netlist.netlist_template import (
    example_instance_configs,
    example_port_slice_assignments,
    netlist_from_simple_spec,
)
from redhdl.voxel.region import Pos

"""
Vertically and horizontally misaligned:

Z  [(28, 43)]

 33335  61115
 3333    11164444
 33***25611154444
 33**22  11164444
 33***25611154444
 33**22  11164444
 33***25611154444
 33**22  11164444
 33***25611154444
 33**22  11164444
 33***25611154444
 33**22  11164444
 33***25611154444
 33**22  11164444
 33***25611154444
   2222     64444
   22225
                  X  [(31, 47)]

   22225    64444
   2222      4444
        6111
         1115
 33335  6111
 3333    111
                  X  [(22, 27)]
{1: 'and', 2: 'not_a', 3: 'not_b', 4: 'not_out', 5: 'outputs', 6: 'inputs'}
"""

example_placements = {
    "vert_horiz_misaligned": frozendict(
        {
            "and": (Pos(8, 0, 2), "east"),
            "not_a": (Pos(2, 4, 0), "east"),
            "not_b": (Pos(0, 0, 2), "east"),
            "not_out": (Pos(12, 4, 1), "east"),
        }
    ),
    "vert_misaligned": frozendict(
        {
            "and": (Pos(8, 0, 0), "east"),
            "not_a": (Pos(2, 4, 0), "east"),
            "not_b": (Pos(0, 0, 0), "east"),
            "not_out": (Pos(12, 4, 0), "east"),
        }
    ),
}

expected_heuristic_costs = {
    "vert_horiz_misaligned": {
        "avg_missing_padding_blocks": 0.19999999999999996,
        "bussing_avg_min_length": 2.321928094887362,
        "bussing_max_min_length": 2.584962500721156,
        "crossed_buses": 0.0,
        "excessive_downwards": 0.0,
        "interrupted_pin_lines_of_sight": 0.0,
        "min_redstone_cost": 0.33170401355533746,
        "placement_has_collisions": 0,
        "placement_size": 0.9615384615384616,
        "shift_misaligned_bus": 0.16278710815035494,
        "stride_misaligned_bus": 0.0,
        "too_directly_above": 0.0,
    },
    "vert_misaligned": {
        "avg_missing_padding_blocks": 0.19999999999999996,
        "bussing_avg_min_length": 2.0,
        "bussing_max_min_length": 2.0,
        "crossed_buses": 0.0,
        "excessive_downwards": 0.06666666666666667,
        "interrupted_pin_lines_of_sight": 0.0,
        "min_redstone_cost": 0.31748463161949253,
        "placement_has_collisions": 0,
        "placement_size": 0.9583333333333334,
        "shift_misaligned_bus": 0.0,
        "stride_misaligned_bus": 0.0,
        "too_directly_above": 0.3333333333333333,
    },
}


@mark.parametrize("placement_name,placement", sorted(example_placements.items()))
def test_unbussable_heuristics(placement_name, placement):
    netlist = netlist_from_simple_spec(
        instance_config=example_instance_configs,
        port_slice_assignments=example_port_slice_assignments,
        output_port_bitwidths={"out": 8},
    )

    heuristic_costs = unbussable_placement_heuristic_costs(netlist, placement)

    print(f"Placement {placement_name}:")
    display_placement(netlist, placement)
    print()

    print(f"[{placement_name}] Unweighted costs:")
    pprint(heuristic_costs)
    print()

    print(f"[{placement_name}] Weighted costs:")
    pprint(
        _weighted_costs(
            heuristic_costs,
            _unbussable_placement_heuristic_weights,
        )
    )

    assert expected_heuristic_costs[placement_name] == heuristic_costs
