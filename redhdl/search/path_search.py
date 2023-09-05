"""
Path search: Use graph search algorithms (such as A*) to find solutions to well
defined problems.

Problems are specified by subclassing (then instantiating) PathSearchProblems.

Once problems are specified, we provide two search methods for problems:
- a_star_bfs_searched_solution
    Breadth-first A* search of the solution space.
    Ideal for problems with a low branching factord; can be somewhat
    memory inefficient and slower for wider problems with a persistently high
    effective branching factor, or problems where branches don't usually fold
    back into each other (like exploring in a grid).

- a_star_iddfs_searched_solution
    Iterative deepening depth-first A* search of the solution space.
    This method has a substantially lower memory footprint/execution time for
    problems with a wider branching factor, but can be substantially slower on
    constrained problems (like exploring in a grid) where branches usually fold
    back into each other or the effective branching factor drops dramatically
    after the first few steps.

These methods raise the SearchErrors NoSolutionError and SearchTimeoutError on
failure.
"""
from abc import ABCMeta, abstractmethod
from dataclasses import dataclass, field
from heapq import heappop, heappush
from math import inf
from typing import Generator, Generic, Literal, Optional, TypeVar

State = TypeVar("State")
Action = TypeVar("Action")


class PathSearchProblem(Generic[State, Action], metaclass=ABCMeta):
    @abstractmethod
    def initial_state(self) -> State:
        pass

    @abstractmethod
    def state_actions(self, state: State) -> list[Action]:
        pass

    @abstractmethod
    def state_action_result(self, state: State, action: Action) -> State:
        pass

    @abstractmethod
    def state_action_cost(self, state: State, action: Action) -> float:
        pass

    @abstractmethod
    def is_goal_state(self, state: State) -> bool:
        pass

    @abstractmethod
    def min_cost(self, state: State) -> float:
        pass

    def expanding_step(self, step: "Step") -> None:
        pass


@dataclass
class Step(Generic[State, Action]):
    parent_step: Optional["Step"]
    action: Action
    state: State
    cost: float
    min_cost: float

    def action_sequence(self) -> list[Action]:
        sequence = []
        step: Step | None = self
        while step is not None:
            sequence.append(step.action)
            step = step.parent_step

        return list(reversed(sequence))[1:]  # First action is always None.

    def next_steps(self, problem: PathSearchProblem) -> Generator["Step", None, None]:
        for action in sorted(problem.state_actions(self.state)):
            yield Step(
                state=(next_state := problem.state_action_result(self.state, action)),
                parent_step=self,
                action=action,
                cost=(
                    next_cost := self.cost
                    + problem.state_action_cost(self.state, action)
                ),
                min_cost=next_cost + problem.min_cost(next_state),
            )

    @staticmethod
    def initial_step(state: State) -> "Step":
        return Step(
            state=state,
            parent_step=None,
            action=None,
            cost=0,
            min_cost=0,
        )

    @property
    def depth(self) -> int:
        return len(self.action_sequence())

    def __eq__(self, other) -> bool:
        return self.min_cost == other.min_cost

    def __lt__(self, other) -> bool:
        return self.min_cost < other.min_cost

    def __le__(self, other) -> bool:
        return self.min_cost <= other.min_cost

    def __gt__(self, other) -> bool:
        return self.min_cost > other.min_cost

    def __ge__(self, other) -> bool:
        return self.min_cost >= other.min_cost


class SearchError(BaseException):
    pass


class NoSolutionError(SearchError):
    pass


class SearchTimeoutError(SearchError):
    pass


def a_star_iddfs_searched_solution(
    problem: PathSearchProblem[State, Action],
    max_steps: int = 10_000,
) -> list[Action]:
    """Iterative deepening depth first A* search.

    Set the "max cost", then run DFS and abort once the A* heuristic min_cost
    cap is reached. If the search doesn't find anything, up the cap (using A*
    heuristic determined min-cost) and continue.
    Eventually this finds all solutions, and it tends to be faster than
    traditional priority-queue-based breadth first search.

    BFS is moderately memory hungry, and memory has a substantial IO/compute
    footprint. If the effective branching factor of a problem is >=2 after a
    few steps, it's sometimes faster to evaluate the core of the tree multiple times
    than it is to perfectly keep track of everything in a queue.
    """

    steps_remaining: int
    state_min_cost: dict[State, float] = {}  # Accumulate over all runs.

    def subtree_solution_should_continue(
        problem: PathSearchProblem[State, Action],
        step: Step,
        max_cost: float,
    ) -> tuple[Step | None, bool, float | None]:

        nonlocal state_min_cost
        prev_min_cost = state_min_cost.get(step.state, inf)
        if step.cost > prev_min_cost:
            return None, False, None

        state_min_cost[step.state] = step.cost

        if step.min_cost > max_cost:
            return None, True, step.min_cost

        if problem.is_goal_state(step.state):
            return step, False, None

        nonlocal steps_remaining
        if steps_remaining == 0:
            raise SearchTimeoutError(f"Could not find solution in {max_steps} steps.")
        steps_remaining -= 1

        any_should_continue = False
        least_min_cost = inf
        for next_step in step.next_steps(problem):
            solution, should_continue, min_cost = subtree_solution_should_continue(
                problem,
                next_step,
                max_cost,
            )
            if solution is not None:
                return solution, False, None
            else:
                any_should_continue |= should_continue
                if min_cost is not None:
                    least_min_cost = min(least_min_cost, min_cost)
        else:
            return None, any_should_continue, least_min_cost

    first_step = Step.initial_step(problem.initial_state())
    max_cost: float = 1
    while max_cost < 100_000:
        steps_remaining = max_steps
        solution, still_unexplored_space, min_cost = subtree_solution_should_continue(
            problem,
            first_step,
            max_cost=max_cost,
        )
        if solution:
            return solution.action_sequence()
        elif not still_unexplored_space:
            raise NoSolutionError("Path search problem has no solutions.")
        else:
            assert isinstance(min_cost, (float, int))  # For MyPy.
            max_cost = max(max_cost + 1, min_cost)
    else:
        raise SearchTimeoutError(f"Could not find solution in {max_steps} steps.")


def a_star_bfs_searched_solution(
    problem: PathSearchProblem[State, Action],
    max_steps: int = 10_000,
) -> list[Action]:

    first_step = Step.initial_step(problem.initial_state())
    next_best_action_heap = [first_step]

    explored_states: set[State] = set()

    remaining_steps: int = max_steps
    while len(next_best_action_heap) > 0 and remaining_steps > 0:
        step = heappop(next_best_action_heap)
        if step.state in explored_states:
            continue

        if problem.is_goal_state(step.state):
            return step.action_sequence()

        explored_states.add(step.state)

        problem.expanding_step(step)  # Just for debugging.
        for next_step in step.next_steps(problem):
            # Optional, but slightly slows things down:
            # if next_step.state not in explored_states
            heappush(next_best_action_heap, next_step)

        remaining_steps -= 1

    else:
        if len(next_best_action_heap) > 0:
            raise SearchTimeoutError(f"Could not find solution in {max_steps} steps.")
        else:
            raise NoSolutionError("Tree search problem has no solutions.")


AlgoAction = Literal[
    "initial_state",
    "state_actions",
    "state_action_result",
    "state_action_cost",
    "is_goal_state",
    "min_cost",
    "expanding_step",
]


@dataclass
class AlgoTraceStep(Generic[State, Action]):
    algo_action: AlgoAction
    state: State | None = None
    action: Action | None = None
    step: Step | None = None


@dataclass
class TracedPathSearchProblem(PathSearchProblem[State, Action]):
    """
    Record the algorithmic steps taken by the path search algorithm for analysis.
    """

    problem: PathSearchProblem[State, Action]
    algo_steps: list[AlgoTraceStep[State, Action]] = field(default_factory=list)

    def initial_state(self) -> State:
        self.algo_steps.append(AlgoTraceStep("initial_state"))
        return self.problem.initial_state()

    def state_actions(self, state: State) -> list[Action]:
        self.algo_steps.append(AlgoTraceStep("state_actions", state))
        return self.problem.state_actions(state)

    def state_action_result(self, state: State, action: Action) -> State:
        self.algo_steps.append(AlgoTraceStep("state_action_result", state, action))
        return self.problem.state_action_result(state, action)

    def state_action_cost(self, state: State, action: Action) -> float:
        self.algo_steps.append(AlgoTraceStep("state_action_cost", state, action))
        return self.problem.state_action_cost(state, action)

    def is_goal_state(self, state: State) -> bool:
        self.algo_steps.append(AlgoTraceStep("is_goal_state", state))
        return self.problem.is_goal_state(state)

    def min_cost(self, state: State) -> float:
        self.algo_steps.append(AlgoTraceStep("min_cost", state))
        return self.problem.min_cost(state)

    def expanding_step(self, step: Step) -> None:
        self.algo_steps.append(
            AlgoTraceStep("expanding_step", step.state, step.action, step)
        )
