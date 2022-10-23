"""
Simplified parse-tree to replace antlr's overly-robust ParseTree implementation.
"""
from dataclasses import dataclass, field
from functools import wraps
from pprint import pformat, pprint
from typing import Any

from antlr4.tree.Tree import ParseTree as ANTLRParseTree
from antlr4.tree.Trees import Trees

from redhdl.vhdl.antlr_parser import vhdl_tree_from_file, vhdl_tree_from_str
from redhdl.vhdl.vhdlParser import vhdlParser


@dataclass
class ParseTree:
    """
    Simple python representation of the verible antlr parse tree.
    Text only provived for terminal nodes.
    Children are slots; not all slots are filled (Nones.)
    Start / end may or may not be available for nonterminals.
    """

    node_type: str
    children: list["ParseTree"] = field(default_factory=list)
    text: str | None = None

    def terminal(self):
        return len(self.children) == 0


def parse_tree_from_antlr(antlr_parse_tree: ANTLRParseTree) -> ParseTree:
    # In ANTLR land, node_text is the node_type for nonterminals, and the actual text symbol
    # for terminals.
    antlr_node_text = Trees.getNodeText(
        antlr_parse_tree, ruleNames=vhdlParser.ruleNames
    )

    if antlr_parse_tree.getChildCount() == 0:
        node_type = antlr_node_text.upper()
        text = antlr_node_text
    else:
        node_type = antlr_node_text
        text = None

    return ParseTree(
        node_type=node_type,
        children=[
            parse_tree_from_antlr(child_node)
            for child_node in getattr(antlr_parse_tree, "children", None) or []
            if child_node is not None
        ],
        text=text,
    )


def parse_tree_from_file(path: str) -> ParseTree:
    """
    >>> from pprint import pprint

    >>> parse_tree = parse_tree_from_file("hdl_examples/simple/Simple.vhdl")
    >>> pprint(parse_tree, compact=True)
    ParseTree(node_type='design_file',
              children=[ParseTree(node_type='design_unit',
                                  children=[ParseTree(node_type='context_clause',
                        ...
                        ParseTree(node_type='<EOF>', children=[], text='<EOF>')],
              text=None)

    >>> pprint_tree(parse_tree)
    [[[['library', 'ieee', ';'],
       ['use', ['ieee', '.', 'std_logic_1164', '.', 'all'], ';'],
       ['use', ['ieee', '.', 'numeric_std', '.', 'all'], ';']],
      ['entity',
     ...
       'end',
       'architecture',
       ';']],
     '<EOF>']
    """
    antlr_parse_tree = vhdl_tree_from_file(path)
    return parse_tree_from_antlr(antlr_parse_tree)


def parse_tree_from_str(source: str) -> ParseTree:
    antlr_parse_tree = vhdl_tree_from_str(source)
    return parse_tree_from_antlr(antlr_parse_tree)


# For pretty printing ParseTrees.
SimplifiedTree = str | list[Any]  # list["SimplifiedTree"]


def simplified_tree(parse_tree: ParseTree) -> SimplifiedTree:
    if parse_tree.terminal():
        assert parse_tree.text is not None  # For MyPy.
        return parse_tree.text

    parts = [
        simplified_tree(child) for child in parse_tree.children if child is not None
    ]
    if len(parts) == 1:
        return parts[0]
    else:
        return parts


def pformatted_tree(parse_tree: ParseTree) -> str:
    return pformat(simplified_tree(parse_tree))


def pprint_tree(parse_tree: ParseTree) -> None:
    """
    Pretty print a parse tree.

    >>> pprint_tree(parse_tree_from_file("hdl_examples/adder_chain.vhdl"))
    [[[['library', 'ieee', ';'],
       ['use', ['ieee', '.', 'std_logic_1164', '.', 'all'], ';'],
       ['use', ['ieee', '.', 'numeric_std', '.', 'all'], ';']],
      ['entity',
       'adder_chain',
       'is',
       ['port',
        '(',
     ...
        ['carry_out', '<=', 'opts', ['result', ['(', '8', ')']], ';'],
        ['tmp_ivl_11', '<=', 'opts', "'0'", ';'],
        ['tmp_ivl_17', '<=', 'opts', "'0'", ';'],
        ['tmp_ivl_7', '<=', 'opts', "'0'", ';']],
       'end',
       'architecture',
       ';']],
     '<EOF>']
    """
    pprint(simplified_tree(parse_tree))


def parse_tree_query(func):
    """
    Similar to @singledispatch, but where the first argument is a ParseTree
    and we're dispatching based on node_type.
    This is a non-lazy visitor; you will be provided with a list the result values
    of your children, along with your arguments.
    ie:
    >>> @parse_tree_query
    ... def my_query(parse_tree: ParseTree, children_values: list[Any], my_arg_1, my_arg_2: bool = False) -> Any:
    ...     for child_value in children_values:
    ...         if child_value is not None:
    ...            return child_value

    >>> @my_query.register("ruleOfInterest")
    ... def my_query_rule_of_interest(parse_tree: ParseTree, children_values: list[Any], my_arg_1, my_arg_2: bool = False) -> Any:
    ...     return parse_tree.text
    """

    @wraps(func)
    def wrapper(parse_tree: ParseTree | None, *args, **kwargs) -> Any | None:
        if parse_tree is None:
            return None

        children_query_results = [
            wrapper(child, *args, **kwargs) for child in parse_tree.children
        ]
        node_type_func = func.node_type_visitor_func.get(parse_tree.node_type, func)

        return node_type_func(
            parse_tree,
            children_query_results,
            *args,
            **kwargs,
        )

    def wrapper_register(node_type: str):
        def wrapped_register(visitor_func):
            func.node_type_visitor_func[node_type] = visitor_func
            return visitor_func

        return wrapped_register

    wrapper.register = wrapper_register
    func.node_type_visitor_func = {}

    return wrapper


def next_child(
    children: list[ParseTree],
    step: int | str,
) -> ParseTree | None:

    if isinstance(step, int):
        assert step < len(children)
        return children[step]

    elif isinstance(step, str):
        matching_children = [
            child for child in children if child is not None if child.node_type == step
        ]

        if len(matching_children) == 0:
            return None
        elif len(matching_children) == 1:
            return matching_children[0]
        else:
            raise ValueError(
                f"Multiple children have node type {step}, expected only one."
            )
    else:
        raise ValueError(
            f"Path steps are either indices (ints) or node_types (str). Got {step}."
        )


ParseTreeNodeTypePath = list[int | str]


def parse_tree_get(
    parse_tree: ParseTree | None, path: ParseTreeNodeTypePath
) -> ParseTree | None:
    if parse_tree is None:
        return None

    if path == []:
        return parse_tree

    if len(parse_tree.children) == 0:
        return None

    next_step, *remaining_path = path

    return parse_tree_get(
        next_child(parse_tree.children, next_step),
        remaining_path,
    )


def parse_tree_assert_get(
    parse_tree: ParseTree, path: ParseTreeNodeTypePath
) -> ParseTree:
    node = parse_tree_get(parse_tree, path)
    assert node is not None, f"Expected node at path {path}, but found nothing."
    return node
