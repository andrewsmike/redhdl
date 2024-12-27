"""
Hierarchically build up netlists and generate their schematics.
Each netlist assumes all previous (dependency) netlists have been synthesized.

TODO
- Simplify (bitrange-implicit, concat- and duplicate-filled) assignments
    - Dedup / handle pass-through mappings.
    - Atomics: Input signals (by bitrange), outputs of subentities,
        constants, and SimpleExpr's
    - Combine parallel compatible assignments (IE, combine A[0-7] & A[8-11] => a[0-11])
- Constant network input value generation


- Multiple destinations from same source D::::
- Schematic generation should be handled by a recursive function on NetlistInstance.
    - Give Instances a to_schematic interface that exports port positions.
- Raise on logic expressions
- Replace logic exprs with new instances, networks
    - Create "logical instance" that just encodes the operator and bitwidth.
        - Have them pull in the stride from the input/output
- Propagate preferred bitwidth across networks / between netlists for generated / logical units
"""

from string import ascii_uppercase
from typing import Any

from redhdl.misc.bitrange import BitRange, bitrange_slice, port_bitrange
from redhdl.misc.slice import Slice
from redhdl.netlist.netlist import Instance, Port
from redhdl.netlist.netlist_template import (
    InstanceConfig,
    InstanceId,
    PortSliceAssignments,
)
from redhdl.vhdl.analysis import arches_from_vhdl_path
from redhdl.vhdl.models import ReferenceExpr, VHDLArchitectureName


def _camel_case(value: str) -> str:
    return "_".join(
        ((part[0].upper() + part[1:]) if part else "") for part in value.split("_")
    )


def _snake_from_camel(value: str) -> str:
    """
    >>> _snake_from_camel("HelloWorld")
    'hello_world'
    """
    parts = []
    while value:
        for i, char in enumerate(value):
            if i > 0 and char in ascii_uppercase:
                parts.append(value[:i].lower())
                value = value[i:]
        else:
            parts.append(value)
            value = ""

    return "_".join(part.lower() for part in parts)


def _normalized_vhdl_name(value: str) -> str:
    value = _snake_from_camel(value)

    for padding_name in [
        "Inst",
        "Sig",
        "Readable",
        "Module",
    ]:
        value = value.replace("_" + padding_name, "")
        value = value.replace("_" + padding_name.lower(), "")

    return value


def _normalized_port_bitrange(
    port_bitrange: tuple[tuple[str, str], BitRange],
) -> tuple[tuple[str, str], Slice]:
    (inst_name, port_name), bitrange = port_bitrange
    return (
        (_normalized_vhdl_name(inst_name), _normalized_vhdl_name(port_name)),
        bitrange_slice(bitrange),
    )


# TODO: Simplify and break apart this method.
def netlist_template_from_vhdl_path(  # noqa: C901
    vhdl_path: str, module_name: str
) -> tuple[dict[InstanceId, InstanceConfig], PortSliceAssignments]:
    arches = arches_from_vhdl_path(vhdl_path)

    possible_arch_names = [
        f"{_camel_case(module_name)}_module",
        _camel_case(module_name),
    ]
    for arch_name in possible_arch_names:
        vhdl_arch_name = VHDLArchitectureName(arch_name)
        if vhdl_arch_name in arches:
            arch = arches[vhdl_arch_name]
            break
    else:
        raise RuntimeError("Could not find module in generated VHDL files.")

    instance_configs: dict[str, InstanceConfig] = {
        _normalized_vhdl_name(instance.instance_name): {
            "schem_name": instance.instance_type.lower(),
        }
        for instance in arch.subinstances.values()
    }

    arch_io_ports = {
        (arch_name, port_name): port
        for arch_name, arch in arches.items()
        for port_name, port in arch.ports.items()
    }

    arch_bitranges = arch.var_bitranges | {
        io_port_name: port_bitrange(io_port)
        for io_port_name, io_port in arch.ports.items()
    }

    # TODO: Validate these, handle arbitrary slices
    wire_range_ports: Any = {}
    for subinst_name, subinstance in arch.subinstances.items():
        for port_name, port_bitrange_exprs in subinstance.port_exprs.items():
            for assignment_bitrange, assignment_expr in port_bitrange_exprs.items():
                if isinstance(assignment_expr, ReferenceExpr):
                    wire_name = assignment_expr.var_name
                    wire_bitrange = (
                        assignment_expr.bitrange or arch_bitranges[wire_name]
                    )
                    wire_range_ports.setdefault((wire_name, wire_bitrange), set()).add(
                        ((subinst_name, port_name), assignment_bitrange)
                    )
                else:
                    raise ValueError(
                        "Only ReferencExprs are supported in synthesis today."
                    )

    for port_name, port in arch.ports.items():
        bitrange = arch_bitranges[port_name]
        if port.port_type == "in":
            wire_range_ports.setdefault((port_name, bitrange), set()).add(
                (("input", port_name), bitrange)
            )
        elif port.port_type == "out":
            wire_range_ports.setdefault((port_name, bitrange), set()).add(
                (("output", port_name), bitrange)
            )
        else:
            raise ValueError(f"Port type unrecognized: {port.port_type}")

    # TODO: Switch to generic assignment resolution scheme.
    # This is made all the more complicated due to slicing.
    # It may be simpler to resolve everything into specific bitindices for the core
    # logic, then do grouping at the end.
    wire_groups: Any = []
    for wire_name, bitrange_assignments in arch.var_bitrange_assignments.items():
        for bitrange, assignment in bitrange_assignments.items():
            # TODO: Hande bitranges
            assert bitrange == (0, 7)
            if isinstance(assignment, ReferenceExpr):
                wire_group = {wire_name, assignment.var_name}
                for other_wire_group in wire_groups:
                    if len(wire_group & other_wire_group) != 0:
                        other_wire_group |= wire_group
                        break
                else:
                    wire_groups.append(wire_group)
            else:
                raise ValueError("Cannot handle non-alias references today.")

    wire_aliases = {
        wire: "_".join(sorted(wire_group))  # Slightly inefficient
        for wire_group in wire_groups
        for wire in wire_group
    }

    aliased_wire_range_ports: Any = {}
    for (wire_name, wire_bitrange), port_ranges in wire_range_ports.items():
        aliased_wire_range_ports.setdefault(
            (wire_aliases.get(wire_name, wire_name), wire_bitrange),
            set(),
        ).update(port_ranges)

    output_ports = {
        (subinst_name, port_name)
        for subinst_name, subinstance in arch.subinstances.items()
        for port_name, port_bitrange_exprs in subinstance.port_exprs.items()
        if arches[subinstance.instance_type].ports[port_name].port_type == "out"
    } | {
        ("input", port_name)
        for port_name, port in arch.ports.items()
        if port.port_type == "in"
    }

    wire_range_driver_port_bitrange = {
        wire_range: (port, bitrange)
        for wire_range, port_bitranges in aliased_wire_range_ports.items()
        for (port, bitrange) in port_bitranges
        if port in output_ports
    }

    sv_port_slice_assignments = {
        (port, bitrange): wire_range_driver_port_bitrange[wire_range]
        for wire_range, port_bitranges in aliased_wire_range_ports.items()
        for (port, bitrange) in port_bitranges
        if port not in output_ports
    }

    port_slice_assignments: PortSliceAssignments = {
        _normalized_port_bitrange(dst_port_bitrange): _normalized_port_bitrange(
            src_port_bitrange
        )
        for dst_port_bitrange, src_port_bitrange in sv_port_slice_assignments.items()
    }

    return (
        instance_configs,
        port_slice_assignments,
    )


_vhdl_stub_template = """\
module {module_name} ({port_specs_str});
endmodule"""


def _port_spec_str(port: Port, port_name: str) -> str:
    """The SystemVerilog module argument string for a given port."""

    port_type_str = {
        "in": "input ",
        "out": "output",
    }[port.port_type]

    if port.pin_count == 1:
        bitrange_expr = ""
    else:
        bitrange_expr = f" [{port.pin_count-1: 2} : 0]"

    return f"{port_type_str}{bitrange_expr} {_camel_case(port_name)}"


def vhdl_stub_from_instance(instance: Instance, module_name: str) -> str:
    """The SystemVerilog string for a module stub for a given instance."""

    port_spec_strs = [
        _port_spec_str(port, port_name) for port_name, port in instance.ports.items()
    ]

    if len(port_spec_strs) == 0:
        port_specs_str = ""
    else:
        port_specs_str = "\n\t" + ",\n\t".join(port_spec_strs) + "\n"

    return _vhdl_stub_template.format(
        module_name=_camel_case(module_name),
        port_specs_str=port_specs_str,
    )
