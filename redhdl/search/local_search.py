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


# This is reasonably close to its min complexity, but it's a bit above the complexity
# threshold. I'm not certain breaking into helpers will add clarity, so leaving as is.
def sim_annealing_searched_solution(  # noqa: C901
    problem: LocalSearchProblem[Solution],
    total_rounds: int = 2_000,
    restarts: int = 1,
    rounds_per_print: int | None = None,
    show_progressbar: bool = False,
    rounds_per_checkpoint: int | None = None,
    checkpoint_func: Callable[[int, Solution, float], None] | None = None,
) -> Solution:
    if total_rounds <= 0:
        raise ValueError(
            "Simulated annealing must ran for a positive number of total_rounds."
        )

    if (rounds_per_checkpoint is None) != (checkpoint_func is None):
        raise ValueError(
            "rounds_per_checkpoint and checkpoint must both be None or both be provided."
        )

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

        should_checkpoint = (
            rounds_per_checkpoint is not None
            and i % rounds_per_checkpoint == 0
            and i > 0
        )
        if should_checkpoint:
            assert best_cost is not None and best_solution is not None  # For MyPy.
            assert checkpoint_func is not None  # For MyPy.
            checkpoint_func(i, best_solution, best_cost)

        candidate_cost = problem.solution_cost(candidate_solution)
        if problem.good_enough(candidate_solution):
            print(
                f"Good enough at round {i+1} of {total_rounds} (cost={candidate_cost})."
            )
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
