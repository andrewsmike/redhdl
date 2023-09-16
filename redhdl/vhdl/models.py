"""
Simpler, partial representation of vHDL files for generating netlists.

See analysis.py for a more thorough docstring.
"""
from dataclasses import dataclass
from pprint import pformat
from typing import cast

from redhdl.misc.bitrange import (
    BitRange,
    bitranges_equal,
    bitranges_valid,
    port_bitrange,
)
from redhdl.netlist.netlist import Port
from redhdl.vhdl.errors import (
    InvalidAssignmentBitrangeError,
    UnsupportedAssignmentExprError,
)
from redhdl.vhdl.parse_tree import ParseTree, str_from_parse_tree


@dataclass
class ConstExpr:
    value: int

    def __str__(self):
        return f"ConstExpr({self.value})"


@dataclass
class ReferenceExpr:
    var_name: str
    bitrange: BitRange | None

    def __str__(self):
        if self.bitrange is not None:
            start, end = self.bitrange
            return f"ReferenceExpr({self.var_name} ({start} downto {end}))"
        else:
            return f"ReferenceExpr({self.var_name})"


@dataclass
class ConcatExpr:
    exprs: list[ReferenceExpr | ConstExpr]

    def __str__(self):
        return f"SimpleExpr(expr='{str_from_parse_tree(self.expr)}')"


@dataclass
class SimpleExpr:
    expr: ParseTree

    def __str__(self):
        return f"SimpleExpr(expr='{str_from_parse_tree(self.expr)}')"


UnconditionalExpr = SimpleExpr | ConstExpr | ReferenceExpr | ConcatExpr


@dataclass
class CondExpr:
    conditions: list[tuple[UnconditionalExpr | None, UnconditionalExpr | None]]

    def __str__(self):
        return f"CondExpr({pformat(self.conditions)})"


Expression = UnconditionalExpr | CondExpr


def validate_assignment_bitrange_expr(
    path: str,
    bitrange: BitRange | None,
    expr: Expression,
) -> None:
    if bitrange is None:
        raise InvalidAssignmentBitrangeError(
            "[{path}] Subinstance port expression has unresolved bitrange assignment."
        )

    for unsupported_expr_cls, name in [
        (ConstExpr, "Constant"),
        (SimpleExpr, "Logical"),
        (CondExpr, "Conditional"),
    ]:
        if isinstance(expr, unsupported_expr_cls):
            raise UnsupportedAssignmentExprError(
                f"[{path}] {name} expressions aren't yet supported: {expr}."
            )


@dataclass
class ArchitectureSubinstance:
    instance_name: str
    entity_name: str
    port_exprs: dict[str, dict[BitRange | None, Expression]]

    def validate_resolved(self, arch_ports: dict[str, dict[str, Port]]):
        for port_name, bitrange_exprs in self.port_exprs.items():
            path = f"{self.entity_name}@{self.instance_name}.{port_name}"

            for bitrange, expr in bitrange_exprs.items():
                validate_assignment_bitrange_expr(path, bitrange, expr)

        for port_name in self.port_exprs.keys():
            path = f"{self.entity_name}@{self.instance_name}.{port_name}"

            port = arch_ports[self.entity_name][port_name]
            assigned_bitranges = cast(
                set[BitRange], set(self.port_exprs[port_name].keys())
            )
            if not bitranges_valid(assigned_bitranges):
                raise InvalidAssignmentBitrangeError(
                    f"[{path}] Overlapping bitrange assignments in port expressions: "
                    + f"{assigned_bitranges}."
                )

            expected_bitranges = {port_bitrange(port)}
            if not bitranges_equal(
                expected_bitranges,
                assigned_bitranges,
            ):
                raise InvalidAssignmentBitrangeError(
                    f"[{path}] Unassigned bitranges in port expression: "
                    + f"{assigned_bitranges} != {expected_bitranges}"
                )


@dataclass
class Architecture:
    name: str

    ports: dict[str, Port]
    subinstances: dict[str, ArchitectureSubinstance]
    var_bitranges: dict[str, BitRange]
    var_bitrange_assignments: dict[str, dict[BitRange, Expression]]

    @property
    def dependencies(self) -> set[str]:
        return {subinstance.entity_name for subinstance in self.subinstances.values()}


def subinstances_with_resolved_port_bitranges(
    subinstances: dict[str, ArchitectureSubinstance],
    arch_ports: dict[str, dict[str, Port]],
) -> dict[str, ArchitectureSubinstance]:

    undeclared_ports = {
        port_name
        for subinst in subinstances.values()
        for port_name in subinst.port_exprs.keys()
        if port_name not in arch_ports.get(subinst.entity_name, {})
    }
    if any(undeclared_ports):
        raise ValueError(
            f"No entity port declaration for {undeclared_ports}; can't resolve port "
            + "assignment bitwidths."
        )

    return {
        subinst_name: ArchitectureSubinstance(
            instance_name=subinst.instance_name,
            entity_name=subinst.entity_name,
            port_exprs={
                port_name: {
                    (
                        bitrange
                        if bitrange is not None
                        else port_bitrange(arch_ports[subinst.entity_name][port_name])
                    ): expr
                    for bitrange, expr in bitrange_exprs.items()
                }
                for port_name, bitrange_exprs in subinst.port_exprs.items()
            },
        )
        for subinst_name, subinst in subinstances.items()
    }


def assignments_with_resolved_bitranges(
    var_bitrange_assignments: dict[str, dict[BitRange | None, Expression]],
    var_bitranges: dict[str, BitRange],
    ports: dict[str, Port],
) -> dict[str, dict[BitRange, Expression]]:
    all_bitranges = var_bitranges | {
        port_name: port_bitrange(port) for port_name, port in ports.items()
    }
    undeclared_variables = {
        var_name
        for var_name in var_bitrange_assignments.keys()
        if var_name not in all_bitranges
    }
    if any(undeclared_variables):
        raise ValueError(
            f"Variables {undeclared_variables} isn't a port or declared variable, "
            + "can't resolve bitwidth."
        )

    return {
        var_name: {
            cast(
                BitRange,
                (bitrange if bitrange is not None else all_bitranges[var_name]),
            ): assignment
            for bitrange, assignment in bitrange_assignments.items()
        }
        for var_name, bitrange_assignments in var_bitrange_assignments.items()
    }


def ordered_arches(arches: dict[str, Architecture]) -> list[str]:
    """
    Using subinstance entity types, determine the correct architecture build order.

    Unordered by default:
    >>> from redhdl.vhdl.analysis import arches_from_vhdl_path
    >>> arches = arches_from_vhdl_path("hdl_examples/simple/Simple.vhdl")
    >>> type(arches)
    <class 'dict'>

    >>> ordered_arches(arches)
    ['Simple_Cell', 'Simple_Row']
    """
    arch_dependencies = {
        arch_name: arch.dependencies for arch_name, arch in arches.items()
    }

    specified_arches = set(arches.keys())

    ordered_arches = []

    # All unspecified arches are assumed to be preexisting and resolved elsewhere.
    unresolved_arches = set(specified_arches)
    while unresolved_arches:
        next_arches = sorted(
            arch
            for arch in unresolved_arches
            if len(arch_dependencies[arch] & unresolved_arches) == 0
        )
        if not next_arches:
            raise ValueError(
                "Failed to resolve architecture evaluation order: There must be a cycle."
                + pformat(
                    {"unresolved": unresolved_arches, "dependencies": arch_dependencies}
                )
            )

        ordered_arches.extend(next_arches)
        unresolved_arches -= set(next_arches)

    return ordered_arches
