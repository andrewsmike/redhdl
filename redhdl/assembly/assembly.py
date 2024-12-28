from dataclasses import dataclass
from math import log2
from pprint import pformat, pprint
from random import seed

from redhdl.assembly.placement import (
    InstancePlacement,
    OverlappingPlacementError,
    avg_instance_padding_blocks,
    mutated_placement,
    netlist_random_placement,
    placement_compactness_score,
    placement_schematic,
    placement_valid,
)
from redhdl.bussing.errors import BussingError
from redhdl.bussing.naive_bussing import (
    PartialPinBuses,
    avg_min_redstone_bus_len_score,
    bussed_placement_schematic,
    bussing_avg_length,
    bussing_avg_min_length,
    bussing_max_length,
    bussing_max_min_length,
    crossed_bus_pct,
    dest_pin_buses,
    misaligned_bus_pct,
    pin_pair_excessive_downwards_pct,
    pin_pair_interrupted_line_of_sight_pct,
    pin_pair_straight_up_pct,
    stride_aligned_bus_pct,
)
from redhdl.misc.caching import first_id_cached
from redhdl.netlist.netlist import InstanceId, Netlist
from redhdl.netlist.netlist_template import (
    InstanceConfig,
    PortSliceAssignments,
    example_instance_configs,
    example_port_slice_assignments,
    netlist_from_simple_spec,
)
from redhdl.search.local_search import (
    LocalSearchProblem,
    sim_annealing_searched_solution,
)
from redhdl.voxel.schematic import Schematic, interactive_display_schematic, save_schem


def _weighted_costs(
    costs: dict[str, float], weights: dict[str, float]
) -> dict[str, float]:
    return {
        heuristic_name: cost * weights[heuristic_name]
        for heuristic_name, cost in costs.items()
    }


@first_id_cached
def unbussable_placement_heuristic_costs(
    netlist: Netlist, placement: InstancePlacement
) -> dict[str, float]:
    return {
        "bussing_avg_min_length": log2(bussing_avg_min_length(netlist, placement) + 1),
        "bussing_max_min_length": log2(bussing_max_min_length(netlist, placement) + 1),
        "placement_has_collisions": 1 - placement_valid(netlist, placement),
        "placement_size": (
            1 + 1 / (placement_compactness_score(netlist, placement) + 10)
        ),
        "interrupted_pin_lines_of_sight": pin_pair_interrupted_line_of_sight_pct(
            netlist, placement
        ),
        "avg_missing_padding_blocks": (
            1 - avg_instance_padding_blocks(netlist, placement) / 5
        ),
        "shift_misaligned_bus": misaligned_bus_pct(netlist, placement),
        "stride_misaligned_bus": (1 - stride_aligned_bus_pct(netlist, placement)),
        "crossed_buses": crossed_bus_pct(netlist, placement),
        "excessive_downwards": pin_pair_excessive_downwards_pct(netlist, placement),
        "too_directly_above": pin_pair_straight_up_pct(netlist, placement),
        "min_redstone_cost": avg_min_redstone_bus_len_score(netlist, placement),
    }


_unbussable_placement_heuristic_weights: dict[str, float] = {
    "bussing_avg_min_length": 5,
    "bussing_max_min_length": 5,
    "placement_has_collisions": 10000,
    "placement_size": 20,
    "interrupted_pin_lines_of_sight": 30,
    "avg_missing_padding_blocks": 10,
    "shift_misaligned_bus": 150,
    "stride_misaligned_bus": 150,
    "crossed_buses": 60,
    "too_directly_above": 70,
    "excessive_downwards": 80,
    "min_redstone_cost": 20,
}


def unbussable_placement_cost(netlist: Netlist, placement: InstancePlacement) -> float:
    return sum(
        _weighted_costs(
            unbussable_placement_heuristic_costs(netlist, placement),
            _unbussable_placement_heuristic_weights,
        ).values()
    )


_bussable_placement_heuristic_weights: dict[str, float] = {
    "placement_has_collisions": 10000,
    "placement_size": 20,
    "interrupted_pin_lines_of_sight": 10,
    "avg_missing_padding_blocks": 10,
    "shift_misaligned_bus": 50,
    "stride_misaligned_bus": 35,
    "crossed_buses": 20,
    "too_directly_above": 20,
    "excessive_downwards": 30,
    "min_redstone_cost": 10,
    "bussing_avg_length": 20,
    "bussing_max_length": 20,
}


def bussable_placement_heuristic_costs(
    netlist: Netlist, placement: InstancePlacement, bussing: PartialPinBuses
) -> dict[str, float]:
    return {
        # collision_count(bussing) * 20
        "placement_has_collisions": 1 - placement_valid(netlist, placement),
        "placement_size": (
            1 + 1 / (placement_compactness_score(netlist, placement) + 10)
        ),
        "bussing_avg_length": bussing_avg_length(bussing),
        "bussing_max_length": bussing_max_length(bussing),
        "avg_missing_padding_blocks": (
            1 - avg_instance_padding_blocks(netlist, placement) / 5
        ),
        "shift_misaligned_bus": misaligned_bus_pct(netlist, placement),
        "stride_misaligned_bus": (1 - stride_aligned_bus_pct(netlist, placement)),
        "crossed_buses": crossed_bus_pct(netlist, placement),
        "too_directly_above": pin_pair_straight_up_pct(netlist, placement),
        "excessive_downwards": pin_pair_excessive_downwards_pct(netlist, placement),
    }


def bussable_placement_cost(
    netlist: Netlist, placement: InstancePlacement, bussing: PartialPinBuses
) -> float:
    return sum(
        _weighted_costs(
            bussable_placement_heuristic_costs(netlist, placement, bussing),
            _bussable_placement_heuristic_weights,
        ).values()
    )


@dataclass
class HeuristicBussingPlacementProblem(LocalSearchProblem[InstancePlacement]):
    netlist: Netlist
    initial_placement: InstancePlacement
    mutations_per_step: int = 2

    def random_solution(self) -> InstancePlacement:
        return self.initial_placement

    def mutated_solution(self, solution: InstancePlacement) -> InstancePlacement:
        for _attempt_index in range(self.mutations_per_step):
            solution = mutated_placement(solution)

        return solution

    def solution_cost(self, solution: InstancePlacement) -> float:
        return unbussable_placement_cost(self.netlist, solution)


PCT_RANDOM_PLACEMENTS = 0.1


def mutated_unbussable_placement(
    netlist: Netlist, placement: InstancePlacement, total_rounds: int
) -> InstancePlacement:
    """Unbussable placement mutation: Optimize placement / pin distance / line of sight a few steps."""
    problem = HeuristicBussingPlacementProblem(netlist, initial_placement=placement)
    next_placement = sim_annealing_searched_solution(
        problem,
        total_rounds=total_rounds,
        restarts=2,
    )
    if next_placement == placement:  # Sim annealing didn't like the results.
        print("No improvement.")
        for _attempt_index in range(3):
            placement = mutated_placement(placement)

        return placement
    else:
        return next_placement


def mutated_bussable_placement(
    netlist: Netlist,
    placement: InstancePlacement,
    bussing: PartialPinBuses,
) -> InstancePlacement:
    return mutated_placement(mutated_placement(placement))


@dataclass
class BussingPlacementProblem(LocalSearchProblem[InstancePlacement]):
    netlist: Netlist
    debug: bool = False
    max_reasonable_unbussed_cost: int = 70
    random_placement_opt_steps: int = 256
    mutation_placement_opt_steps: int = 64
    max_bussing_steps: int = 25

    def random_solution(self) -> InstancePlacement:
        return mutated_unbussable_placement(
            self.netlist,
            netlist_random_placement(self.netlist),
            total_rounds=self.random_placement_opt_steps,
        )

    def mutated_solution(self, solution: InstancePlacement) -> InstancePlacement:
        try:
            # This call should be cached and return (or raise) immediately.
            bussing = self.solution_dest_pin_buses(solution)
        except BussingError:
            return mutated_unbussable_placement(
                self.netlist,
                solution,
                total_rounds=self.mutation_placement_opt_steps,  # 2**10,
            )
        else:
            return mutated_bussable_placement(self.netlist, solution, bussing)

    def solution_dest_pin_buses(self, solution: InstancePlacement):
        unbussable_cost = unbussable_placement_cost(self.netlist, solution)
        if unbussable_cost > self.max_reasonable_unbussed_cost:
            raise BussingError(
                "This looks like a terrible placement. Not attempting to bus."
            )

        return dest_pin_buses(self.netlist, solution, self.max_bussing_steps)

    def good_enough(self, solution: InstancePlacement) -> bool:
        try:
            self.solution_dest_pin_buses(solution)
            return True
        except (OverlappingPlacementError, BussingError):
            return False

    def solution_cost(self, solution: InstancePlacement) -> float:
        print("Placement:")
        pprint(dict(solution))

        unbussable_cost = unbussable_placement_cost(self.netlist, solution)
        bussable = False
        try:
            if unbussable_cost > self.max_reasonable_unbussed_cost:
                return 100_000 + unbussable_cost

            bussing = dest_pin_buses(self.netlist, solution)
            bussable = True
            return bussable_placement_cost(self.netlist, solution, bussing)
        except BussingError as e:
            return 100_000 + unbussable_cost

        finally:
            if bussable:
                bussable_str = "Bussable"
                costs = bussable_placement_heuristic_costs(
                    self.netlist, solution, bussing
                )
                weights = _bussable_placement_heuristic_weights
            else:
                bussable_str = "Unbussable"
                costs = unbussable_placement_heuristic_costs(self.netlist, solution)
                weights = _unbussable_placement_heuristic_weights

            weighted_costs = _weighted_costs(costs, weights)

            desc = (
                f"{bussable_str} cost: {sum(weighted_costs.values())}\n"
                + "Factors:\n"
                + pformat(weighted_costs)
            )

            try:
                interactive_display_schematic(
                    placement_schematic(self.netlist, solution),
                    "current_placement",
                    desc,
                )
            except OverlappingPlacementError:
                print("Failed to save schematic: Overlapping regions.")


def schematic_placement_from_netlist(
    netlist: Netlist,
    debug: bool = False,
) -> tuple[Schematic, InstancePlacement]:
    def solution_schematic(placement: InstancePlacement) -> Schematic:
        pin_buses = dest_pin_buses(netlist, placement)
        # print(f"Collision count: {collision_count(pin_buses)}")
        return bussed_placement_schematic(netlist, placement, pin_buses)

    # TOTAL_ROUNDS = 1_000
    TOTAL_ROUNDS = 150

    def checkpoint(round: int, placement: InstancePlacement, cost: float):
        path = f"build/checkpoints/output_{round}.schem"
        try:
            schem = solution_schematic(placement)
            save_schem(schem, path)

        except OverlappingPlacementError as e:
            print(
                f"[{round + 1}/{TOTAL_ROUNDS}] Failed to checkpoint due to overlapping instances: {e}"
            )
        except BussingError as e:
            print(
                f"[{round + 1}/{TOTAL_ROUNDS}] Failed to checkpoint due to bussing error: {e}"
            )

    seed(0xDEADBEEF)
    placement_problem = BussingPlacementProblem(netlist, debug=debug)
    placement = sim_annealing_searched_solution(
        placement_problem,
        total_rounds=TOTAL_ROUNDS,
        show_progressbar=True,
        rounds_per_print=1,
        rounds_per_checkpoint=1,
        checkpoint_func=checkpoint,
    )

    print(f"Best cost: {placement_problem.solution_cost(placement)}")

    try:
        return solution_schematic(placement), placement
    except BaseException:
        import pdb

        pdb.set_trace()
        raise


def assembled_circuit_schem(
    instance_config: dict[InstanceId, InstanceConfig],
    port_slice_assignments: PortSliceAssignments,
    debug: bool = False,
) -> Schematic:
    netlist = netlist_from_simple_spec(
        instance_config=instance_config,
        port_slice_assignments=port_slice_assignments,
        output_port_bitwidths={"out": 8},
    )
    return schematic_placement_from_netlist(netlist, debug=debug)[0]


def main():
    schem = assembled_circuit_schem(
        example_instance_configs,
        example_port_slice_assignments,
        debug=False,
    )
    save_schem(schem, "output.schem")


if __name__ == "__main__":
    try:
        main()
    except BaseException:
        raise
