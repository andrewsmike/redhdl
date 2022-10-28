"""
Get a list of sub-netlist-like components from the vhdl file.
Order them by their dependency graph, then run the following logic on each:
- Parse the entity block to define the input, output instances (wires, directions, and bitwidths).
    - Check!
- Focus on the architecture block.
    - Check!
- For each instantiation block, pull the input/output spec from the previously parsed components.
    - Add instances for these. Fill in appropriate port details.
        - Find a way to deduplicate the Netlist => schematic generation here across similar units.
- Extract signal source/dest statements:
    - Represent direct references and array indexed references.
    - For each instance (inc I/O instances), create (source-deduplicated) ports for each signal.
        - Handle array logic here. Tricky stuff, but supported by the Port Slice concepts :D
    - Raise error on logic signal. (TODO: Add simple logic elements.)

Then, return the dict[name, big ole' netlist].
Schematic generation should be handled by a recursive function on NetlistInstance.

Functions of interest:
- tree_entity_ports: The IO port declarations by entity name.
    IE:
    {'Simple_Cell': {...},
     'Simple_Row': {'A': Port(port_type='in', pin_count=1),
                    'B': Port(port_type='in', pin_count=2),
                    'C': Port(port_type='out', pin_count=1),
                    'D': Port(port_type='out', pin_count=2)}}

- tree_architecture_nodes: The architecture nodes, by entity name.
- architecture_components: The components in an architecture, by name.
    ArchitectureComponents have a name, type/class, and IO port assignments to signals.

- For each instantiation block, pull the input/output spec from the previously parsed components.
    - Add instances for these. Fill in appropriate port details.
        - Find a way to deduplicate the Netlist => schematic generation here across similar units.
- Extract signal source/dest statements:
    - Represent direct references and array indexed references.
    - For each instance (inc I/O instances), create (source-deduplicated) ports for each signal.
        - Handle array logic here. Tricky stuff, but supported by the Port Slice concepts :D
    - Raise error on logic signal. (TODO: Add simple logic elements.)

TODO: Give Instances a to_schematic interface that exports port positions.
"""
from dataclasses import dataclass
from typing import Any

from redhdl.netlist import Port
from redhdl.slice import Slice
from redhdl.vhdl.parse_tree import ParseTree, parse_tree_assert_get, parse_tree_query


def range_bitwidth(range_node) -> int:
    """
    - constraint -> index_constraint -> discrete_range -> range_decl -> explicit_range
        - simple_expression -> term -> factor -> primary -> literal -> numeric_literal
            -> abstract_literal -> "1"
        - direction -> "downto"
        - simple_expression -> term -> factor -> primary -> literal -> numeric_literal
            -> abstract_literal -> "0"
    """
    assert len(range_node.children) == 3, "Expected 'X downto Y' expression."
    assert (
        parse_tree_assert_get(range_node, "direction", 0).text == "downto"
    ), "Expected 'downto' expression, got something else."

    bound_path = [
        "term",
        "factor",
        "primary",
        "literal",
        "numeric_literal",
        "abstract_literal",
        0,
    ]
    left_bound_str = parse_tree_assert_get(range_node, 0, *bound_path).text
    right_bound_str = parse_tree_assert_get(range_node, 2, *bound_path).text

    assert right_bound_str == "0", "Expected BitArray indexing to start at 0."

    return int(left_bound_str) + 1


def port_clause_ports(parse_tree: ParseTree) -> dict[str, Port]:
    """
    Array port definition:
    subtype_indication
    - selected_name -> identifier -> "unsigned"
    - constraint -> index_constraint -> discrete_range -> range_decl -> explicit_range
        - simple_expression -> term -> factor -> primary -> literal -> numeric_literal
            -> abstract_literal -> "1"
        - direction -> "downto"
        - simple_expression -> term -> factor -> primary -> literal -> numeric_literal
            -> abstract_literal -> "0"

    Binary port definition:
    - subtype_indication -> selected_name -> identifier -> "std_logic"
    """
    assert (
        parse_tree.node_type == "port_clause"
    ), "Attempted to get ports for something that wasn't a port_clause."
    interface_port_list = parse_tree_assert_get(
        parse_tree,
        "port_list",
        "interface_port_list",
    )

    port_declaration_nodes = [
        child
        for child in interface_port_list.children
        if child.node_type == "interface_port_declaration"
    ]

    port_declarations = {}
    for declaration_node in port_declaration_nodes:
        name = parse_tree_assert_get(
            declaration_node, "identifier_list", "identifier", 0
        ).text

        port_type = parse_tree_assert_get(declaration_node, "signal_mode", 0).text
        assert port_type in ("in", "out")

        signal_type = parse_tree_assert_get(
            declaration_node,
            "subtype_indication",
            "selected_name",
            "identifier",
            0,
        ).text
        assert signal_type in (
            "std_logic",
            "unsigned",
        ), f"Found unexpected signal_type: {signal_type}."
        if signal_type == "std_logic":
            bit_width = 1
        else:
            range_node = parse_tree_assert_get(
                declaration_node,
                "subtype_indication",
                "constraint",
                "index_constraint",
                "discrete_range",
                "range_decl",
                "explicit_range",
            )

            bit_width = range_bitwidth(range_node)

        port_declarations[name] = Port(port_type, bit_width)

    return port_declarations


@parse_tree_query
def tree_entity_ports(
    parse_tree: ParseTree,
    children_values: list[Any],
) -> dict[str, dict[str, Port]]:
    """
    The (name -> Port) mappings for every entity in the parse tree.

    >>> from pprint import pprint
    >>> from redhdl.vhdl.parse_tree import parse_tree_from_file

    >>> parse_tree = parse_tree_from_file("hdl_examples/simple/Simple.vhdl")

    >>> pprint(tree_entity_ports(parse_tree))
    {'Simple_Cell': {'A': Port(port_type='in', pin_count=1),
                     'B': Port(port_type='in', pin_count=1),
                     'C': Port(port_type='out', pin_count=1)},
     'Simple_Row': {'A': Port(port_type='in', pin_count=1),
                    'B': Port(port_type='in', pin_count=2),
                    'C': Port(port_type='out', pin_count=1),
                    'D': Port(port_type='out', pin_count=2)}}
    """
    return {
        entity: ports
        for child_entity_ports in children_values
        for entity, ports in child_entity_ports.items()
    }


@tree_entity_ports.register("entity_declaration")
def tree_entity_ports_entity_declaration(
    parse_tree: ParseTree,
    children_values: list[Any],
) -> dict[str, dict[str, Port]]:

    entity_name_node = parse_tree_assert_get(parse_tree, "identifier", 0)
    assert (
        entity_name_node.terminal()
    ), "Entity name node was expected to be a terminal, but was not."
    name = entity_name_node.text

    port_clause = parse_tree_assert_get(parse_tree, "entity_header", "port_clause")
    ports = port_clause_ports(port_clause)

    return {name: ports}


@parse_tree_query
def tree_architecture_nodes(
    parse_tree: ParseTree,
    children_values: list[Any],
) -> dict[str, dict[str, Port]]:
    """
    Architecture nodes, by entity name.

    >>> from pprint import pprint
    >>> from redhdl.vhdl.parse_tree import parse_tree_from_file

    >>> parse_tree = parse_tree_from_file("hdl_examples/simple/Simple.vhdl")

    >>> pprint(tree_architecture_nodes(parse_tree))
    {'Simple_Cell': ParseTree(node_type='architecture_body',
                              children=[ParseTree(node_type='ARCHITECTURE',
                                                  children=[],
                                                  text='architecture'),
                                        ParseTree(node_type='identifier',
                              ...),
     'Simple_Row': ParseTree(node_type='architecture_body',
                             ...)}
    """
    return {
        entity_name: node
        for child_nodes in children_values
        for entity_name, node in child_nodes.items()
    }


@tree_architecture_nodes.register("architecture_body")
def tree_architecture_nodes_architecture_body(
    parse_tree: ParseTree,
    children_values: list[Any],
) -> dict[str, ParseTree]:
    entity_name = parse_tree_assert_get(parse_tree, 3, 0).text
    return {entity_name: parse_tree}


@dataclass
class ArchitectureComponent:
    instance_name: str
    entity_type_name: str
    port_exprs: dict[tuple[str, Slice], ParseTree]


def association_element_name_slice_expr(
    parse_tree: ParseTree,
) -> tuple[str, Slice, ParseTree]:
    return (
        parse_tree_assert_get(parse_tree, "formal_part", "identifier", 0).text,
        Slice(1),  # TODO: Real slice parsing.
        parse_tree_assert_get(
            parse_tree, "actual_part", "actual_designator", "expression"
        ),
    )


def component_port_exprs(parse_tree: ParseTree) -> dict[tuple[str, Slice], ParseTree]:
    assoc_list = parse_tree_assert_get(
        parse_tree, "port_map_aspect", "association_list"
    )

    # Filter out the ',' terminals.
    assoc_elements = [
        node for node in assoc_list.children if node.node_type == "association_element"
    ]

    return {
        (var_name, var_slice): expr
        for assoc_element in assoc_elements
        for var_name, var_slice, expr in (
            association_element_name_slice_expr(assoc_element),
        )
    }


@parse_tree_query
def architecture_components(
    parse_tree: ParseTree,
    children_values: list[Any],
) -> dict[str, ArchitectureComponent]:
    """
    >>> from pprint import pprint
    >>> from redhdl.vhdl.parse_tree import parse_tree_from_file

    >>> parse_tree = parse_tree_from_file("hdl_examples/simple/Simple.vhdl")

    >>> pprint(architecture_components(parse_tree))
    {'SimpleCell_i0': ArchitectureComponent(instance_name='SimpleCell_i0',
                                            entity_type_name='Simple_Cell',
                                            port_exprs={('A', Slice(0, 1, 1)): ParseTree(node_type='expression',
                                                                                         ...),
                                                        ...}),
     ...}

    """
    return {
        entity_name: architecture_component
        for child_components in children_values
        for entity_name, architecture_component in child_components.items()
    }


@architecture_components.register("component_instantiation_statement")
def architecture_components_component_instantiation(
    parse_tree: ParseTree,
    children_values: list[Any],
) -> dict[str, ArchitectureComponent]:
    instance_name = parse_tree_assert_get(
        parse_tree, "label_colon", "identifier", 0
    ).text
    entity_type_name = parse_tree_assert_get(
        parse_tree, "instantiated_unit", "name", "identifier", 0
    ).text

    return {
        instance_name: ArchitectureComponent(
            instance_name=instance_name,
            entity_type_name=entity_type_name,
            port_exprs=component_port_exprs(parse_tree),
        )
    }
