"""
Boil iverlog-generated vHDL files down to a set of netlist-like Architecture objects.

# Top-level example
>>> arches = arches_from_vhdl_path("hdl_examples/simple/Simple.vhdl")
>>> pprint(arches)
{'Simple_Cell': Architecture(name='Simple_Cell',
                             ports={'A': Port(port_type='in', pin_count=1),
                                    'B': Port(port_type='in', pin_count=1),
                                    'C': Port(port_type='out', pin_count=1)},
                             subinstances={},
                             var_bitranges={'L': (0, 0)},
                             var_bitrange_assignments={'C': {(0, 0): ...},...}),
 'Simple_Row': Architecture(...)}


# Architecture field details
Below are the helpers that are used to populate Architecture fields. These fully specify
Architecture semantics, except for the assignment bitrange resolution pass _currently_
performed in `arches_from_vhdl_path`.

How do we derive a single Netlist level from a given architecture in a vHDL AST?
We need a few things.
>>> parse_tree = parse_tree_from_file("hdl_examples/simple/Simple.vhdl")

We need to know the Netlist's I/O spec:
>>> pprint(architecture_ports(parse_tree)["Simple_Row"])
{'A': Port(port_type='in', pin_count=1),
 'B': Port(port_type='in', pin_count=2),
 'C': Port(port_type='out', pin_count=1),
 'D': Port(port_type='out', pin_count=2)}


We need to know what (sub)instances are part of the Netlist, and their types:
>>> pprint(architecture_subinstances(parse_tree)["Simple_Row"])
{'SimpleCell_i0': ArchitectureSubinstance(instance_name='SimpleCell_i0',
                                          entity_name='Simple_Cell',
                                          ...}),
 'SimpleCell_i1': ArchitectureSubinstance(...)}


We need to know what networks are used in the Netlist, and their bitwidths:
>>> pprint(architecture_local_var_bitrange(parse_tree)["Simple_Row"])
{'L': (0, 2),
 'LPM_d0_ivl_32': (0, 0),
 ...,
 'tmp_ivl_21': (0, 30),
 'tmp_ivl_22': (0, 31),
 ...,
 'tmp_ivl_9': (0, 0)}

We need to know how each instance's I/O ports connect to the networks:
>>> pprint(architecture_subinstances(parse_tree)["Simple_Row"]["SimpleCell_i0"])
ArchitectureSubinstance(instance_name='SimpleCell_i0',
                        entity_name='Simple_Cell',
                        port_exprs={('A', None): AliasExpr(var_name='LPM_q_ivl_0',
                                                           bitrange=None),
                                    ('B', None): AliasExpr(var_name='A',
                                                           bitrange=None),
                                    ('C', None): AliasExpr(var_name='LPM_d0_ivl_32',
                                                           bitrange=None)})

Finally, we need to know how networks are sourced from each other (using simple logical expressions):
>>> var_assignments = architecture_var_assignments(parse_tree)["Simple_Row"]
>>> pprint(var_assignments)
{'C': {None: SimpleExpr(...)},
 'D': {(0, 0): AliasExpr(var_name='tmp_ivl_31', bitrange=None)},
 'L': {None: ConcatExpr(exprs=[AliasExpr(var_name='tmp_ivl_35', bitrange=None),
                               AliasExpr(var_name='tmp_ivl_13', bitrange=None),
                               AliasExpr(var_name='tmp_ivl_9', bitrange=None)])},
 ...
 'tmp_ivl_9': {None: AliasExpr(var_name='A', bitrange=None)}}

>>> (l_bit_ranges := var_assignments["C"].keys())
dict_keys([None])
>>> print(str_from_parse_tree(var_assignments["C"][None].expr))
tmp_ivl_15 and tmp_ivl_24
"""
from typing import Any, cast

from redhdl.misc.bitrange import BitRange, bitrange_width
from redhdl.netlist.netlist import Port
from redhdl.vhdl.models import (
    AliasExpr,
    Architecture,
    ArchitectureSubinstance,
    ConcatExpr,
    CondExpr,
    ConstExpr,
    Expression,
    SimpleExpr,
    UnconditionalExpr,
    assignments_with_resolved_bitranges,
    subinstances_with_resolved_port_bitranges,
)
from redhdl.vhdl.parse_tree import (
    ParseTree,
    called_on_node_type,
    children_of_type,
    parse_tree_assert_get,
    parse_tree_from_file,
    parse_tree_get,
    parse_tree_query,
)


@called_on_node_type("explicit_range")
def explicit_range_bitrange(range_node: ParseTree) -> BitRange:
    """
    Range is inclusive.

    - explicit_range
        - simple_expression -> term -> factor -> primary -> literal -> numeric_literal
            -> abstract_literal -> "1"
        - direction -> "downto"
        - simple_expression -> term -> factor -> primary -> literal -> numeric_literal
        -> abstract_literal -> "0"

    >>> explicit_range_bitrange(parsed("1 downto 0", "explicit_range"))
    (0, 1)
    >>> explicit_range_bitrange(parsed("8", "explicit_range"))
    (8, 8)
    """
    direction_node = parse_tree_get(range_node, "direction", 0)
    assert (
        direction_node is None or direction_node.text == "downto"
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
    upper_bound_str = parse_tree_assert_get(range_node, 0, *bound_path).text
    lower_bound_node = parse_tree_get(range_node, 2, *bound_path)
    if lower_bound_node is None:
        lower_bound_str = upper_bound_str
    else:
        lower_bound_str = lower_bound_node.text

    return (int(lower_bound_str), int(upper_bound_str))


@called_on_node_type("subtype_indication")
def subtype_indication_bitrange(parse_tree: ParseTree) -> BitRange:
    signal_type = parse_tree_assert_get(
        parse_tree,
        "selected_name",
        "identifier",
        0,
    ).text
    assert signal_type in (
        "std_logic",
        "unsigned",
    ), f"Found unexpected signal_type: {signal_type}."

    if signal_type == "std_logic":
        start, stop = 0, 0
    else:
        range_node = parse_tree_assert_get(
            parse_tree,
            "constraint",
            "index_constraint",
            "discrete_range",
            "range_decl",
            "explicit_range",
        )

        start, stop = explicit_range_bitrange(range_node)

    return (start, stop)


@called_on_node_type("port_clause")
def port_clause_ports(parse_tree: ParseTree) -> dict[str, Port]:
    """
    Array port definition:
    subtype_indication
    - selected_name -> identifier -> "unsigned"
    - constraint -> index_constraint -> discrete_range -> range_decl -x> explicit_range
        - simple_expression -> term -> factor -> primary -> literal -> numeric_literal
            -> abstract_literal -> "1"
        - direction -> "downto"
        - simple_expression -> term -> factor -> primary -> literal -> numeric_literal
            -> abstract_literal -> "0"

    Binary port definition:
    - subtype_indication -> selected_name -> identifier -> "std_logic"

    >>> port_clause_node = parsed('''
    ...   port (
    ...     A : in std_logic;
    ...     B : in unsigned(1 downto 0);
    ...     C : out std_logic;
    ...     D : out unsigned(1 downto 0)
    ...   );
    ... ''', "port_clause")
    >>> pprint(port_clause_ports(port_clause_node))
    {'A': Port(port_type='in', pin_count=1),
     'B': Port(port_type='in', pin_count=2),
     'C': Port(port_type='out', pin_count=1),
     'D': Port(port_type='out', pin_count=2)}
    """
    interface_port_list = parse_tree_assert_get(
        parse_tree,
        "port_list",
        "interface_port_list",
    )

    port_declaration_nodes = children_of_type(
        interface_port_list,
        "interface_port_declaration",
    )

    port_declarations = {}
    for declaration_node in port_declaration_nodes:
        name = parse_tree_assert_get(
            declaration_node, "identifier_list", "identifier", 0
        ).text

        port_type = parse_tree_assert_get(declaration_node, "signal_mode", 0).text
        assert port_type in ("in", "out")

        bitrange = subtype_indication_bitrange(
            parse_tree_assert_get(declaration_node, "subtype_indication")
        )

        port_declarations[name] = Port(port_type, bitrange_width(bitrange))

    return port_declarations


@parse_tree_query
def architecture_ports(
    parse_tree: ParseTree,
    children_values: list[Any],
) -> dict[str, dict[str, Port]]:
    """
    The (name -> Port) mappings for every entity in the parse tree.

    >>> parse_tree = parse_tree_from_file("hdl_examples/simple/Simple.vhdl")

    >>> pprint(architecture_ports(parse_tree))
    {'Simple_Cell': {'A': Port(port_type='in', pin_count=1),
                     'B': Port(port_type='in', pin_count=1),
                     'C': Port(port_type='out', pin_count=1)},
     'Simple_Row': {'A': Port(port_type='in', pin_count=1),
                    'B': Port(port_type='in', pin_count=2),
                    'C': Port(port_type='out', pin_count=1),
                    'D': Port(port_type='out', pin_count=2)}}

    >>> entity_decl_node = parsed('''
    ... entity Simple_Row is
    ...   port (
    ...     A : in std_logic;
    ...     B : in unsigned(1 downto 0);
    ...     C : out std_logic;
    ...     D : out unsigned(1 downto 0)
    ...   );
    ... end entity;
    ... ''', "entity_declaration")
    >>> pprint(architecture_ports_entity_declaration(entity_decl_node, []))
    {'Simple_Row': {'A': Port(port_type='in', pin_count=1),
                    'B': Port(port_type='in', pin_count=2),
                    'C': Port(port_type='out', pin_count=1),
                    'D': Port(port_type='out', pin_count=2)}}
    """
    return {
        entity: ports
        for child_architecture_ports in children_values
        for entity, ports in child_architecture_ports.items()
    }


@architecture_ports.register("entity_declaration")
def architecture_ports_entity_declaration(
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


ArchitectureName = str


@parse_tree_query
def tree_architecture_nodes(
    parse_tree: ParseTree,
    children_values: list[Any],
) -> dict[ArchitectureName, ParseTree]:
    """
    Architecture nodes, by entity name.

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
) -> dict[ArchitectureName, ParseTree]:
    entity_name = parse_tree_assert_get(parse_tree, 3, 0).text
    return {entity_name: parse_tree}


def const_from_quoted_str(value: str) -> int:
    """
    >>> const_from_quoted_str("1")
    1
    >>> const_from_quoted_str('X"00aA"')
    170
    >>> const_from_quoted_str('"1000"')
    8
    >>> const_from_quoted_str("'Z'")
    0
    """
    if value.startswith("X"):
        base = 16
        prefix_stripped_value = value[1:]
    else:
        base = None
        prefix_stripped_value = value

    quote_chars = "'\""
    is_quoted = (prefix_stripped_value[0] in quote_chars) and (
        prefix_stripped_value[-1] in quote_chars
    )
    if not is_quoted and any(
        quote_char in prefix_stripped_value for quote_char in quote_chars
    ):
        raise ValueError(f"Literal is inconsistently quoted: {prefix_stripped_value}")

    if base is None:
        base = 2 if is_quoted else 10

    if is_quoted:
        raw_value = prefix_stripped_value[1:-1]
    else:
        raw_value = prefix_stripped_value

    if raw_value == "Z":
        return 0

    return int(raw_value, base=base)


_index_path = [
    "function_call_or_indexed_name_part",
    "actual_parameter_part",
    "association_list",
    "association_element",
    "actual_part",
    "actual_designator",
    "expression",
    "relation",
    "shift_expression",
    "simple_expression",
    "term",
    "factor",
    "primary",
    "literal",
    "numeric_literal",
    "abstract_literal",
]

_bitrange_base_path = [
    "slice_name_part",
    "discrete_range",
    "range_decl",
    "explicit_range",
]

_bitrange_each_index_path = [
    # There are multiple simple_expressions per explicit_range. Use children_of_type().
    # "simple_expression",
    "term",
    "factor",
    "primary",
    "literal",
    "numeric_literal",
    "abstract_literal",
    0,
]


@called_on_node_type("name_part")
def bitrange_from_name_part(name_part_node: ParseTree) -> BitRange | None:
    index_node = parse_tree_get(name_part_node, *_index_path)
    if index_node is not None:
        index = int(index_node.children[0].text)
        return (index, index)

    index_range_base_node = parse_tree_get(name_part_node, *_bitrange_base_path)
    if index_range_base_node is None:
        raise ValueError("Expected either bit index or bit range, found neither.")

    indices = [
        int(index_node.text)
        for child in children_of_type(index_range_base_node, "simple_expression")
        if (index_node := parse_tree_get(child, *_bitrange_each_index_path)) is not None
    ]
    if len(indices) != 2:
        raise ValueError("Bitrange AST looks malformed.")

    return cast(tuple[int, int], tuple(sorted(indices)))  # For MyPy.


_alias_base_path = [
    "factor",
    "primary",
]


_alias_identifier_node_paths = [
    _alias_base_path + ["name", "identifier"],
    _alias_base_path + ["literal", "enumeration_literal", "identifier"],
]


@called_on_node_type("term")
def alias_from_term_node(alias_expr_node: ParseTree) -> AliasExpr | None:
    """
    Direct alias:
    expression -> relation -> shift_expression -> simple_expression
        -> term -> factor -> primary -> literal -> enumeration_literal -> identifier

    Alias with indices:
    expression -> relation -> shift_expression -> simple_expression
        -> term -> factor -> primary -> name, then:

        Name:
        -> identifier

        Bit-index:
        -> name_part -> function_call_or_indexed_name_part -> actual_parameter_part
            -> association_list -> association_element -> actual_part -> actual_designator
            -> expression -> ... -> literal -> numeric_literal -> abstract_literal

        Bit-range
        -> name_part -> slice_name_part -> discrete_range -> range_decl -> explicit_range
            -2x-> simple_expression -> term -> factor -> primary -> literal
            -> numeric_literal -> abstract_literal -> <TOKEN>

    Aliases get parsed into AliasExpr objects:
    >>> alias_from_term_node(parsed("tmp_ivl_21", "term"))
    AliasExpr(var_name='tmp_ivl_21', bitrange=None)

    Bit indices are handled:
    >>> alias_from_term_node(parsed("tmp_ivl_21(2)", "term"))
    AliasExpr(var_name='tmp_ivl_21', bitrange=(2, 2))

    Bit ranges are handled:
    >>> alias_from_term_node(parsed("tmp_ivl_21(4 downto 2)", "term"))
    AliasExpr(var_name='tmp_ivl_21', bitrange=(2, 4))
    """
    alias_nodes = [
        child_node
        for alias_id_node_path in _alias_identifier_node_paths
        if (
            child_node := parse_tree_get(
                alias_expr_node,
                *alias_id_node_path,
                raise_on_ambiguous=False,
            )
        )
        is not None
    ]
    if len(alias_nodes) > 1:
        raise ValueError(
            "Found multiple alias names in expression; expected zero or one."
        )
    elif len(alias_nodes) == 0:
        return None

    alias_name = parse_tree_get(alias_nodes[0], 0).text

    indexing_base_node = parse_tree_get(
        alias_expr_node, *_alias_base_path, "name", "name_part"
    )
    if indexing_base_node is None:
        return AliasExpr(alias_name, None)
    else:
        return AliasExpr(alias_name, bitrange_from_name_part(indexing_base_node))


@called_on_node_type("term")
def expr_from_term_node(term_node: ParseTree) -> Expression | None:
    alias_expr = alias_from_term_node(term_node)
    if alias_expr is not None:
        return alias_expr

    constant_base_path = [
        "factor",
        "primary",
        "literal",
    ]
    constant_node = parse_tree_get(term_node, *constant_base_path)
    if constant_node is not None:
        enum_lit_node = parse_tree_get(constant_node, "enumeration_literal")
        if enum_lit_node is not None:
            quoted_value_str = parse_tree_get(enum_lit_node, 0).text
        else:
            quoted_value_str = parse_tree_get(constant_node, 0).text
            if quoted_value_str is None:
                quoted_value_node = parse_tree_get(
                    constant_node,
                    "numeric_literal",
                    "abstract_literal",
                    0,
                )
                quoted_value_str = quoted_value_node.text

            if quoted_value_str is None:
                raise ValueError("Could not find quoted constant value.")

        return ConstExpr(value=const_from_quoted_str(quoted_value_str))

    return None


@called_on_node_type("expression", "term")
def expr_from_node(expression_node: ParseTree) -> Expression:
    """
    Constant:
    expression -> relation -> shift_expression -> simple_expression
        -> term -> factor -> primary -> literal
        Numeric:
        -> '"00000000000000000"', 'X"0000"'
        Letters:
        -> enumeration_literal -> "'Z'"

    >>> expr_from_node(parsed('X"000000aa"', "expression"))
    ConstExpr(value=170)
    >>> expr_from_node(parsed('"00000000000000000000000000101"', "expression"))
    ConstExpr(value=5)
    >>> expr_from_node(parsed("'Z'", "expression"))
    ConstExpr(value=0)

    Concat expressions:
        simple_expression [
            term -> factor -> ...,
            adding_operator,
            term -> factor -> ...,
            adding_operator,
            term -> factor, ...,
        ]
    simple_expression
      : ( PLUS | MINUS )? term ( : adding_operator term )*
      ;
    >>> pprint(expr_from_node(parsed("A & B & C", "expression")))
    ConcatExpr(exprs=[AliasExpr(var_name='A', bitrange=None),
                      AliasExpr(var_name='B', bitrange=None),
                      AliasExpr(var_name='C', bitrange=None)])
    """
    simple_expr_node = parse_tree_get(
        expression_node,
        "relation",
        "shift_expression",
        "simple_expression",
    )

    term_node = parse_tree_get(simple_expr_node, "term")
    if term_node is not None:
        term_expr = expr_from_term_node(term_node)
        if term_expr is not None:
            return term_expr

    is_concat_expr = (
        simple_expr_node is not None
        and len(children_of_type(simple_expr_node, {"PLUS", "MINUS"})) == 0
        and len(adding_ops := children_of_type(simple_expr_node, "adding_operator")) > 0
        and all(parse_tree_get(op, "&") is not None for op in adding_ops)
    )
    if is_concat_expr:
        return ConcatExpr(
            exprs=[
                expr_from_term_node(child_term_node)
                for child_term_node in children_of_type(simple_expr_node, "term")
            ]
        )

    else:
        return SimpleExpr(expression_node)


@called_on_node_type("association_element")
def association_element_name_slice_expr(
    parse_tree: ParseTree,
) -> tuple[str, BitRange | None, ParseTree]:
    """
    >>> association_element_name_slice_expr(parsed(
    ...     "A (1 downto 0) => a + b / c",
    ...     "association_element",
    ... ))
    ('A', (0, 1), ParseTree(node_type='expression', ...))

    >>> association_element_name_slice_expr(parsed(
    ...     "A => a + b / c",
    ...     "association_element",
    ... ))
    ('A', None, ParseTree(node_type='expression', ...))
    """
    range_node = parse_tree_get(parse_tree, "formal_part", "explicit_range")
    if range_node is not None:
        range_value = explicit_range_bitrange(range_node)
    else:
        range_value = None

    return (
        parse_tree_assert_get(parse_tree, "formal_part", "identifier", 0).text,
        range_value,
        parse_tree_assert_get(
            parse_tree, "actual_part", "actual_designator", "expression"
        ),
    )


@called_on_node_type("component_instantiation_statement")
def component_port_exprs(
    parse_tree: ParseTree,
) -> dict[tuple[str, BitRange | None], ParseTree]:
    assoc_list = parse_tree_assert_get(
        parse_tree, "port_map_aspect", "association_list"
    )

    assoc_elements = children_of_type(assoc_list, "association_element")

    return {
        (var_name, var_slice): expr_from_node(expr)
        for assoc_element in assoc_elements
        for var_name, var_slice, expr in (
            association_element_name_slice_expr(assoc_element),
        )
    }


@parse_tree_query
def architecture_subinstances(
    parse_tree: ParseTree,
    children_values: list[Any],
) -> dict[ArchitectureName, dict[str, ArchitectureSubinstance]]:
    """
    >>> parse_tree = parse_tree_from_file("hdl_examples/simple/Simple.vhdl")

    >>> pprint(architecture_subinstances(parse_tree))
    {'Simple_Cell': {},
     'Simple_Row': {'SimpleCell_i0': ArchitectureSubinstance(instance_name='SimpleCell_i0',
                                                             entity_name='Simple_Cell',
                                                             port_exprs={('A', None): AliasExpr(...),
                                                                         ...}),
                    'SimpleCell_i1': ArchitectureSubinstance(...)}}

    """
    results: dict[ArchitectureName, dict[str, ArchitectureSubinstance]] = {}
    for child_vars in children_values:
        for arch_name, arch_subinstances in child_vars.items():
            results.setdefault(arch_name, {}).update(arch_subinstances)

    return results


@architecture_subinstances.register("component_instantiation_statement")
def architecture_subinstances_instantiation_statement(
    parse_tree: ParseTree,
    children_values: list[Any],
) -> dict[ArchitectureName, dict[str, ArchitectureSubinstance]]:
    instance_name = parse_tree_assert_get(
        parse_tree, "label_colon", "identifier", 0
    ).text
    entity_type_name = parse_tree_assert_get(
        parse_tree, "instantiated_unit", "name", "identifier", 0
    ).text

    return {
        "UNKNOWN_ARCH": {
            instance_name: ArchitectureSubinstance(
                instance_name=instance_name,
                entity_name=entity_type_name,
                port_exprs=component_port_exprs(parse_tree),
            ),
        },
    }


@architecture_subinstances.register("architecture_body")
def architecture_subinstances_architecture_body(
    parse_tree: ParseTree,
    children_values: list[Any],
) -> dict[ArchitectureName, dict[str, ArchitectureSubinstance]]:
    arch_name = parse_tree_assert_get(parse_tree, 3, 0).text  # Identifier

    results: dict[ArchitectureName, dict[str, ArchitectureSubinstance]] = {}
    for child_value in children_values:
        for child_arch_name, arch_subinstances in child_value.items():
            results.setdefault(child_arch_name, {}).update(arch_subinstances)

    results[arch_name] = results.get("UNKNOWN_ARCH", {})
    if "UNKNOWN_ARCH" in results:
        del results["UNKNOWN_ARCH"]

    return results


@called_on_node_type("identifier_list")
def identifier_list_strs(identifier_list_node: ParseTree) -> list[str]:
    """
    >>> identifier_list_strs(parsed("a, b", "identifier_list"))
    ['a', 'b']
    """
    return list(
        parse_tree_assert_get(identifier_node, 0).text
        for identifier_node in children_of_type(identifier_list_node, "identifier")
    )


@parse_tree_query
def architecture_local_var_bitrange(
    parse_tree: ParseTree,
    children_values: list[Any],
) -> dict[ArchitectureName, dict[str, BitRange]]:
    """
    >>> parse_tree = parse_tree_from_file("hdl_examples/simple/Simple.vhdl")
    >>> pprint(architecture_local_var_bitrange(parse_tree))
    {'Simple_Cell': {'L': (0, 0)},
     'Simple_Row': {'L': (0, 2),
                    'LPM_d0_ivl_32': (0, 0),
                    'LPM_d1_ivl_32': (0, 0),
                    'LPM_q_ivl_0': (0, 0),
                    'LPM_q_ivl_3': (0, 0),
                    'M': (0, 1),
                    'tmp_ivl_13': (0, 0),
                    ...,
                    'tmp_ivl_21': (0, 30),
                    'tmp_ivl_22': (0, 31),
                    ...,
                    'tmp_ivl_9': (0, 0)}}
    """
    results: dict[ArchitectureName, dict[str, BitRange]] = {}
    for child_vars in children_values:
        for arch_name, arch_vars in child_vars.items():
            results.setdefault(arch_name, {}).update(arch_vars)

    return results


@architecture_local_var_bitrange.register("signal_declaration")
def architecture_local_var_bitrange_signal_declaration(
    parse_tree: ParseTree,
    children_values: list[Any],
) -> dict[ArchitectureName, dict[str, BitRange]]:
    """
    signal_declaration
      : SIGNAL identifier_list COLON
        subtype_indication ( signal_kind )? ( VARASGN expression )? SEMI
      ;
    subtype_indication
      : selected_name ( selected_name )? ( constraint )? ( tolerance_aspect )?
      ;
    index_constraint
      : LPAREN discrete_range ( COMMA discrete_range )* RPAREN
      ;
    discrete_range
      : range_decl
      | subtype_indication
      ;
    """
    local_var_names = identifier_list_strs(
        parse_tree_assert_get(parse_tree, "identifier_list")
    )
    bitrange = subtype_indication_bitrange(
        parse_tree_assert_get(parse_tree, "subtype_indication"),
    )

    return {
        "UNKNOWN_ARCH": {local_var_name: bitrange for local_var_name in local_var_names}
    }


@architecture_local_var_bitrange.register("architecture_body")
def architecture_local_var_bitrange_architecture_body(
    parse_tree: ParseTree,
    children_values: list[Any],
) -> dict[ArchitectureName, dict[str, BitRange]]:
    arch_name = parse_tree_assert_get(parse_tree, 3, 0).text  # Identifier

    results: dict[ArchitectureName, dict[str, BitRange]] = {}
    for child_value in children_values:
        for child_arch_name, var_bitwidths in child_value.items():
            results.setdefault(child_arch_name, {}).update(var_bitwidths)

    results[arch_name] = results.get("UNKNOWN_ARCH", {})
    if "UNKNOWN_ARCH" in results:
        del results["UNKNOWN_ARCH"]

    return results


@called_on_node_type("name")
def name_node_str(name_node: ParseTree) -> str:
    ident_node = parse_tree_assert_get(name_node, 0)
    if ident_node.node_type == "STRING_LITERAL":
        return ident_node.text
    elif ident_node.node_type == "identifier":
        return parse_tree_assert_get(ident_node, 0).text
    else:
        raise ValueError(
            "Failed to parse identifier. First node of 'name' wasn't STRING_LITERAL "
            + f"or identifier, found {ident_node.node_type}."
        )


@parse_tree_query
def architecture_var_assignments(
    parse_tree: ParseTree,
    children_values: list[Any],
) -> dict[ArchitectureName, dict[str, dict[BitRange | None, Expression]]]:
    """
    >>> parse_tree = parse_tree_from_file("hdl_examples/simple/Simple.vhdl")

    >>> var_assignments = architecture_var_assignments(parse_tree)
    >>> sorted(var_assignments.keys())
    ['Simple_Cell', 'Simple_Row']

    >>> sorted(var_assignments["Simple_Cell"].keys())
    ['C', 'L']

    >>> assignment_expr = var_assignments["Simple_Cell"]["L"][None]
    >>> print(type(assignment_expr).__name__)
    SimpleExpr
    >>> print(str_from_parse_tree(assignment_expr.expr))
    A xor B
    """
    results: dict[ArchitectureName, dict[str, dict[BitRange | None, Expression]]] = {}
    for child_vars in children_values:
        for arch_name, var_bitrange_exprs in child_vars.items():
            for var_name, bitrange_exprs in var_bitrange_exprs.items():
                results.setdefault(arch_name, {}).setdefault(var_name, {}).update(
                    bitrange_exprs
                )

    return results


@called_on_node_type("waveform")
def waveform_expr(waveform_node: ParseTree) -> Expression:

    waveform_elements = children_of_type(waveform_node, "waveform_element")
    if len(waveform_elements) > 1:
        raise ValueError("Cannot handle comma-separated waveform expressions.")
    if len(waveform_elements) < 1:
        raise ValueError("Cannot handle UNAFFECTED waveforms.")

    expr_nodes = children_of_type(waveform_elements[0], "expression")
    if len(expr_nodes) > 1:
        raise ValueError("Cannot handle AFTER-delimited waveform expressions.")

    return expr_from_node(expr_nodes[0])


@called_on_node_type("conditional_waveforms")
def cond_waveforms_expr(cond_waveforms_node: ParseTree) -> Expression:
    """
    >>> pprint(cond_waveforms_expr(parsed("1 WHEN A ELSE 2 WHEN B", "conditional_waveforms")))
    CondExpr(conditions=[(AliasExpr(...),
                          ConstExpr(...)),
                         (AliasExpr(...),
                          ConstExpr(...))])

    >>> pprint(cond_waveforms_expr(parsed("1 WHEN A ELSE 2", "conditional_waveforms")))
    CondExpr(conditions=[(AliasExpr(...),
                          ConstExpr(value=1)),
                         (None, ConstExpr(value=2))])

    """
    if parse_tree_get(cond_waveforms_node, "condition") is None:
        waveforms_node = parse_tree_assert_get(cond_waveforms_node, "waveform")

        return waveform_expr(waveforms_node)

    cond_expr = expr_from_node(
        parse_tree_assert_get(cond_waveforms_node, "condition", "expression")
    )

    when_true_node = parse_tree_assert_get(cond_waveforms_node, "waveform")
    when_true_expr = waveform_expr(when_true_node)

    when_false_node = parse_tree_get(cond_waveforms_node, "conditional_waveforms")
    if when_false_node is None:
        else_conditions: list[
            tuple[UnconditionalExpr | None, UnconditionalExpr | None]
        ] = []
    else:
        when_false_expr = cond_waveforms_expr(when_false_node)
        if not isinstance(when_false_expr, CondExpr):
            else_conditions = [(None, when_false_expr)]
        else:
            else_conditions = when_false_expr.conditions

    return CondExpr(
        conditions=[(cond_expr, when_true_expr)] + else_conditions,
    )


@architecture_var_assignments.register("conditional_signal_assignment")
def architecture_var_assignments_cond_signal_assignment(
    parse_tree: ParseTree,
    children_values: list[Any],
) -> dict[ArchitectureName, dict[str, dict[BitRange | None, Expression]]]:
    """
    architecture_statement
    concurrent_signal_assignment_statement
      : ( label_colon )? ( POSTPONED )?
        ( conditional_signal_assignment | selected_signal_assignment )
      ;
    conditional_signal_assignment
      : target LE opts conditional_waveforms SEMI
      ;
    target
      : name
      | aggregate
      ;
    name
      : ( identifier | STRING_LITERAL ) ( name_part )*
      ;
    conditional_waveforms
      : waveform ( WHEN condition (ELSE conditional_waveforms)?)?
      ;
    waveform
      : waveform_element ( COMMA waveform_element )*
      | UNAFFECTED
      ;
    waveform_element
      : expression ( AFTER expression )?
      ;
    """
    name_node = parse_tree_assert_get(parse_tree, "target", "name")
    local_var_name = name_node_str(name_node)

    name_part_node = parse_tree_get(name_node, "name_part")
    if name_part_node is not None:
        bitrange = bitrange_from_name_part(name_part_node)
    else:
        bitrange = None

    expr = cond_waveforms_expr(
        parse_tree_assert_get(parse_tree, "conditional_waveforms")
    )

    return {
        "UNKNOWN_ARCH": {local_var_name: {bitrange: expr}},
    }


@architecture_var_assignments.register("architecture_body")
def architecture_var_assignments_architecture_body(
    parse_tree: ParseTree,
    children_values: list[Any],
) -> dict[ArchitectureName, dict[str, dict[BitRange | None, Expression]]]:
    arch_name = parse_tree_assert_get(parse_tree, 3, 0).text  # Identifier

    results: dict[ArchitectureName, dict[str, dict[BitRange | None, Expression]]] = {}
    for child_vars in children_values:
        for child_arch_name, var_bitrange_exprs in child_vars.items():
            for var_name, bitrange_exprs in var_bitrange_exprs.items():
                results.setdefault(child_arch_name, {}).setdefault(var_name, {}).update(
                    bitrange_exprs
                )

    results[arch_name] = results.get("UNKNOWN_ARCH", {})
    if "UNKNOWN_ARCH" in results:
        del results["UNKNOWN_ARCH"]

    return results


def arches_from_vhdl_path(vhdl_path: str) -> dict[str, Architecture]:
    """
    >>> arches = arches_from_vhdl_path("hdl_examples/simple/Simple.vhdl")
    >>> pprint(arches)
    {'Simple_Cell': Architecture(name='Simple_Cell',
                                 ports={'A': Port(port_type='in', pin_count=1),
                                        'B': Port(port_type='in', pin_count=1),
                                        'C': Port(port_type='out', pin_count=1)},
                                 subinstances={},
                                 var_bitranges={'L': (0, 0)},
                                 var_bitrange_assignments={'C': {(0, 0): ...},...}),
     'Simple_Row': Architecture(...)}
    """
    parse_tree = parse_tree_from_file(vhdl_path)

    arch_ports = architecture_ports(parse_tree)
    arch_subinstances = architecture_subinstances(parse_tree)
    arch_var_bitranges = architecture_local_var_bitrange(parse_tree)
    arch_assignments = architecture_var_assignments(parse_tree)

    arch_names = (
        arch_subinstances.keys()
        | arch_ports.keys()
        | arch_var_bitranges.keys()
        | arch_assignments.keys()
    )

    # Note: it'd be nicer to break out the bitrange resolving pass, so it can be
    # used in different contexts / with more port expressions available.
    return {
        arch_name: Architecture(
            name=arch_name,
            ports=(ports := arch_ports.get(arch_name, {})),
            subinstances=subinstances_with_resolved_port_bitranges(
                arch_subinstances.get(arch_name, {}),
                arch_ports,
            ),
            var_bitranges=(var_bitranges := arch_var_bitranges.get(arch_name, {})),
            var_bitrange_assignments=assignments_with_resolved_bitranges(
                arch_assignments.get(arch_name, {}),
                var_bitranges,
                ports=ports,
            ),
        )
        for arch_name in arch_names
    }
