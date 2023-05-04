from time import time

from redhdl.bussing import BussingTimeoutError
from redhdl.redstone_bussing import *


def test_search_durations():
    """
    5 216 0.02058696746826172 24
    10 1331 0.060437917709350586 49
    20 9261 0.19190597534179688 145
    30 29791 0.28361082077026367 114
    40 68921 3.213214874267578 3307
    50 132651 3.4154770374298096 215
    60 226981 8.252267122268677 5483
    70 357911 12.555897951126099 4518
    """
    durations = {}
    start_time = time()
    for distance in [5, 10, 30, 70]:
        try:
            bussing, states, steps, costs, algo_steps = redstone_bussing_details(
                start_pos=Pos(0, 0, 0),
                # end_pos=Pos(3, 2, 2),
                end_pos=Pos(distance, distance, distance),
                start_xz_dir="south",
                end_xz_dir="east",
                instance_points=set(),
                other_buses=RedstoneBussing(),
                max_steps=5_000,
                debug=False,
            )
            expanding_steps = [
                step for step in algo_steps if step.algo_action == "expanding_step"
            ]
            durations[distance] = time() - start_time
            print(
                distance, (distance + 1) ** 3, durations[distance], len(expanding_steps)
            )

        except BussingTimeoutError:
            break
