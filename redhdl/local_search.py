"""
Local search: Use black-box optimization methods to solve problems.

Can be contrasted with tree-based search methods, which are complete / not probabilistic.
Currently used to identify placements.
"""
from abc import ABCMeta, abstractmethod
from math import exp
from random import random
from typing import Callable, Generic, TypeVar

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

    def good_enough(self, solution: Solution) -> bool:
        return False


def sim_annealing_searched_solution(
    problem: LocalSearchProblem[Solution],
    total_rounds: int = 2_000,
    restarts: int = 1,
    rounds_per_print: int | None = None,
    show_progressbar: bool = False,
    rounds_per_checkpoint: int | None = None,
    checkpoint_func: Callable[[int, Solution, float], None] | None = None,
) -> Solution:
    # We use random restarts, so we need to track
    # the best we saw throughout all the restart periods.
    best_cost: float | None = None
    best_solution: Solution | None = None
    current_cost: float | None = None
    current_solution: Solution | None = None

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
            print(f"\nBest cost: {best_cost}, last cost: {current_cost}")

        if (
            rounds_per_checkpoint is not None
            and i % rounds_per_checkpoint == 0
            and i > 0
        ):
            assert best_cost is not None and best_solution is not None  # For MyPy.
            assert (
                checkpoint_func is not None
            ), "Cannot checkpoint without a checkpoint_func."
            checkpoint_func(i, best_solution, best_cost)

        candidate_cost = problem.solution_cost(candidate_solution)
        if problem.good_enough(candidate_solution):
            print(f"Good enough at {i}/{total_rounds}")
            return candidate_solution

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
