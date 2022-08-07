"""
Local search: Use black-box optimization methods to solve problems.

Can be contrasted with tree-based search methods, which are complete / not probabilistic.
Currently used to identify placements.
"""
from abc import ABCMeta, abstractmethod
from math import exp
from random import random
from typing import Generic, TypeVar

from tqdm import tqdm

Solution = TypeVar("Solution")


class LocalSearchProblem(Generic[Solution], metaclass=ABCMeta):
    @abstractmethod
    def random_solution(self) -> Solution:
        pass

    @abstractmethod
    def mutated_solution(self, solution: Solution) -> Solution:
        pass

    @abstractmethod
    def solution_cost(self, solution: Solution) -> float:
        pass


def sim_annealing_searched_solution(
    problem: LocalSearchProblem[Solution],
    total_rounds: int = 2_000,
    restarts: int = 1,
    rounds_per_print: int | None = None,
    show_progressbar: bool = False,
) -> Solution:
    # We use random restarts, so we need to track
    # the best we saw throughout all the restart periods.
    best_cost, best_solution = None, None
    current_cost, current_solution = None, None

    rounds_per_restart = total_rounds // restarts

    if show_progressbar:
        it = tqdm(range(total_rounds))
    else:
        it = range(total_rounds)

    for i in it:
        if i % rounds_per_restart == 0:
            candidate_solution = problem.random_solution()
        else:
            assert current_solution is not None  # For MyPy.
            candidate_solution = problem.mutated_solution(current_solution)
        if rounds_per_print is not None and i % rounds_per_print == 0:
            print(best_cost)

        candidate_cost = problem.solution_cost(candidate_solution)

        accept_solution = (
            current_cost is None
            or candidate_cost < current_cost
            or random() < exp(-(candidate_cost / current_cost) * (4 * i / total_rounds))
        )
        if accept_solution:
            current_solution = candidate_solution
            current_cost = candidate_cost

        if best_cost is None or candidate_cost < best_cost:
            best_cost, best_solution = candidate_cost, candidate_solution

    assert best_solution is not None  # For MyPy.

    return best_solution
