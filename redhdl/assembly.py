from dataclasses import dataclass
from math import log2
from random import seed

from redhdl.bussing import BussingError
from redhdl.local_search import LocalSearchProblem, sim_annealing_searched_solution
from redhdl.naive_bussing import (
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
    stride_aligned_bus_pct,
)
from redhdl.netlist import InstanceId, Netlist
from redhdl.netlist_template import (
    InstanceConfig,
    NetworkSpecs,
    example_instance_configs,
    example_network_specs,
    netlist_from_simple_spec,
)
from redhdl.placement import (
    InstancePlacement,
    avg_instance_buffer_blocks,
    display_placement,
    mutated_placement,
    netlist_random_placement,
    placement_compactness_score,
    placement_valid,
)
from redhdl.schematic import Schematic, save_schem


def unbussable_placement_cost(netlist: Netlist, placement: InstancePlacement) -> float:
    return (
        log2(bussing_avg_min_length(netlist, placement)) * 5
        + log2(bussing_max_min_length(netlist, placement)) * 5
        + 20 / (placement_compactness_score(netlist, placement) + 10)
        + pin_pair_interrupted_line_of_sight_pct(netlist, placement) * 10
        + (6 - avg_instance_buffer_blocks(netlist, placement)) * 100
        + misaligned_bus_pct(netlist, placement) * 50
        + (1 - stride_aligned_bus_pct(netlist, placement)) * 10
        + crossed_bus_pct(netlist, placement) * 40
        + pin_pair_excessive_downwards_pct(netlist, placement) * 40
        + avg_min_redstone_bus_len_score(netlist, placement) * 10
    )


def bussable_placement_cost(
    netlist: Netlist, placement: InstancePlacement, bussing: PartialPinBuses
) -> float:
    return (
        # collision_count(bussing) * 20
        -placement_compactness_score(netlist, placement)
        + bussing_avg_length(bussing) / 6
        + bussing_max_length(bussing) / 6
        + (6 - avg_instance_buffer_blocks(netlist, placement)) * 5
        + misaligned_bus_pct(netlist, placement) * 10
        + pin_pair_excessive_downwards_pct(netlist, placement) * 40
    )


@dataclass
class HeuristicBussingPlacementProblem(LocalSearchProblem[InstancePlacement]):
    netlist: Netlist
    initial_placement: InstancePlacement
    mutations_per_step: int = 2

    def random_solution(self) -> InstancePlacement:
        return self.initial_placement

    def mutated_solution(self, solution: InstancePlacement) -> InstancePlacement:
        for i in range(self.mutations_per_step):
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
        for i in range(3):
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

    def random_solution(self) -> InstancePlacement:
        return mutated_unbussable_placement(
            self.netlist,
            netlist_random_placement(self.netlist),
            total_rounds=8192,
        )

    def mutated_solution(self, solution: InstancePlacement) -> InstancePlacement:
        try:
            unbussable_cost = unbussable_placement_cost(self.netlist, solution)
            if unbussable_cost > 275:
                raise BussingError(
                    "This looks like a terrible placement. Trying again."
                )

            # This call should be cached and return (or raise) immediately.
            bussing = dest_pin_buses(self.netlist, solution)
        except BussingError:
            return mutated_unbussable_placement(
                self.netlist,
                solution,
                total_rounds=2**14,
            )
        else:
            return mutated_bussable_placement(self.netlist, solution, bussing)

    def solution_cost(self, solution: InstancePlacement) -> float:
        display_placement(self.netlist, solution)

        if not placement_valid(self.netlist, solution):
            return 1_000_000

        unbussable_cost = unbussable_placement_cost(self.netlist, solution)
        if unbussable_cost > 275:
            return 100_000 + unbussable_cost
        try:
            bussing = dest_pin_buses(self.netlist, solution)
        except BussingError as e:
            print(f"Unbussable! Error: {e}")
            return 100_000 + unbussable_cost
        else:
            print("Bussable!")  # Collision count: {collision_count(bussing)}")
            return bussable_placement_cost(self.netlist, solution, bussing)


def assembled_circuit_schem(
    instance_config: dict[InstanceId, InstanceConfig],
    network_specs: NetworkSpecs,
) -> Schematic:
    netlist = netlist_from_simple_spec(
        instance_config=instance_config,
        network_specs=network_specs,
        output_port_bitwidths={"out": 8},
    )

    def solution_schematic(placement: InstancePlacement) -> Schematic:
        pin_buses = dest_pin_buses(netlist, placement)
        # print(f"Collision count: {collision_count(pin_buses)}")
        return bussed_placement_schematic(netlist, placement, pin_buses)

    # TOTAL_ROUNDS = 1_000
    TOTAL_ROUNDS = 150

    def checkpoint(round: int, placement: InstancePlacement, cost: float):
        path = f"checkpoints/output_{round}.schem"
        print(
            f"[{round + 1}/{TOTAL_ROUNDS}] Saving solution with cost {cost} to {path}..."
        )
        try:
            from pprint import pprint

            print("Placement:")
            pprint(placement)
            schem = solution_schematic(placement)
            save_schem(schem, path)
            # from pprint import pprint
            # pprint(schem)
        except BussingError as e:
            print(f"Failed to save due to bussing error: {e}")

    seed(0xDEADBEEF)
    placement_problem = BussingPlacementProblem(netlist)
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
        return solution_schematic(placement)
    except BaseException:
        import pdb

        pdb.set_trace()
        raise


def main():
    schem = assembled_circuit_schem(
        example_instance_configs,
        example_network_specs,
    )
    save_schem(schem, "output.schem")


if __name__ == "__main__":
    try:
        main()
    except BaseException:
        raise
