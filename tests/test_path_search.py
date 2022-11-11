from dataclasses import dataclass
from time import time

from redhdl.region import Direction, Pos, direction_unit_pos, xz_directions
from redhdl.path_search import (
    Action,
    PathSearchProblem,
    State,
    a_star_bfs_searched_solution,
    a_star_iddfs_searched_solution,
)


@dataclass
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
            if (
                    next_pos := state + direction_unit_pos[direction]
            ) not in self.wall_poses
        ]

    def state_action_result(self, state: Pos, action: Direction) -> Pos:
        return state + direction_unit_pos[action]

    def state_action_cost(self, state: Pos, action: Direction) -> float:
        return 1

    def is_goal_state(self, state: Pos) -> bool:
        return state == self.end_pos

    def min_distance(self, state: Pos) -> float:
        return (state - self.end_pos).l1()

    def display_solution(self, solution: list[Direction]):
        solution_positions = set()
        current_pos = self.start_pos
        for step_direction in solution:
            current_pos += direction_unit_pos[step_direction]
            solution_positions.add(current_pos)

        all_positions = set(solution_positions) | self.wall_poses | {self.start_pos, self.end_pos}

        min_x, max_x = (
            min(x for x, y, z in all_positions),
            max(x for x, y, z in all_positions),
        )

        min_y, max_y = (
            min(z for x, y, z in all_positions),
            max(z for x, y, z in all_positions),
        )

        lines = []
        for y in range(min_y, max_y + 1):
            wall_poses: set[Pos]
            start_pos: Pos
            end_pos: Pos
            line = ""
            for x in range(min_x, max_x + 1):
                pos = Pos(x, 0, y)
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


    def solution_valid(self, solution: list[Action]) -> bool:
        current_pos = self.start_pos
        for step_direction in solution:
            if current_pos in self.wall_poses:
                return False
            current_pos += direction_unit_pos[step_direction]

        return current_pos == self.end_pos


problem_map = """\
         e
          
########  
       #  
       #  
       #  
s      #  
       #  \
"""


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
    print(planar_path_problem.display_solution(solution))
    assert planar_path_problem.solution_valid(solution)
    assert len(solution) == 17


def test_bfs_efficiency():
    start_time = time()
    for i in range(100):
        a_star_bfs_searched_solution(planar_path_problem)
    end_time = time()

    print(end_time - start_time)
    assert end_time - start_time < 0.4

def test_iddfs_search():
    solution = a_star_bfs_searched_solution(planar_path_problem)
    print(planar_path_problem.display_solution(solution))
    assert planar_path_problem.solution_valid(solution)
    assert len(solution) == 17


def test_iddfs_efficiency():
    start_time = time()
    for i in range(100):
        a_star_iddfs_searched_solution(planar_path_problem)
    end_time = time()

    print(end_time - start_time)
    assert end_time - start_time < 2


@dataclass
class BinarySearchProblem(PathSearchProblem[tuple[int], int]):
    hard_hint: bool
    solution: tuple[int]

    def initial_state(self) -> tuple[int]:
        return ()

    def state_actions(self, state: tuple[int]) -> list[int]:
        return [0, 1, 2, 3]

    def state_action_result(self, state: tuple[int], action: int) -> tuple[int]:
        return state + (action,)

    def state_action_cost(self, state: tuple[int], action: int) -> float:
        return 1 if action > 0 else 1.25

    def is_goal_state(self, state: tuple[int]) -> bool:
        return state == self.solution

    def min_distance(self, state: tuple[int]) -> float:
        INF = 1000000000
        if len(state) > len(self.solution):
            return INF

        if self.hard_hint and (self.solution[:len(state)] != state):
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
    Example output for a high-branching-factor problem:
    ('bfs', 'hints', 14.899113416671753)
    ('bfs', 'no_hints', 12.301818132400513)
    ('iddfs', 'hints', 1.8538579940795898)
    ('iddfs', 'no_hints', 1.8927991390228271)
    """
    for algo_name in ["bfs", "iddfs"]:
        for problem_name in ["hints", "no_hints"]:
            algo = {
                "bfs": a_star_bfs_searched_solution,
                "iddfs": a_star_iddfs_searched_solution,
            }[algo_name]

            problem = {
                "hints": hinting_bsp,
                "no_hints": no_hinting_bsp,
            }[problem_name]

            start_time = time()
            for i in range(100):
                algo(problem)

            end_time = time()
            print((algo_name, problem_name, end_time - start_time))

    assert False
