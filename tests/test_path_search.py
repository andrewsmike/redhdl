from contextlib import ExitStack, contextmanager
from dataclasses import dataclass
from time import time
from unittest.mock import patch

from redhdl.search.path_search import (
    Action,
    PathSearchProblem,
    State,
    Step,
    TracedPathSearchProblem,
    a_star_bfs_searched_solution,
    a_star_iddfs_searched_solution,
)
from redhdl.voxel.region import Direction, Pos, direction_unit_pos, xz_directions


@dataclass(frozen=True)
class PlanarPathSearchProblem(PathSearchProblem[Pos, Direction]):
    wall_poses: set[Pos]
    start_pos: Pos
    end_pos: Pos

    def initial_state(self) -> Pos:
        return self.start_pos

    def state_actions(self, state: Pos) -> list[Direction]:
        return [
            direction
            for direction in xz_directions
            if (next_pos := state + direction_unit_pos[direction])
            not in self.wall_poses
        ]

    def state_action_result(self, state: Pos, action: Direction) -> Pos:
        return state + direction_unit_pos[action]

    def state_action_cost(self, state: Pos, action: Direction) -> float:
        return 1

    def is_goal_state(self, state: Pos) -> bool:
        return state == self.end_pos

    def min_cost(self, state: Pos) -> float:
        return (state - self.end_pos).l1()

    def display_solution_str(self, solution: list[Direction]):
        solution_positions = set()
        current_pos = self.start_pos
        for step_direction in solution:
            current_pos += direction_unit_pos[step_direction]
            solution_positions.add(current_pos)

        all_positions = (
            set(solution_positions) | self.wall_poses | {self.start_pos, self.end_pos}
        )

        min_x, _, min_z = Pos.elem_min(*all_positions)
        max_x, _, max_z = Pos.elem_max(*all_positions)

        lines = []
        for z in range(min_z, max_z + 1):
            line = ""
            for x in range(min_x, max_x + 1):
                pos = Pos(x, 0, z)
                if pos in self.wall_poses:
                    pos_char = "#"
                elif pos == self.start_pos:
                    pos_char = "s"
                elif pos == self.end_pos:
                    pos_char = "e"
                elif pos in solution_positions:
                    pos_char = "@"
                else:
                    pos_char = " "
                line += pos_char
            lines.append(line)

        return "\n".join(lines)

    def solution_valid(self, solution: list[Direction]) -> bool:
        current_pos = self.start_pos
        for step_direction in solution:
            if current_pos in self.wall_poses:
                return False

            current_pos += direction_unit_pos[step_direction]

        return current_pos == self.end_pos


problem_map = (
    "         e"
    + "          "
    + "########  "
    + "       #  "
    + "       #  "
    + "       #  "
    + "s      #  "
    + "       #  "
)


def planar_path_problem_search_from_map(problem_map: str) -> PlanarPathSearchProblem:
    start_pos = None
    end_pos = None
    wall_poses = set()
    for y, line in enumerate(problem_map.split("\n")):
        for x, pos_type_char in enumerate(line):
            pos = Pos(x, 0, y)
            if pos_type_char == "#":
                wall_poses.add(pos)
            elif pos_type_char == "s":
                start_pos = pos
            elif pos_type_char == "e":
                end_pos = pos

    assert start_pos is not None
    assert end_pos is not None

    return PlanarPathSearchProblem(
        wall_poses=wall_poses,
        start_pos=start_pos,
        end_pos=end_pos,
    )


planar_path_problem = planar_path_problem_search_from_map(problem_map)


def test_bfs_search():
    solution = a_star_bfs_searched_solution(planar_path_problem)
    print(planar_path_problem.display_solution_str(solution))
    assert planar_path_problem.solution_valid(solution)
    assert len(solution) == 17


def test_bfs_efficiency():
    start_time = time()
    for _round_index in range(100):
        a_star_bfs_searched_solution(planar_path_problem)
    end_time = time()

    print(end_time - start_time)
    assert end_time - start_time < 0.4


def test_iddfs_search():
    solution = a_star_bfs_searched_solution(planar_path_problem)
    print(planar_path_problem.display_solution_str(solution))
    assert planar_path_problem.solution_valid(solution)
    assert len(solution) == 17


def test_iddfs_efficiency():
    start_time = time()
    for _round_index in range(100):
        a_star_iddfs_searched_solution(planar_path_problem)
    end_time = time()

    print(end_time - start_time)
    assert end_time - start_time < 2


def steps_2d_map_str(steps: list[Pos]) -> str:
    pos_indices: dict[Pos, int] = {}
    for step in steps:
        if step not in pos_indices:
            pos_indices[step] = len(pos_indices)

    min_x, _, min_z = Pos.elem_min(*steps)
    max_x, _, max_z = Pos.elem_max(*steps)

    return "\n".join(
        "".join(
            f"{pos_indices.get(Pos(x, 0, z), -1):3d}" for x in range(min_x, max_x + 1)
        )
        for z in range(min_z, max_z + 1)
    )


@contextmanager
def fully_order_steps():
    """
    Force path search methods to deterministically order all next steps, rather than
    allowing min-cost-equivalent states to be ordered arbitrarily or nondeterministically.

    This is useful for reproducible testing.
    """

    def cmp_key(step: Step[State, Action]) -> tuple[float, float, State, Action]:
        return (step.min_cost, -step.cost, step.state, step.action)

    with ExitStack() as stack:
        for patch_func_name, patch_func in [
            ("__eq__", lambda self, other: cmp_key(self) == cmp_key(other)),
            ("__lt__", lambda self, other: cmp_key(self) < cmp_key(other)),
            ("__le__", lambda self, other: cmp_key(self) <= cmp_key(other)),
            ("__gt__", lambda self, other: cmp_key(self) > cmp_key(other)),
            ("__ge__", lambda self, other: cmp_key(self) >= cmp_key(other)),
        ]:
            stack.enter_context(
                patch(
                    f"redhdl.search.path_search.AlgoTraceStep.{patch_func_name}",
                    patch_func,
                )
            )

        yield


@fully_order_steps()
def display_bfs_expansion_order():
    """
    Example visual of the expansion order.
    This _should_ be consistent within the same algorithm, and is helpful for
    verifying search semantics.

    >>> display_bfs_expansion_order()  # doctest: +NORMALIZE_WHITESPACE
    Solution path:
    @@@@@@@@@@e
    @
    @########
    @@      #
     @      #
     @      #
     s      #
            #
    ...
    Expansion order:
     34 35 36 37 38 39 40 41 42 43
     33 -1 -1 -1 -1 -1 -1 -1 -1 -1
     32 -1 -1 -1 -1 -1 -1 -1 -1 -1
     31  3  4  5  6  7  8  9 -1 -1
     -1  2 10 11 12 13 14 15 -1 -1
     -1  1 16 17 18 19 20 21 -1 -1
     -1  0 22 23 24 25 26 27 -1 -1
     -1 -1 -1 -1 -1 30 29 28 -1 -1
    """
    traced_problem = TracedPathSearchProblem(planar_path_problem)
    solution = a_star_bfs_searched_solution(traced_problem)
    assert planar_path_problem.solution_valid(solution)
    assert len(solution) == 17

    print("Solution path:")
    print(planar_path_problem.display_solution_str(solution))
    print("...")
    print("Expansion order:")
    print(
        steps_2d_map_str(
            [
                step.state
                for step in traced_problem.algo_steps
                if step.algo_action == "state_actions"
            ]
        )
    )


@fully_order_steps()
def display_iddfs_expansion_order():
    """
    Example visual of the expansion order.
    This _should_ be consistent within the same algorithm, and is helpful for
    verifying search semantics.

    >>> display_iddfs_expansion_order()  # doctest: +NORMALIZE_WHITESPACE
    Solution path:
              e
    @@@@@@@@@@@
    @########
    @@      #
     @      #
     @      #
     s      #
            #
    ...
    Expansion order:
     36 37 38 39 40 41 42 43 44 45 46
     35 -1 -1 -1 -1 -1 -1 -1 -1 -1 -1
     34 27 24 21 18 15 12  9 -1 -1 -1
     -1 26 23 20 17 14 11  8 -1 -1 -1
     -1 25 22 19 16 13 10  7 -1 -1 -1
     -1  0  1  2  3  4  5  6 -1 -1 -1
     -1 -1 33 32 31 30 29 28 -1 -1 -1
    """
    traced_problem = TracedPathSearchProblem(planar_path_problem)
    solution = a_star_iddfs_searched_solution(traced_problem)
    assert planar_path_problem.solution_valid(solution)
    assert len(solution) == 17

    print("Solution path:")
    print(planar_path_problem.display_solution_str(solution))
    print("...")
    print("Expansion order:")
    print(
        steps_2d_map_str(
            [
                step.state
                for step in traced_problem.algo_steps
                if step.algo_action == "state_actions"
            ]
        )
    )


@dataclass(frozen=True)
class BinarySearchProblem(PathSearchProblem[tuple[int, ...], int]):
    hard_hint: bool
    solution: tuple[int, ...]

    def initial_state(self) -> tuple[int, ...]:
        return ()

    def state_actions(self, state: tuple[int, ...]) -> list[int]:
        return [0, 1, 2, 3]

    def state_action_result(
        self, state: tuple[int, ...], action: int
    ) -> tuple[int, ...]:
        return state + (action,)

    def state_action_cost(self, state: tuple[int, ...], action: int) -> float:
        return 1 if action > 0 else 1.25

    def is_goal_state(self, state: tuple[int, ...]) -> bool:
        return state == self.solution

    def min_cost(self, state: tuple[int, ...]) -> float:
        INF = 1000000000
        if len(state) > len(self.solution):
            return INF

        if self.hard_hint and (self.solution[: len(state)] != state):
            return INF

        return max(len(self.solution) - len(state), 1)


bsp_solution = (0, 1, 2, 2, 3, 1, 2)

no_hinting_bsp = BinarySearchProblem(
    solution=bsp_solution,
    hard_hint=False,
)
hinting_bsp = BinarySearchProblem(
    solution=bsp_solution,
    hard_hint=False,
)


def test_bsp_problem():
    bfs_solution = a_star_bfs_searched_solution(no_hinting_bsp)
    iddfs_solution = a_star_iddfs_searched_solution(no_hinting_bsp)
    assert bfs_solution == list(bsp_solution)
    assert iddfs_solution == list(bsp_solution)


def test_hinting_bsp_problem():
    bfs_solution = a_star_bfs_searched_solution(hinting_bsp)
    iddfs_solution = a_star_iddfs_searched_solution(hinting_bsp)
    assert bfs_solution == list(bsp_solution)
    assert iddfs_solution == list(bsp_solution)


def print_benchmarks():
    """
    # >>> print_benchmarks()

    Without state caching in iddfs:
    ('hinting_bsp', 'bfs', 6.307959079742432)
    ('hinting_bsp', 'iddfs', 5.053704023361206)
    ('no_hinting_bsp', 'bfs', 6.303386926651001)
    ('no_hinting_bsp', 'iddfs', 5.0512471199035645)
    ('path_search', 'bfs', 0.05878019332885742)
    ('path_search', 'iddfs', 7.332165956497192)
    """
    for problem_name, problem in {
        "hinting_bsp": hinting_bsp,
        "no_hinting_bsp": no_hinting_bsp,
        "path_search": planar_path_problem,
    }.items():
        for algo_name in ["bfs", "iddfs"]:
            algo = {
                "bfs": a_star_bfs_searched_solution,
                "iddfs": a_star_iddfs_searched_solution,
            }[algo_name]

            start_time = time()
            for _round_index in range(100):
                algo(problem)

            end_time = time()
            print((problem_name, algo_name, end_time - start_time))
