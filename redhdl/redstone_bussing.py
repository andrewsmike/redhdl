"""
Redstone bus pathfinding problem.
Encodes the logic necessary to bus:
- Using repeaters, wires
- With correct signal strength handling
- With spacer blocks (as necessary)
- Using transparent / glass blocks
- While avoiding hard/soft powering other busses's stuff
- While avoiding getting hard/soft powered by another bus
- Compactly

Examples:
>>> bussing = redstone_bussing(
...     start_pos=Pos(0, 0, 0),
...     stop_pos=Pos(3, 2, 2),
...     instance_points=set(),
...     other_busses=RedstoneBussing(),
...     max_steps=10000,
... )

>>> pprint(bussing)
RedstoneBussing(element_sig_strengths=frozendict.frozendict({Pos(0, 0, 0): 15, ..., Pos(3, 2, 2): 10}),
                ...,
                airspace_blocks=frozenset({Pos(3, 2, 1), Pos(3, 1, 0)}))
>>> schem = bussing.schem()
>>> pprint(schem)
Schematic(pos_blocks={Pos(0, -1, 0): Block(block_type='minecraft:gray_wool',
                                           attributes=frozendict.frozendict({})),
                      Pos(0, 0, 0): Block(block_type='minecraft:redstone_wire',
                                          attributes=frozendict.frozendict({})),
...
                      Pos(3, 1, 2): Block(block_type='minecraft:gray_wool',
                                          attributes=frozendict.frozendict({})),
                      Pos(3, 2, 2): Block(block_type='minecraft:redstone_wire',
                                          attributes=frozendict.frozendict({}))},
          pos_sign_lines={})

The minimal bus has a traverse element, and an ascend element:
>>> from redhdl.region import display_regions
>>> display_regions(schem.pos_blocks.mask())  # doctest: +NORMALIZE_WHITESPACE
Y
   1
  11
 11
 1
     Z
Z
    1
    1
 1111
      X
Y
    1
    1
 1111
 1111
      X

"""
from dataclasses import dataclass, field
from functools import reduce
from typing import Any, Literal, NamedTuple, Optional, cast

from frozendict import frozendict

from redhdl.bussing import BussingError
from redhdl.path_search import PathSearchProblem, a_star_bfs_searched_solution
from redhdl.positional_data import PositionalData
from redhdl.region import (
    Direction,
    Pos,
    RectangularPrism,
    direction_unit_pos,
    directions,
    opposite_direction,
    unit_pos_direction,
    xz_directions,
    zero_pos,
)
from redhdl.schematic import Block, Schematic

SignalStrength = Literal[0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15]
signal_strengths = cast(list[SignalStrength], list(range(16)))


class RedstoneBussingError(BussingError):
    pass


class RedstonePathStep(NamedTuple):
    next_pos: Pos

    is_repeater: bool
    facing: Direction | None

    @property
    def is_wire(self) -> bool:
        return not self.is_repeater

    def next_steps(
        self,
        transparent_foundation: bool,
    ) -> list["RedstonePathStep"]:
        """
        Potential extension: Allow wire-block-repeater-block-wire pattern.
        """
        foundation_soft_powered = not (self.is_repeater or transparent_foundation)

        place_repeater_steps = [
            RedstonePathStep(
                next_pos=(
                    self.next_pos
                    + direction_unit_pos[xz_direction]
                    + (direction_unit_pos["down"] if step_down else zero_pos)
                ),
                is_repeater=True,
                facing=xz_direction,
            )
            for xz_direction in xz_directions
            for step_down in (True, False)
            if foundation_soft_powered or not step_down
        ]

        place_wire_steps = [
            RedstonePathStep(
                next_pos=(
                    self.next_pos
                    + direction_unit_pos[xz_direction]
                    + Pos(0, elev_change, 0)
                ),
                is_repeater=False,
                facing=None,
            )
            for xz_direction in (
                cast(list[Direction], ["north", "south", "east", "west"])
                if self.is_repeater is not None
                else [cast(Direction, self.facing)]
            )
            for elev_change in [-1, 0, 1]
            if (not transparent_foundation) or elev_change != -1
        ]

        return place_wire_steps + place_repeater_steps


@dataclass(frozen=True)
class RedstoneBussing:
    """
    A description of one-or-more redstone busses.

    All elements in element_sig_strengths are assumed to be wires, unless in
    repeater_directions.
    """

    element_sig_strengths: frozendict[Pos, SignalStrength] = field(
        default_factory=frozendict
    )
    repeater_directions: frozendict[Pos, Direction] = field(default_factory=frozendict)

    spacer_blocks: frozenset[Pos] = field(default_factory=frozenset)
    airspace_blocks: frozenset[Pos] = field(default_factory=frozenset)

    @property
    def foundation_blocks(self) -> set[Pos]:
        return {
            wire_pos + direction_unit_pos["down"]
            for wire_pos in self.element_sig_strengths
        }

    def transparent_foundation_blocks(
        self,
        other_bus_airspace_blocks: set[Pos] | frozenset[Pos],
    ) -> set[Pos]:
        return self.foundation_blocks & (
            other_bus_airspace_blocks | self.airspace_blocks
        )

    @property
    def element_blocks(self) -> set[Pos]:
        return set(self.element_sig_strengths)

    @property
    def non_element_blocks(self) -> set[Pos]:
        return (self.foundation_blocks | self.spacer_blocks) - self.element_blocks

    @property
    def repeater_blocks(self) -> set[Pos]:
        return set(self.repeater_directions.keys())

    @property
    def wire_blocks(self) -> set[Pos]:
        return self.element_blocks - self.repeater_blocks

    @property
    def element_foundation_blocks(self) -> set[Pos]:
        return self.element_blocks | self.foundation_blocks

    @property
    def soft_power_sensitive_blocks(self) -> frozenset[Pos]:
        return frozenset(
            repeater_block - direction_unit_pos[direction]
            for repeater_block, direction in self.repeater_directions.items()
        )

    @property
    def hard_power_sensitive_blocks(self) -> frozenset[Pos]:
        return (
            self.soft_power_sensitive_blocks
            | self.wire_blocks
            | {
                wire_block + direction_unit_pos[dir]
                for wire_block in self.wire_blocks
                for dir in directions
            }
        )

    @property
    def hard_powered_blocks(self) -> set[Pos]:
        return {
            repeater_block + direction_unit_pos[direction]
            for repeater_block, direction in self.repeater_directions.items()
        }

    @property
    def soft_powered_blocks(self) -> set[Pos]:
        return (
            self.hard_powered_blocks
            | self.foundation_blocks
            | {
                wire_block + direction_unit_pos[dir]
                for wire_block in self.wire_blocks
                for dir in self.wire_possible_directions(wire_block)
            }
        )

    def wire_possible_directions(self, wire_block: Pos) -> set[Direction]:
        """
        TODO: What about attractors causing the wire to point in the opposite direction?
        """
        directions_with_wire = {
            direction
            for direction in xz_directions
            if any(
                (wire_block + direction_unit_pos[direction] + vert_adjustment)
                in self.wire_blocks
                for vert_adjustment in (
                    direction_unit_pos["down"],
                    zero_pos,
                    direction_unit_pos["up"],
                )
            )
        }

        if len(directions_with_wire) == 0:
            return set(xz_directions)
        elif len(directions_with_wire) == 1:
            (direction,) = directions_with_wire
            return {direction, opposite_direction[direction]}
        else:
            return directions_with_wire

    @property
    def all_blocks(self) -> set[Pos]:
        return (
            set(self.element_sig_strengths.keys())
            | self.spacer_blocks
            | self.airspace_blocks
            | self.foundation_blocks
        )

    @property
    def min_pos(self) -> Pos:
        return reduce(Pos.elem_min, self.all_blocks)

    @property
    def max_pos(self) -> Pos:
        return reduce(Pos.elem_max, self.all_blocks)

    def __or__(self, other: Any) -> Any:
        """
        Join two redstone busses.

        Operation only valid if one bus was generated using next_step() calls with
        the other bus as an argument, or if two busses occupy completely disconnected
        regions.
        """
        if isinstance(other, RedstoneBussing):
            return RedstoneBussing(
                element_sig_strengths=(
                    self.element_sig_strengths | other.element_sig_strengths  # type: ignore
                ),
                repeater_directions=(
                    self.repeater_directions | other.repeater_directions  # type: ignore
                ),
                spacer_blocks=self.spacer_blocks | other.spacer_blocks,
                airspace_blocks=self.airspace_blocks | other.airspace_blocks,
            )
        else:
            return NotImplemented

    def pos_block(self, pos: Pos) -> Block:
        if pos in self.element_sig_strengths:
            if pos in self.repeater_directions:
                return Block(
                    block_type="minecraft:repeater",
                    attributes=frozendict(
                        {
                            "delay": "1",
                            "facing": self.repeater_directions[pos],
                            "locked": "false",
                            "powered": "false",
                        }
                    ),
                )
            else:
                return Block(
                    block_type="minecraft:redstone_wire",
                    attributes=frozendict(),
                )

        # If in foundation or spacer
        if pos not in self.non_element_blocks:
            return Block(
                block_type="minecraft:air",
                attributes=frozendict(),
            )

        if pos in self.hard_powered_blocks:
            block_type = "minecraft:black_wool"
        elif pos in self.soft_powered_blocks:
            block_type = "minecraft:gray_wool"
        else:
            block_type = "minecraft:white_wool"

        return Block(
            block_type=block_type,
            attributes=frozendict(),
        )

    def pos_blocks(self) -> PositionalData[Block]:
        return PositionalData(
            (pos, block)
            for pos in RectangularPrism(self.min_pos, self.max_pos)
            if (block := self.pos_block(pos)).block_type != "minecraft:air"
        )

    def schem(self) -> Schematic:
        return Schematic(
            pos_blocks=self.pos_blocks(),
            pos_sign_lines=PositionalData(),
        )

    def step_from_pos(self, pos: Pos) -> RedstonePathStep:
        return RedstonePathStep(
            next_pos=pos,
            is_repeater=pos in self.repeater_directions,
            facing=self.repeater_directions.get(pos),
        )

    def add_step(
        self,
        other_busses: "RedstoneBussing",
        prev_pos: Pos,
        step: RedstonePathStep,
    ) -> Optional["RedstoneBussing"]:
        """
        There are a variety of concepts here:
        - Element (wire/repeater) blocks.
        - Foundation blocks: Blocks immediately underneath wire/repeater. May be solid or transparent.
        - Spacer blocks: solid blocks placed to separate wires and connect repeaters to I/O blocks.
        - Airspace blocks: Blocks that must be clear or transparent for some wires to connect.
            - Foundation & airspace are the transparent foundation blocks. The rest are presumed solid.

        - Hard/soft powered/power-sensitive: Blocks and their power sensitivities.

        Assertions:
        [COLLISION 1] Foundation and wire/repeater blocks don't conflict with existing foundation,
            wire/repeater blocks. [CHECK]
        [COLLISION 2] Wires do not cause a spacer to conflict with an airspace block. [CHECK]
            - Foundations may conflict; they just become transparent and limit the next actions.
        [COLLISION 3] New airspace blocks don't conflict with old solid foundation or spacer
            blocks. [CHECK]
            - IE, wire does not imply a previously solid block must now be transparent.
            - We could patch this in later, but detecting whether it is safe / whether a wire is
                descending is a bit tricky.

        [CONNECTIVITY 1] Wires don't run out of signal strength. [CHECK]
        [CONNECTIVITY 2] Spacers are used in front of repeaters in descending wires. [CHECK]
        [CONNECTIVITY 3] Airspace blocks are used above de/ascending wires. [CHECK]

        [INPUT NOISE 1] Wire is not adjacent to another wire. [CHECK IN 2 PARTS]
        [INPUT NOISE 2] Wire is not adjacent to a hard-powered block. [CHECK]
        [INPUT NOISE 3] Repeater input block isn't soft-powered or hard-powered by other
            busses. [CHECK]

        [OUTPUT NOISE 1] Wire does not soft-power a soft-power-sensitive block. [CHECK]
        [OUTPUT NOISE 2] Repeater does not hard-power a hard-power-sensitive block. [CHECK]

        Additionally, RedstonePathStep.next_steps() ensures:
        [CONNECTIVITY 4] Wires cannot descend when they have a transparent foundation.
        [CONNECTIVITY 5] Two repeaters in a row must be at the same height.
        [CONNECTIVITY 6] A repeater cannot be powered by a wire below its input port.
        """
        xz_neighbor_blocks = [
            step.next_pos + direction_unit_pos[direction] for direction in xz_directions
        ]
        neighbor_blocks = [
            step.next_pos + direction_unit_pos[direction] for direction in directions
        ]
        above_block = step.next_pos + direction_unit_pos["up"]
        below_block = step.next_pos + direction_unit_pos["down"]

        prev_was_repeater = prev_pos in self.repeater_directions

        # [COLLISION 1] Foundation and wire/repeater blocks don't conflict with existing foundation,
        #     wire/repeater blocks.
        placement_blocks = {step.next_pos, below_block}
        preexisting_placement_blocks = (
            other_busses.element_blocks
            | other_busses.element_foundation_blocks
            | self.element_blocks
            | self.element_foundation_blocks
        )
        if len(placement_blocks & preexisting_placement_blocks) > 0:
            return None

        if step.is_wire:
            # [INPUT NOISE 1] Wire is not adjacent to another wire. [PART 1, dy=0]
            any_adjacent_wires = any(
                neighbor in other_busses.wire_blocks for neighbor in xz_neighbor_blocks
            )
            # [INPUT NOISE 2] Wire is not adjacent to a hard-powered block.
            any_adjacent_hard_powered_blocks = any(
                neighbor in other_busses.hard_powered_blocks
                for neighbor in neighbor_blocks
            )

            # [OUTPUT NOISE 1] Wire does not soft-power a soft-power-sensitive block.
            any_adjacent_soft_power_sensitive_blocks = (
                any(
                    neighbor in other_busses.soft_power_sensitive_blocks
                    for neighbor in xz_neighbor_blocks
                )
                or below_block in other_busses.soft_power_sensitive_blocks
            )

            if (
                any_adjacent_wires
                or any_adjacent_hard_powered_blocks
                or any_adjacent_soft_power_sensitive_blocks
            ):
                return None

        if step.is_repeater:
            assert step.facing is not None  # For MyPy.
            # [INPUT NOISE 3] Repeater input block isn't soft-powered or hard-powered by other busses.
            has_noisy_input = (
                step.next_pos + direction_unit_pos[opposite_direction[step.facing]]
            ) in other_busses.soft_powered_blocks

            # [OUTPUT NOISE 2] Repeater does not hard-power a hard-power-sensitive block.
            output_affects_others = (
                step.next_pos + direction_unit_pos[step.facing]
            ) in other_busses.hard_power_sensitive_blocks

            if has_noisy_input or output_affects_others:
                return None

        if step.is_repeater:
            next_sig_strength = 15
        else:
            next_sig_strength = self.element_sig_strengths[prev_pos] - 1

        # [CONNECTIVITY 1] Wires don't run out of signal strength.
        if next_sig_strength == 0:
            return None

        if step.is_repeater:
            repeater_directions = self.repeater_directions.set(  # type: ignore
                step.next_pos, step.facing
            )
        else:
            repeater_directions = self.repeater_directions

        new_spacer_blocks = set()

        # [CONNECTIVITY 2] Spacers are used in front of repeaters in descending wires.
        if prev_was_repeater and step.next_pos.y < prev_pos.y:
            new_spacer_blocks.add(step.next_pos + direction_unit_pos["up"])

        # [INPUT NOISE 1] Wire is not adjacent to another wire. [PART 2, dy != 0]
        if step.is_wire:
            if any(
                (neighbor + direction_unit_pos["up"]) in other_busses.wire_blocks
                for neighbor in xz_neighbor_blocks
            ):
                new_spacer_blocks.add(step.next_pos + direction_unit_pos["up"])

            new_spacer_blocks |= set(
                neighbor_block
                for neighbor_block in xz_neighbor_blocks
                if (
                    (neighbor_block + direction_unit_pos["down"])
                    in other_busses.wire_blocks
                )
            )

        spacer_blocks = self.spacer_blocks | frozenset(new_spacer_blocks)

        # [CONNECTIVITY 3] Airspace blocks are used above de/ascending wires. [CHECK]
        new_airspace_blocks = set()
        if step.next_pos.y < prev_pos.y:
            new_airspace_blocks.add(above_block)
        if step.next_pos.y > prev_pos.y:
            new_airspace_blocks.add(prev_pos + direction_unit_pos["up"])

        airspace_blocks = self.airspace_blocks | frozenset(new_airspace_blocks)

        # [COLLISION 2] Wires do not cause a spacer to conflict with an airspace block.
        if len(airspace_blocks & spacer_blocks) != 0:
            return None

        # [COLLISION 3] New airspace blocks don't conflict with old solid foundation or spacer blocks.
        if (
            len(
                (other_busses.foundation_blocks | other_busses.spacer_blocks)
                & (new_airspace_blocks - other_busses.airspace_blocks)
            )
            != 0
        ):
            return None

        return RedstoneBussing(
            element_sig_strengths=self.element_sig_strengths.set(  # type: ignore
                step.next_pos, next_sig_strength
            ),
            repeater_directions=repeater_directions,
            spacer_blocks=spacer_blocks,
            airspace_blocks=airspace_blocks,
        )


XZDirection = Literal["north", "east", "south", "west"]
# any_up is either straight_up or slant_up.
# The actual direction is ambiguous until the following step.
BusYDirection = Literal["straight_up", "slant_up", "any_up", "flat", "slant_down"]


momentum_expected_step_poses: dict[tuple[XZDirection, BusYDirection], set[Pos]] = {
    xz_y_dir: poses
    for xz_direction in xz_directions
    for xz_y_dir, poses in cast(
        dict[tuple[XZDirection, BusYDirection], set[Pos]],
        {
            (xz_direction, "straight_up"): {
                direction_unit_pos[opposite_direction[xz_direction]] + Pos(0, 1, 0)
            },
            (xz_direction, "slant_up"): {
                direction_unit_pos[xz_direction] + Pos(0, 1, 0)
            },
            (xz_direction, "any_up"): {
                direction_unit_pos[opposite_direction[xz_direction]] + Pos(0, 1, 0),
                direction_unit_pos[xz_direction] + Pos(0, 1, 0),
            },
            (xz_direction, "flat"): {direction_unit_pos[xz_direction]},
            (xz_direction, "slant_down"): {
                direction_unit_pos[xz_direction] + Pos(0, -1, 0)
            },
        },
    ).items()
}


class PartialBus(NamedTuple):
    # Where we're currently at.
    current_position: Pos

    # The actual blocks/airspaces/etc for the (incomplete) bus.
    current_bussing: RedstoneBussing

    # Momentum: Changing directions is arbitrary; don't do it often.
    # None for the first step. After, None
    momentum_xz_dir: XZDirection | None
    momentum_y_dir: BusYDirection | None


def _next_momentum_xy_z_and_momentum_broken(
    state: PartialBus,
    action: RedstonePathStep,
) -> tuple[XZDirection, BusYDirection, bool]:
    step = action.next_pos - state.current_position
    step_xz_dir = cast(XZDirection, unit_pos_direction[step.xz_pos()])

    # Vague momentum term: Not specific to straight_up or slant_up.
    step_y_dir = cast(
        dict[int, BusYDirection],
        {
            1: "any_up",
            0: "flat",
            -1: "slant_down",
        },
    )[int(step.y)]

    no_momentum_history = state.momentum_xz_dir is None or state.momentum_y_dir is None
    if no_momentum_history:
        momentum_broken = False
    else:
        # For MyPy.
        assert state.momentum_xz_dir is not None and state.momentum_y_dir is not None

        momentum_broken = (
            step
            not in momentum_expected_step_poses[
                (state.momentum_xz_dir, state.momentum_y_dir)
            ]
        )

    momentum_xz_dir = step_xz_dir

    if no_momentum_history or momentum_broken:  # When beginning / resetting
        momentum_y_dir: BusYDirection = step_y_dir
    else:  # When continuing a straight line

        # For MyPy.
        assert state.momentum_xz_dir is not None and state.momentum_y_dir is not None

        if step_y_dir == "any_up":
            if state.momentum_y_dir != "any_up":  # No inference necessary; just copy.
                momentum_y_dir = state.momentum_y_dir
            else:  # Infer from direction alignment.
                momentum_y_dir = (
                    "slant_up" if momentum_xz_dir == step_xz_dir else "straight_up"
                )
        else:
            momentum_y_dir = step_y_dir

    return momentum_xz_dir, momentum_y_dir, momentum_broken


@dataclass
class RedstonePathFindingProblem(
    PathSearchProblem[PartialBus | None, RedstonePathStep]
):
    """
    Initial context:
    - Set of other busses' wire blocks.
    - Set of other busses' foundation and cover blocks.
    - Set of blocks that would cover/cut off another busses' wires
    - Set of hard-powered blocks (from other busses' repeaters)

    Path context:
    - Set of wire blocks
        - Set of foundation blocks (implied as wire blocks + Pos(0, -1, 0)
    - Set of spacer blocks for insulating this bus from others.
    - Mapping of wire block -> signal strength
    - Set of repeater blocks

    Steps:
    - Are the current point and signal strength, with path context.
    - Must add a new repeater or wire.
    - May add repeaters:
        - Prematurely, though this is costly.
        - Flat with the current line.
        - One step down from the current line.
    - May add wires:
        - Going straight/up/down


    Example:
    >>> problem = RedstonePathFindingProblem(
    ...     start_pos=Pos(0, 0, 0),
    ...     stop_pos=Pos(3, 3, 0),
    ...     instance_points=set(),
    ...     other_busses=RedstoneBussing(),
    ...     repeater_cost=12,
    ...     momentum_break_cost=3,
    ... )

    >>> steps = a_star_bfs_searched_solution(problem, max_steps=500)

    # >>> pprint(steps)
    # [RedstonePathStep(next_pos=Pos(1, 1, 0), is_repeater=False, facing=None),
    #  RedstonePathStep(next_pos=Pos(2, 2, 0), is_repeater=False, facing=None),
    #  RedstonePathStep(next_pos=Pos(3, 3, 0), is_repeater=False, facing=None)]

    >>> state = problem.initial_state()
    >>> for step in steps:
    ...     state = problem.state_action_result(state, step)

    >>> pprint(state.current_bussing)
    RedstoneBussing(element_sig_strengths=frozendict.frozendict({Pos(0, 0, 0): 15, ..., Pos(3, 3, 0): 12}),
                    repeater_directions=frozendict.frozendict({}),
                    spacer_blocks=frozenset(),
                    airspace_blocks=frozenset({Pos(2, 3, 0),
                                               Pos(0, 1, 0),
                                               Pos(1, 2, 0)}))

    >>> pprint(state.current_bussing.schem())
    Schematic(pos_blocks={Pos(0, -1, 0): Block(block_type='minecraft:gray_wool',
                                               attributes=frozendict.frozendict({})),
                          Pos(0, 0, 0): Block(block_type='minecraft:redstone_wire',
                                              attributes=frozendict.frozendict({})),
                          ...},
              pos_sign_lines={})
    """

    start_pos: Pos
    stop_pos: Pos

    instance_points: set[Pos]
    other_busses: "RedstoneBussing"

    repeater_cost: int
    momentum_break_cost: int

    def initial_state(self) -> PartialBus:
        return PartialBus(
            current_position=self.start_pos,
            current_bussing=RedstoneBussing(
                element_sig_strengths=frozendict({self.start_pos: 15})
            ),
            momentum_xz_dir=None,
            momentum_y_dir=None,
        )

    def state_actions(self, state: PartialBus | None) -> list[RedstonePathStep]:
        # When step is invalid, we're at a dead end.
        if state is None:
            return []
        else:
            curr_step = state.current_bussing.step_from_pos(state.current_position)
            return curr_step.next_steps(
                transparent_foundation=(
                    state.current_position
                    in state.current_bussing.transparent_foundation_blocks(
                        self.other_busses.airspace_blocks
                    )
                ),
            )

    def state_action_result(
        self,
        state: PartialBus | None,
        action: RedstonePathStep,
    ) -> PartialBus | None:
        if state is None:
            return None
        else:
            (
                momentum_xz_dir,
                momentum_y_dir,
                _,
            ) = _next_momentum_xy_z_and_momentum_broken(state, action)

            next_bussing = state.current_bussing.add_step(
                self.other_busses,
                prev_pos=state.current_position,
                step=action,
            )

            if next_bussing is None:
                return None

            return PartialBus(
                current_position=action.next_pos,
                current_bussing=next_bussing,
                momentum_xz_dir=momentum_xz_dir,
                momentum_y_dir=momentum_y_dir,
            )

    def state_action_cost(
        self, state: PartialBus | None, action: RedstonePathStep
    ) -> float:
        if state is None:
            return 0
        elif state.current_position in state.current_bussing.repeater_directions:
            return self.repeater_cost
        else:
            _, _, momentum_broken = _next_momentum_xy_z_and_momentum_broken(
                state, action
            )
            if momentum_broken:
                return self.momentum_break_cost
            else:
                return 1

    def is_goal_state(self, state: PartialBus | None) -> bool:
        return (
            state is not None
            and state.current_position == self.stop_pos
            and state.current_position not in state.current_bussing.repeater_directions
        )

    def min_distance(self, state: PartialBus | None) -> float:
        if state is None:
            return 10000

        distance_vector = state.current_position - self.stop_pos

        y_distance = distance_vector.y
        xz_distance = Pos(distance_vector.x, 0, distance_vector.z).l1()

        # How many redstone steps are necessary to get there?
        min_steps = max(xz_distance, y_distance)

        return (self.repeater_cost * min_steps // 16) + min_steps


def redstone_bussing(
    start_pos: Pos,
    stop_pos: Pos,
    instance_points: set[Pos],
    other_busses: RedstoneBussing,
    max_steps: int,
) -> RedstoneBussing:
    problem = RedstonePathFindingProblem(
        start_pos=start_pos,
        stop_pos=stop_pos,
        instance_points=set(),
        other_busses=RedstoneBussing(),
        repeater_cost=12,
        momentum_break_cost=3,
    )

    steps = a_star_bfs_searched_solution(problem, max_steps=max_steps)

    state: Optional[PartialBus] = problem.initial_state()
    for step in steps:
        state = problem.state_action_result(state, step)
        if state is None:
            raise RedstoneBussingError("Bus search somehow chose an invalid path.")

    assert state is not None  # For MyPy.

    return state.current_bussing
