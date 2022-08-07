from dataclasses import dataclass
from random import seed

from redhdl.bussing import (
    BussingError,
    bussed_placement_schematic,
    bussing_cost,
    bussing_min_cost,
    collision_count,
    dest_pin_relaxed_bus_path,
)
from redhdl.local_search import LocalSearchProblem, sim_annealing_searched_solution
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
    mutated_placement,
    netlist_random_placement,
    placement_compactness_score,
    placement_valid,
)
from redhdl.schematic import Schematic, save_schem


@dataclass
class GreedyBussingPlacementProblem(LocalSearchProblem[InstancePlacement]):
    netlist: Netlist

    def random_solution(self) -> InstancePlacement:
        return netlist_random_placement(self.netlist)

    def mutated_solution(self, solution: InstancePlacement) -> InstancePlacement:
        return mutated_placement(self.netlist, solution)

    def solution_cost(self, solution: InstancePlacement) -> float:
        if not placement_valid(self.netlist, solution):
            return 10000

        placement_cost = -placement_compactness_score(self.netlist, solution)

        try:
            bussing = dest_pin_relaxed_bus_path(self.netlist, solution)
        except BussingError:
            return placement_cost + bussing_min_cost(self.netlist, solution) + 1000

        return placement_cost + bussing_cost(bussing) + collision_count(bussing) * 5


def assembled_circuit_schem(
    instance_config: dict[InstanceId, InstanceConfig],
    network_specs: NetworkSpecs,
) -> Schematic:
    netlist = netlist_from_simple_spec(
        instance_config=instance_config,
        network_specs=network_specs,
    )
    seed(0xDEADBEEF)
    placement_problem = GreedyBussingPlacementProblem(netlist)
    placement = sim_annealing_searched_solution(
        placement_problem,
        total_rounds=40,
        show_progressbar=True,
        rounds_per_print=10,
    )
    print(f"Best cost: {placement_problem.solution_cost(placement)}")

    bus_paths = dest_pin_relaxed_bus_path(netlist, placement)

    collision_count(bus_paths)

    schem = bussed_placement_schematic(netlist, placement, bus_paths)
    import pdb

    pdb.set_trace()

    return schem


def main():
    schem = assembled_circuit_schem(
        example_instance_configs,
        example_network_specs,
    )
    save_schem(schem, "output.schem")


if __name__ == "__main__":
    main()
