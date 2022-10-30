"""
Simple components are packaged the following way:
- Build the core circuit. This region is the "core".
- Expand the region 1 block in every direction to create the "padding" region.
    No blocks may be in the outer padding region.
- Put glass blocks on two opposing corners of the padding region.
    These enclose the area taken by the circuit, and the thin 'skin' ports
    exist in around the circuit.
- Put red or green wool blocks, with repeaters on top, in the padding region.
    These are the I/O port pins.
- Put port-describing signs on the first and last pins' mounting blocks for
    each port, such that they are outside of the core and the padding regions.
- Put an overall-description sign on the front face of a corner glass block.
    The first line should be the circuit name. The remaining lines may later
    be used to describe, IE, stacking behaviour.

Port describing signs:
- The first line should read "<input|output> <name>[<index>]", IE "input a[0]".
    Index is optional for one-bit ports: "output cout" is also acceptable.
- All other lines are currently ignored. They could be used to encode more
    sophisticated bus connecter logic.

>>> from pprint import pprint
>>> from redhdl.schematic import load_schem
>>> schem = load_schem("schematic_examples/hdl_diagonal_not.schem")
>>> pprint(schem)
Schematic(pos_blocks={Pos(0, 0, 0): Block(block_type='minecraft:oak_wall_sign',
                                          attributes=frozendict.frozendict({'facing': 'north', 'waterlogged': 'false'})),
                      Pos(0, 0, 1): Block(block_type='minecraft:glass',
                                          attributes=frozendict.frozendict({})),
                      ...
                      Pos(3, 2, 3): Block(block_type='minecraft:repeater',
                                          attributes=frozendict.frozendict({'delay': '1', 'facing': 'north', 'locked': 'false', 'powered': 'true'})),
                      Pos(4, 3, 3): Block(block_type='minecraft:glass',
                                          attributes=frozendict.frozendict({})),
                      Pos(4, 3, 4): Block(block_type='minecraft:oak_wall_sign',
                                          attributes=frozendict.frozendict({'facing': 'south', 'waterlogged': 'false'}))},
          pos_sign_lines={Pos(0, 0, 0): ['diagonal not', 'stack i=[1x+1y]'],
                          Pos(2, 1, 0): ['input a[i]',
                                         'full soft power',
                                         'hard power'],
                          Pos(3, 1, 4): ['output b[i]',
                                         'full soft power',
                                         'full hard power'],
                          Pos(4, 3, 4): ['PLACEHOLDER']})

>>> pprint(schematic_instance_from_schem(schem))
SchematicInstance(ports={'a': Port(port_type='input', pin_count=1),
                         'b': Port(port_type='output', pin_count=1)},
                  name='diagonal not',
                  schematic=Schematic(...),
                  region=RectangularPrism(Pos(0, 0, 0), Pos(2, 1, 2)),
                  port_placement={'a': RepeaterPortPlacement(positions=PositionSequence(Pos(1, 0, 0), Pos(1, 0, 0), count=1),
                                                             facing='south'),
                                  'b': RepeaterPortPlacement(positions=PositionSequence(Pos(2, 0, 2), Pos(2, 0, 2), count=1),
                                                             facing='south')})
>>> and_schem = load_schem("schematic_examples/hdl_and_h8b.schem")
>>> pprint(schematic_instance_from_schem(and_schem))
SchematicInstance(ports={'a': Port(port_type='input', pin_count=8),
                         'b': Port(port_type='input', pin_count=8),
                         'out': Port(port_type='output', pin_count=8)},
                  name='and_h8b',
                  schematic=Schematic(...),
                  region=RectangularPrism(Pos(0, 0, 0), Pos(14, 3, 2)),
                  port_placement={'a': RepeaterPortPlacement(positions=PositionSequence(Pos(0, 2, 0), Pos(14, 2, 0), count=8),
                                                             facing='south'),
                                  'b': RepeaterPortPlacement(positions=PositionSequence(Pos(0, 0, 0), Pos(14, 0, 0), count=8),
                                                             facing='south'),
                                  'out': RepeaterPortPlacement(positions=PositionSequence(Pos(0, 1, 2), Pos(14, 1, 2), count=8),
                                                               facing='south')})

>>> not_schem = load_schem("schematic_examples/hdl_not_h8b.schem")
>>> pprint(schematic_instance_from_schem(not_schem))
SchematicInstance(ports={'in': Port(port_type='input', pin_count=8),
                         'out': Port(port_type='output', pin_count=8)},
                  name='not_h8b',
                  schematic=Schematic(...),
                  region=RectangularPrism(Pos(0, 0, 0), Pos(14, 1, 3)),
                  port_placement={'in': RepeaterPortPlacement(positions=PositionSequence(Pos(0, 0, 0), Pos(14, 0, 0), count=8),
                                                              facing='south'),
                                  'out': RepeaterPortPlacement(positions=PositionSequence(Pos(0, 0, 3), Pos(14, 0, 3), count=8),
                                                               facing='south')})
"""
from re import match
from typing import cast

from redhdl.instances import RepeaterPortPlacement, SchematicInstance
from redhdl.netlist import Port, PortType
from redhdl.positional_data import PositionalData
from redhdl.region import (
    Direction,
    Pos,
    PositionSequence,
    RectangularPrism,
    direction_unit_pos,
    opposite_direction,
)
from redhdl.schematic import Schematic


def glass_corner_positions(schem: Schematic) -> tuple[Pos, Pos]:
    # Select the outer-most glass parts.
    glass_pos_blocks = PositionalData(
        (pos, block)
        for pos, block in schem.pos_blocks.items()
        if block.block_type == "minecraft:glass"
    )

    bottom_right_pos, top_left_pos = (
        glass_pos_blocks.min_pos(),
        glass_pos_blocks.max_pos(),
    )

    # TODO: This is terrible.
    assert (
        bottom_right_pos in glass_pos_blocks and top_left_pos in glass_pos_blocks
    ), "Template schematic loading is currently dumb; pls reformat glass corners."

    return bottom_right_pos, top_left_pos


def port_type_name_index(sign_text: str) -> tuple[str, str, int]:
    matches = match("(input|output) ([a-zA-Z_-]*)(\\[([0-9]+)\\])?", sign_text)
    if not matches:
        raise ValueError(f"Sign text is misformatted: {sign_text}.")

    port_type, name, index_br_str, index_str = matches.groups()
    if index_str is not None:
        index = int(index_str)
    else:
        index = 0

    return port_type, name, index


def schematic_instance_from_schem(schem: Schematic) -> SchematicInstance:
    """ """
    # Establish core and padded regions
    bottom_right_pos, top_right_pos = glass_corner_positions(schem)
    padded_region = RectangularPrism(bottom_right_pos, top_right_pos)
    core_region = RectangularPrism(
        padded_region.min_pos + Pos(1, 1, 1), padded_region.max_pos - Pos(1, 1, 1)
    )

    overall_sign_lines = schem.pos_sign_lines[bottom_right_pos - Pos(0, 0, 1)]
    schem_name = overall_sign_lines[0]

    # Schematic should be the core, plus the padded region, minus any glass.
    # We only use this in the output, 'cause the coordinates are messed up.
    # Retain the normalization offset.
    core_schem = (schem & padded_region) - {bottom_right_pos, top_right_pos}
    core_schem_normalized = core_schem.shift_normalized()
    normalized_offset = -core_schem.rect_region().min_pos

    # Get sign metadata.
    pos_port_type_name_index = {
        pos: port_type_name_index(lines[0])
        for pos, lines in (schem - padded_region).pos_sign_lines.items()
        if len(lines) > 0
        and (lines[0].startswith("input") or lines[0].startswith("output"))
    }

    port_type = {}
    port_indices: dict[str, set[int]] = {}
    port_index_position = {}
    for pos, (port_io_type, port_name, pin_index) in pos_port_type_name_index.items():
        port_type[port_name] = port_io_type
        port_indices.setdefault(port_name, set()).add(pin_index)
        port_index_position[(port_name, pin_index)] = pos

    ports = {}
    port_placement = {}
    for port_name in port_type.keys():
        pin_count = max(port_indices[port_name]) + 1
        assert (
            min(port_indices[port_name]) == 0
        ), "Port {port_name} must start with index 0."
        start_sign_pos, stop_sign_pos = (
            port_index_position[(port_name, 0)],
            port_index_position[(port_name, pin_count - 1)],
        )

        sign_facing_direction = cast(
            Direction,
            schem.pos_blocks[start_sign_pos].attributes["facing"],
        )
        sign_base_block_offset = -direction_unit_pos[sign_facing_direction]

        if port_type[port_name] == "input":
            facing = opposite_direction[sign_facing_direction]
        elif port_type[port_name] == "output":
            facing = sign_facing_direction
        else:
            raise ValueError

        ports[port_name] = Port(
            pin_count=pin_count,
            port_type=cast(PortType, port_type[port_name]),
        )

        port_placement[port_name] = RepeaterPortPlacement(
            positions=PositionSequence(
                start_sign_pos + sign_base_block_offset + normalized_offset,
                stop_sign_pos + sign_base_block_offset + normalized_offset,
                count=pin_count,
            ),
            facing=facing,
        )

    return SchematicInstance(
        name=schem_name,
        ports=cast(dict[str, Port], ports),
        schematic=core_schem_normalized,
        region=core_schem_normalized.rect_region(),
        port_placement=port_placement,
    )
