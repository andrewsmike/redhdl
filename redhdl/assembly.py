from dataclasses import dataclass
from random import seed

from redhdl.bussing import BussingError
from redhdl.local_search import LocalSearchProblem, sim_annealing_searched_solution
from redhdl.naive_bussing import (
    PartialBusPaths,
    bussed_placement_schematic,
    bussing_avg_length,
    bussing_max_length,
    bussing_min_avg_length,
    bussing_min_max_length,
    collision_count,
    dest_pin_relaxed_bus_path,
    interrupted_pin_line_of_sight_count,
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
    display_placement,
    instance_buffer_blocks,
    mutated_placement,
    netlist_random_placement,
    placement_compactness_score,
    placement_valid,
)
from redhdl.schematic import Schematic, save_schem


def unbussable_placement_cost(netlist: Netlist, placement: InstancePlacement) -> float:
    return (
        bussing_min_avg_length(netlist, placement) / 2
        + bussing_min_max_length(netlist, placement) / 2
        - placement_compactness_score(netlist, placement)
        + interrupted_pin_line_of_sight_count(netlist, placement) / 2
        + (20 * 4 - instance_buffer_blocks(netlist, placement) * 20)
    )


def bussable_placement_cost(
    netlist: Netlist, placement: InstancePlacement, bussing: PartialBusPaths
) -> float:
    return (
        collision_count(bussing) * 20
        - placement_compactness_score(netlist, placement)
        + bussing_avg_length(bussing) / 6
        + bussing_max_length(bussing) / 6
    )


@dataclass
class HeuristicBussingPlacementProblem(LocalSearchProblem[InstancePlacement]):
    netlist: Netlist
    initial_placement: InstancePlacement

    def random_solution(self) -> InstancePlacement:
        return self.initial_placement

    def mutated_solution(self, solution: InstancePlacement) -> InstancePlacement:
        return mutated_placement(solution)

    def solution_cost(self, solution: InstancePlacement) -> float:
        return unbussable_placement_cost(self.netlist, solution)


def mutated_unbussable_placement(
    netlist: Netlist, placement: InstancePlacement
) -> InstancePlacement:
    """Unbussable placement mutation: Optimize placement / pin distance / line of sight a few steps."""
    problem = HeuristicBussingPlacementProblem(netlist, initial_placement=placement)
    solution_placement = sim_annealing_searched_solution(
        problem, total_rounds=250, restarts=2
    )
    if solution_placement != placement:
        return solution_placement
    else:
        return mutated_placement(mutated_placement(placement))


def mutated_bussable_placement(
    netlist: Netlist,
    placement: InstancePlacement,
    bussing: PartialBusPaths,
) -> InstancePlacement:
    return mutated_placement(mutated_placement(placement))


@dataclass
class BussingPlacementProblem(LocalSearchProblem[InstancePlacement]):
    netlist: Netlist

    def random_solution(self) -> InstancePlacement:
        return netlist_random_placement(self.netlist)

    def mutated_solution(self, solution: InstancePlacement) -> InstancePlacement:
        try:
            # This call should be cached and return (or raise) immediately.
            bussing = dest_pin_relaxed_bus_path(self.netlist, solution)
        except BussingError:
            return mutated_unbussable_placement(self.netlist, solution)
        else:
            return mutated_bussable_placement(self.netlist, solution, bussing)

    def solution_cost(self, solution: InstancePlacement) -> float:
        display_placement(self.netlist, solution)

        if not placement_valid(self.netlist, solution):
            return 1_000_000

        try:
            bussing = dest_pin_relaxed_bus_path(self.netlist, solution)
        except BussingError:
            print("Unbussable!")
            return 100_000 + unbussable_placement_cost(self.netlist, solution)
        else:
            print(f"Bussable! Collision count: {collision_count(bussing)}")
            return bussable_placement_cost(self.netlist, solution, bussing)


def assembled_circuit_schem(
    instance_config: dict[InstanceId, InstanceConfig],
    network_specs: NetworkSpecs,
) -> Schematic:
    netlist = netlist_from_simple_spec(
        instance_config=instance_config,
        network_specs=network_specs,
    )

    def solution_schematic(placement: InstancePlacement) -> Schematic:
        bus_paths = dest_pin_relaxed_bus_path(netlist, placement)
        print(f"Collision count: {collision_count(bus_paths)}")
        return bussed_placement_schematic(netlist, placement, bus_paths)

    TOTAL_ROUNDS = 1_000

    def checkpoint(round: int, placement: InstancePlacement, cost: float):
        path = f"checkpoints/output_{round}.schem"
        print(
            f"[{round + 1}/{TOTAL_ROUNDS}] Saving solution with cost {cost} to {path}..."
        )
        try:
            schem = solution_schematic(placement)
            save_schem(schem, path)
        except BaseException as e:
            print(f"Failed to save: {e}")

    seed(0xDEADBEEF)
    placement_problem = BussingPlacementProblem(netlist)
    placement = sim_annealing_searched_solution(
        placement_problem,
        total_rounds=TOTAL_ROUNDS,
        show_progressbar=True,
        rounds_per_print=1,
        rounds_per_checkpoint=50,
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
