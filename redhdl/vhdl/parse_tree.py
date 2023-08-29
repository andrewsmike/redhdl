"""
Simplified parse-tree to replace antlr's overly-robust ParseTree implementation.
"""
from dataclasses import dataclass, field
from functools import wraps
from pprint import pformat, pprint
from typing import Any, Callable

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


def parse_tree_from_str(source: str, node_type: str = "design_file") -> ParseTree:
    antlr_parse_tree = vhdl_tree_from_str(source, node_type=node_type)
    return parse_tree_from_antlr(antlr_parse_tree)


def parsed(*args, **kwargs) -> ParseTree:
    return parse_tree_from_str(*args, **kwargs)


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


def str_from_parse_tree(parse_tree: ParseTree) -> str:
    if parse_tree.text is not None:
        return parse_tree.text
    else:
        return " ".join(str_from_parse_tree(child) for child in parse_tree.children)


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
            visitor_func.register = wrapper_register

            return visitor_func

        return wrapped_register

    wrapper.register = wrapper_register
    func.node_type_visitor_func = {}

    return wrapper


def called_on_node_type(*node_types: str) -> Callable[[Callable], Callable]:
    """
    >>> @called_on_node_type("my_node_type")
    ... def my_node_name(blah: ParseTree, *args, **kwargs):
    ...     return "_".join(child.text for child in blah.children)

    >>> my_node = ParseTree(
    ...     "my_node_type", [ParseTree("HELLO", [], "hello"), ParseTree("WORLD", [], "world")]
    ... )
    >>> print(my_node_name(my_node))
    hello_world

    >>> print(my_node_name(ParseTree("wrong_node_type", [], "blah")))
    Traceback (most recent call last):
      ...
    ValueError: Attempted to invoke my_node_name with wrong_node_type, expected one of {'my_node_type'}.
    """

    def decorator(func) -> Callable:
        @wraps(func)
        def wrapper(node: ParseTree, *args, **kwargs):
            if node.node_type not in node_types:
                raise ValueError(
                    f"Attempted to invoke {func.__name__} with {node.node_type}, "
                    + f"expected one of {set(node_types)}."
                )
            return func(node, *args, **kwargs)

        return wrapper

    return decorator


def next_child(
    children: list[ParseTree],
    step: int | str,
    raise_on_ambiguous: bool = True,
) -> ParseTree | None:

    if isinstance(step, int):
        if len(children) <= step:
            return None
        else:
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
            if raise_on_ambiguous:
                raise ValueError(
                    f"Multiple children have node type {step}, expected only one."
                )
            else:
                return None
    else:
        raise ValueError(
            f"Path steps are either indices (ints) or node_types (str). Got {step}."
        )


def children_of_type(
    node: ParseTree,
    children_types: str | set[str],
) -> list[ParseTree]:
    if isinstance(children_types, str):
        acceptable_node_types = {children_types}
    elif isinstance(children_types, set):
        acceptable_node_types = children_types
    else:
        raise ValueError(
            f"Expected either node_type or set[node_type], got {children_types}"
        )

    return [
        child for child in node.children if child.node_type in acceptable_node_types
    ]


def parse_tree_get(
    parse_tree: ParseTree | None,
    *path: int | str,
    raise_on_ambiguous: bool = False,
) -> ParseTree | None:
    if parse_tree is None:
        return None

    if len(path) == 0:
        return parse_tree

    if len(parse_tree.children) == 0:
        return None

    next_step, *remaining_path = path

    return parse_tree_get(
        next_child(
            parse_tree.children, next_step, raise_on_ambiguous=raise_on_ambiguous
        ),
        *remaining_path,
    )


def parse_tree_assert_get(parse_tree: ParseTree, *path: int | str) -> ParseTree:
    node = parse_tree_get(parse_tree, *path)
    assert node is not None, f"Expected node at path {path}, but found nothing."
    return node
