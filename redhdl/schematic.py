"""
"""

from dataclasses import dataclass
from json import loads

from frozendict import frozendict
from nbtlib import File as NBTFile
from nbtlib import load
from nbtlib.tag import ByteArray, Compound, Int, Short

from redhdl.positional_data import PositionalData, PositionMask
from redhdl.region import X_AXIS, Y_AXIS, Z_AXIS, Pos, Region


@dataclass(frozen=True, order=True)
class Block:
    block_type: str
    attributes: frozendict[str, str]

    def is_air(self) -> bool:
        return self.block_type == "minecraft:air"

    def y_rotated(self, quarter_turns: int) -> "Block":
        # TODO.
        raise NotImplementedError

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
        if self.pos_sign_lines.mask() - self.pos_blocks.mask():
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
            pos_sign_lines=self.pos_sign_lines,
        )

    def shifted(self, offset: Pos) -> "Schematic":
        return Schematic(
            pos_blocks=self.pos_blocks.shifted(offset),
            pos_sign_lines=self.pos_sign_lines.shifted(offset),
        )

    def __and__(self, mask: PositionMask) -> "Schematic":
        if not isinstance(mask, set):
            raise ValueError(
                f"Attempted to __and__ Schematic to {type(mask)}; expected PositionMask."
            )

        return Schematic(
            pos_blocks=self.pos_blocks.masked(mask),
            pos_sign_lines=self.pos_sign_lines.masked(mask),
        )

    def __or__(self, other) -> "Schematic":
        return Schematic(
            pos_blocks=self.pos_blocks | other.pos_blocks,
            pos_sign_lines=self.pos_sign_lines | other.pos_sign_lines,
        )

    def rect_region(self) -> Region:
        return self.pos_blocks.rect_region()

    def mask(self) -> PositionMask:
        return self.pos_blocks.mask()


def load_schem(path: str) -> Schematic:
    schem = load(path)
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
            for entity in schem["BlockEntities"]
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

    # The original 0, 0, 0 will be where it pastes from.
    if blocks:
        we_pos = -blocks.min_pos()
    else:
        we_pos = Pos(0, 0, 0)

    blocks = blocks.shift_normalized()

    if blocks:
        max_pos = blocks.max_pos()
    else:
        max_pos = Pos(0, 0, 0)

    block_type_palette_index = {
        block_type: index
        for index, block_type in enumerate(sorted(set(blocks.values()) | {air_block}))
    }

    encoded_pos_blocks = bytearray()
    for y in range(max_pos[Y_AXIS] + 1):
        for z in range(max_pos[Z_AXIS] + 1):
            for x in range(max_pos[X_AXIS] + 1):
                encoded_pos_blocks.append(
                    block_type_palette_index[blocks.get(Pos(x, y, z), air_block)]
                )

    block_palette = {
        block_type.to_str(): Int(block_type_palette_index)
        for block_type, block_type_palette_index in block_type_palette_index.items()
    }
    nbt_data = {
        "Schematic": Compound(
            {
                "Version": Int(2),
                "DataVersion": Int(2584),
                "MetaData": Compound(
                    {
                        "WEOffsetX": Int(we_pos[X_AXIS]),
                        "WEOffsetY": Int(we_pos[Y_AXIS]),
                        "WEOffsetZ": Int(we_pos[Z_AXIS]),
                    }
                ),
                "Height": Short(max_pos[Y_AXIS] + 1),
                "Length": Short(max_pos[Z_AXIS] + 1),
                "Width": Short(max_pos[X_AXIS] + 1),
                "PaletteMax": Int(len(block_type_palette_index)),
                "Palette": Compound(block_palette),
                "BlockData": ByteArray(encoded_pos_blocks),
            }
        )
    }

    schem = NBTFile(nbt_data, gzipped=True)
    schem.save(dest_path)

    return nbt_data
