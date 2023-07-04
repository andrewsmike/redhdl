"""
Define minecraft Blocks and Schematics; load and save schematics.

>>> schem = load_schem("schematic_examples/hdl_diagonal_not.schem")
>>> pprint(schem)
Schematic(pos_blocks={Pos(0, 0, 0): Block(block_type='minecraft:oak_wall_sign',
                                          attributes=frozendict.frozendict({'facing': 'north', 'waterlogged': 'false'})),
                      Pos(0, 0, 1): Block(block_type='minecraft:glass',
                                          attributes=frozendict.frozendict({})),
                      ...,
                      Pos(2, 2, 2): Block(block_type='minecraft:comparator',
                                          attributes=frozendict.frozendict({'facing': 'west', 'mode': 'subtract', 'powered': 'true'})),
                      Pos(3, 2, 2): Block(block_type='minecraft:gray_wool',
                                          attributes=frozendict.frozendict({})),
                      Pos(3, 2, 3): Block(block_type='minecraft:repeater',
                                          attributes=frozendict.frozendict({'delay': '1', 'facing': 'north', 'locked': 'false', 'powered': 'true'})),
                      ...},
          pos_sign_lines={Pos(0, 0, 0): ['diagonal not', 'stack i=[1x+1y]'],
                          Pos(2, 1, 0): ['input a[i]',
                                         'full soft power',
                                         'hard power'],
                          Pos(3, 1, 4): ['output b[i]',
                                         'full soft power',
                                         'full hard power'],
                          Pos(4, 3, 4): ['PLACEHOLDER']})

>>> pprint(schem.y_rotated(1))
Schematic(pos_blocks={Pos(0, 0, 0): Block(block_type='minecraft:oak_wall_sign',
                                          attributes=frozendict.frozendict({'facing': 'west', 'waterlogged': 'false'})),
                      ...,
                      Pos(1, 2, -2): Block(block_type='minecraft:repeater',
                                           attributes=frozendict.frozendict({'delay': '1', 'facing': 'west', 'locked': 'false', 'powered': 'false'})),
                      ...},
          pos_sign_lines=...)
"""

import atexit
from dataclasses import dataclass
from functools import cache
from json import loads
from subprocess import Popen
from tempfile import NamedTemporaryFile
from typing import Literal, Optional

from frozendict import frozendict
import matplotlib.pyplot as plt
from nbtlib import File as NBTFile
from nbtlib import load
from nbtlib.tag import ByteArray, Compound, Int, Short
import numpy as np

from redhdl.positional_data import PositionalData, PositionMask
from redhdl.region import (
    X_AXIS_INDEX,
    Y_AXIS_INDEX,
    Z_AXIS_INDEX,
    Direction,
    Pos,
    RectangularPrism,
    is_direction,
    xz_direction_y_rotated,
)

BlockColor = Literal[
    "white",
    "orange",
    "magenta",
    "light_blue",
    "yellow",
    "lime",
    "pink",
    "gray",
    "light_gray",
    "cyan",
    "purple",
    "blue",
    "brown",
    "green",
    "red",
    "black",
]


block_colors: list[BlockColor] = [
    "white",
    "orange",
    "magenta",
    "light_blue",
    "yellow",
    "lime",
    "pink",
    "gray",
    "light_gray",
    "cyan",
    "purple",
    "blue",
    "brown",
    "green",
    "red",
    "black",
]


@dataclass(frozen=True, order=True)
class Block:
    block_type: str
    attributes: frozendict[str, str]

    def is_air(self) -> bool:
        return self.block_type == "minecraft:air"

    def y_rotated(self, quarter_turns: int = 1) -> "Block":
        attributes = self.attributes
        if "facing" in self.attributes:
            direction: str | Direction = self.attributes["facing"]
            assert is_direction(direction)
            attributes = frozendict(
                attributes
                | {"facing": xz_direction_y_rotated(direction, quarter_turns)}
            )
        return Block(
            block_type=self.block_type,
            attributes=attributes,
        )

    def to_str(self) -> str:
        if self.attributes:
            attr_strs = [f"{key}={value}" for key, value in self.attributes.items()]
            attrs_str = f"[{','.join(attr_strs)}]"
        else:
            attrs_str = ""

        return f"{self.block_type}{attrs_str}"

    @staticmethod
    def from_str(value: str) -> "Block":
        if "[" not in value:
            return Block(block_type=value, attributes=frozendict())
        else:
            block_type, *rest = value.split("[")

            if len(rest) != 1 or rest[0][-1] != "]":
                raise ValueError(f"Invalid block attributes: {value}")
            attrs_str = rest[0][: -len("]")]

            attrs = frozendict(
                {
                    key: "=".join(value_parts)
                    for attr_str in attrs_str.split(",")
                    for key, *value_parts in (attr_str.split("="),)
                }
            )

            return Block(
                block_type=block_type,
                attributes=attrs,
            )


air_block = Block("minecraft:air", frozendict())


@dataclass
class Schematic:
    pos_blocks: PositionalData[Block]
    pos_sign_lines: PositionalData[list[str]]

    def __post_init__(self):
        if set(self.pos_sign_lines.mask()) - set(self.pos_blocks.mask()):
            raise ValueError(
                "Attempted to create schematic with inappropriate sign metadata."
            )

        if any(block.is_air() for block in self.pos_blocks.values()):
            raise ValueError("Attempted to add empty air to a schematic.")

    def y_rotated(self, quarter_turns: int) -> "Schematic":
        return Schematic(
            pos_blocks=PositionalData(
                (pos.y_rotated(quarter_turns), block.y_rotated(quarter_turns))
                for pos, block in self.pos_blocks.items()
            ),
            pos_sign_lines=PositionalData(
                (pos.y_rotated(quarter_turns), sign_lines)
                for pos, sign_lines in self.pos_sign_lines.items()
            ),
        )

    def shifted(self, offset: Pos) -> "Schematic":
        return Schematic(
            pos_blocks=self.pos_blocks.shifted(offset),
            pos_sign_lines=self.pos_sign_lines.shifted(offset),
        )

    def shift_normalized(self) -> "Schematic":
        return self.shifted(-self.rect_region().min_pos)

    def __and__(self, mask: PositionMask) -> "Schematic":
        return Schematic(
            pos_blocks=self.pos_blocks & mask,
            pos_sign_lines=self.pos_sign_lines & mask,
        )

    def __or__(self, other) -> "Schematic":
        return Schematic(
            pos_blocks=self.pos_blocks | other.pos_blocks,
            pos_sign_lines=self.pos_sign_lines | other.pos_sign_lines,
        )

    def __sub__(self, mask: PositionMask) -> "Schematic":
        return Schematic(
            pos_blocks=self.pos_blocks - mask,
            pos_sign_lines=self.pos_sign_lines - mask,
        )

    def rect_region(self) -> RectangularPrism:
        return self.pos_blocks.rect_region()

    def mask(self) -> PositionMask:
        return self.pos_blocks.mask()


def load_schem(path: str) -> Schematic:
    schem = load(path)

    if "Schematic" in schem:
        schem = schem["Schematic"]

    block_by_palette_index = {
        int(palette_index): Block.from_str(block_type)
        for block_type, palette_index in schem["Palette"].items()
    }
    width, height, length = (
        int(schem["Width"]),
        int(schem["Height"]),
        int(schem["Length"]),
    )

    # Block data is packed in YZX order.
    positions = (
        Pos(x, y, z) for y in range(height) for z in range(length) for x in range(width)
    )

    pos_blocks = PositionalData(
        {
            Pos(x, y, z): block
            for (x, y, z), palette_index in zip(positions, schem["BlockData"])
            if not (block := block_by_palette_index[int(palette_index)]).is_air()
        }
    )

    pos_sign_lines = PositionalData(
        {
            Pos(*(int(pos_elem) for pos_elem in entity["Pos"])): [
                text
                for line_index in range(1, 5)
                if (text := loads(entity[f"Text{line_index}"])["text"])
            ]
            for entity in schem.get("BlockEntities", [])
            if entity["Id"] == "minecraft:sign"
        }
    )

    return Schematic(
        pos_blocks=pos_blocks,
        pos_sign_lines=pos_sign_lines,
    )


def save_schem(schematic: Schematic, dest_path: str):
    # TODO: Save sign metadata.
    blocks = schematic.pos_blocks

    blocks = blocks.shift_normalized()

    if blocks:
        max_pos = blocks.max_pos()
    else:
        max_pos = Pos(0, 0, 0)

    block_type_palette_index = {
        block: index
        for index, block in enumerate(
            sorted(
                {block for block in blocks.values()} | {air_block},
                key=lambda block: (block.block_type, set(block.attributes.items())),
            )
        )
    }

    encoded_pos_blocks = bytearray()
    for y in range(max_pos[Y_AXIS_INDEX] + 1):
        for z in range(max_pos[Z_AXIS_INDEX] + 1):
            for x in range(max_pos[X_AXIS_INDEX] + 1):
                encoded_pos_blocks.append(
                    block_type_palette_index[blocks.get(Pos(x, y, z), air_block)]
                )

    block_palette = {
        block_type.to_str(): Int(block_type_palette_index)
        for block_type, block_type_palette_index in block_type_palette_index.items()
    }
    nbt_data = {
        "schematic": Compound(
            {
                "Version": Int(2),
                "DataVersion": Int(2584),
                "Metadata": Compound(
                    {
                        "WEOffsetX": Int(0),
                        "WEOffsetY": Int(0),
                        "WEOffsetZ": Int(0),
                    }
                ),
                "Height": Short(max_pos[Y_AXIS_INDEX] + 1),
                "Length": Short(max_pos[Z_AXIS_INDEX] + 1),
                "Width": Short(max_pos[X_AXIS_INDEX] + 1),
                "PaletteMax": Int(len(block_type_palette_index)),
                "Palette": Compound(block_palette),
                "BlockData": ByteArray(encoded_pos_blocks),
            }
        )
    }["schematic"]

    schem = NBTFile(nbt_data, gzipped=True)
    schem.root_name = "Schematic"
    schem.save(dest_path)

    return nbt_data


RGBColor = tuple[int, int, int]


def _block_color(block: Block) -> str:
    block_type_suffix_color: dict[str, str] = {
        "sign": "brown",
        #
        "glass": "cyan",
        "wool": "navy",
        #
        "wire": "crimson",
        "torch": "red",
        "repeater": "darkred",
        "comparator": "purple",
        # Shouldn't occur.
        "air": "white",
    }

    for block_type_suffix, color in block_type_suffix_color.items():
        if block.block_type.endswith(block_type_suffix):
            return color
    else:
        return color


@cache
def _plt_fig_ax_text():
    fig = plt.figure()
    ax = fig.add_subplot(projection="3d")
    text = fig.text(0.0, 0.0, "")

    return fig, ax, text


def display_schematic(schem: Schematic, desc: Optional[str] = None) -> None:
    normed_schem = schem.shift_normalized()
    region = normed_schem.rect_region()
    min_pos, max_pos = region.min_pos, region.max_pos

    if min_pos != Pos(0, 0, 0):
        raise RuntimeError(
            f"Expected shift_normalized schematic to center on Pos(0, 0, 0), not {min_pos}."
        )

    region_size = max_pos + Pos(1, 1, 1)

    block_colors = np.empty(region_size, dtype=object)  # Optional RGBColor.
    for block_pos, block in normed_schem.pos_blocks.items():
        if block.block_type == "minecraft:air":
            continue

        block_colors[block_pos] = _block_color(block)

    # In PLT, the z coordinate is up, whereas in minecraft y is up.
    # Swap the Z axis with the Y axis.
    block_colors = block_colors.transpose(
        (X_AXIS_INDEX, Z_AXIS_INDEX, Y_AXIS_INDEX),
    )

    block_mask = ~np.equal(block_colors, None)  # type: ignore

    fig, ax, text = _plt_fig_ax_text()

    ax.clear()
    ax.voxels(
        block_mask,
        facecolors=block_colors,
        edgecolor="k",
    )

    if desc:
        text.set_text(desc)

    plt.show()


@cache
def _interactive_schem_desc_paths(prefix: str) -> tuple[str, str]:
    schem_file = NamedTemporaryFile(prefix=f"{prefix}_", suffix=".schem")
    desc_file = NamedTemporaryFile(prefix=f"{prefix}_", suffix=".txt")
    display_proc = Popen(
        ["scripts/display_schem.py", schem_file.name, desc_file.name],
    )
    atexit.register(lambda: display_proc.kill())
    return schem_file.name, desc_file.name


def interactive_display_schematic(schem: Schematic, name: str, desc: str):
    schem_path, desc_file_path = _interactive_schem_desc_paths(prefix=name)
    save_schem(schem, schem_path)
    with open(desc_file_path, "w") as f:
        f.write(desc)
