#!/usr/bin/env python

from os import system
from time import time

from redhdl.bussing import BussingError
from redhdl.path_search import Step
from redhdl.redstone_bussing import *
from redhdl.region import PointRegion, display_regions

_DISTANCE = 20
seen_step_min_costs = {}

def display_step(step: Step, problem):
    min_x, max_x = -1, _DISTANCE + 1
    min_y, max_y = -1, _DISTANCE + 1
    curr_step = step

    pos_prev_pos = {}
    bus_pos_costs_min_costs = {}
    repeater_poses = set()
    while curr_step is not None:
        if curr_step.action is not None:
            bus_pos_costs_min_costs[curr_step.action.next_pos] = (curr_step.cost, curr_step.min_cost)
            seen_step_min_costs[curr_step.action.next_pos] = min(
                seen_step_min_costs.get(curr_step.action.next_pos, 1000000000),
                curr_step.min_cost,
            )
            if curr_step.action.is_repeater:
                repeater_poses.add(curr_step.action.next_pos)

        parent_step = curr_step.parent_step
        if parent_step is not None and parent_step.action is not None:
            pos_prev_pos[curr_step.action.next_pos] = parent_step.action.next_pos

        curr_step = curr_step.parent_step

    pos_symbol = {}
    for x in range(min_x, max_x):
        pos_symbol[(x, 0)] = "."
    for y in range(min_y, max_y):
        pos_symbol[(0, y)] = "."

    # for pos, min_cost in seen_step_min_costs.items():
    #     pos_symbol[(pos[0], pos[2])] = str(min_cost)

    for pos, (cost, min_cost) in bus_pos_costs_min_costs.items():
        dy = (pos - pos_prev_pos.get(pos, Pos(0, 0, 0))).y
        if dy > 0:
            dir_sym = "^"
        elif dy == 0:
            dir_sym = "-"
        elif dy < 0:
            dir_sym = "v"
        if pos not in repeater_poses:
            pos_symbol[(pos[0], pos[2])] = f"[{min_cost}{dir_sym}]"
        else:
            pos_symbol[(pos[0], pos[2])] = f"<{min_cost}{dir_sym}>"


    # system('clear')
    from pprint import pprint
    pprint(set(bus_pos_costs_min_costs.keys()))
    for y in range(max_y, min_y - 1, -1):
        print(
            "".join(
                f"{pos_symbol.get((x, y), ''):^5}"
                for x in range(min_x, max_x)
            )
        )
    if step.parent_step is not None:
        problem.state_action_cost(step.parent_step.state, step.action)
    print(f"Current cost: {step.cost}")
    if step.parent_step is not None:
        assert step.min_cost == problem.min_cost(step.state) + step.cost
    print(f"Min cost: {step.min_cost}")


def main():
    start_time = time()

    start_xz_dir = "south"
    end_xz_dir = "east"

    bussing, states, steps, costs, algo_steps = redstone_bussing_details(
        start_pos=Pos(0, 0, 0),
        # end_pos=Pos(3, 2, 2),
        end_pos=Pos(_DISTANCE, _DISTANCE, _DISTANCE),
        start_xz_dir=start_xz_dir,
        end_xz_dir=end_xz_dir,
        instance_points=set(),
        other_busses=RedstoneBussing(),
        max_steps=10000,
        debug=False,
    )
    duration = time() - start_time


    expansion_steps = [
        step.step
        for step in algo_steps
        if step.algo_action == "expanding_step"
    ]

    print(_DISTANCE, (_DISTANCE + 1) ** 3, duration, len(expansion_steps))

    debug_problem = RedstonePathFindingProblem(
        start_pos=Pos(0, 0, 0),
        end_pos=Pos(_DISTANCE, _DISTANCE, _DISTANCE),
        start_xz_dir=start_xz_dir,
        end_xz_dir=end_xz_dir,
        instance_points=set(),
        other_busses=RedstoneBussing(),
        early_repeater_cost=12,
        momentum_break_cost=3,
        debug=True,
    )

    for expansion_step in expansion_steps:
        display_step(expansion_step, debug_problem)
        input()


if __name__ == "__main__":
    main()