"""
Tools for parsing vhdl using an ANTLR-generated parser.
"""
from os.path import dirname, join
from pprint import pformat
from sys import argv
from typing import Any, Callable, Iterable, Optional

from antlr4.CommonTokenStream import CommonTokenStream
from antlr4.FileStream import FileStream
from antlr4.InputStream import InputStream
from antlr4.error.ErrorListener import ErrorListener
from antlr4.tree.Tree import ParseTree
from antlr4.tree.Trees import Trees
from graphviz import Digraph

from redhdl.vhdl.vhdlLexer import vhdlLexer
from redhdl.vhdl.vhdlListener import vhdlListener  # noqa
from redhdl.vhdl.vhdlParser import vhdlParser


class AbortSyntaxErrorListener(ErrorListener):
    def syntaxError(self, recognizer, offendingSymbol, line, column, msg, e):
        raise SyntaxError(f"At {line}:{column}: {msg}")


def children_contexts(
    ctx_func: Callable[[int], Optional[ParseTree]]
) -> list[ParseTree]:
    """
    The list of elements provided by a zero-indexed (index: int -> Optional[ParseTree])
    function.
    This is a bizarre way of providing this data, and it's usually useful to convert
    it into a proper list.

    >>> # Note: This should return contexts, but making them takes effort.
    >>> def get_word(index: int) -> Optional[str]:
    ...     content = ["hello", "world"]
    ...     if 0 <= index < len(content):
    ...         return content[index]
    ...     else:
    ...         return None
    >>> children_contexts(get_word)
    ['hello', 'world']
    """
    children: list[ParseTree] = []
    while (next_child := ctx_func(len(children))) is not None:
        children.append(next_child)

    return children


def vhdl_parser_from_str(expr: str) -> vhdlParser:
    lexer = vhdlLexer(InputStream(expr))
    token_stream = CommonTokenStream(lexer)
    parser = vhdlParser(token_stream)

    parser.addErrorListener(AbortSyntaxErrorListener())

    return parser


def vhdl_tree_from_stream(
    input_stream: InputStream,
    node_type: str = "design_file",
) -> ParseTree:
    lexer = vhdlLexer(input_stream)
    token_stream = CommonTokenStream(lexer)
    parser = vhdlParser(token_stream)

    parser.addErrorListener(AbortSyntaxErrorListener())

    if not hasattr(parser, node_type):
        raise ValueError(f"Unknown root node_type {node_type}; cannot parse vhdl.")
    parse_node_type_func = getattr(parser, node_type)

    return parse_node_type_func()


def vhdl_tree_from_file(path: str) -> ParseTree:
    return vhdl_tree_from_stream(FileStream(path))


def vhdl_tree_from_str(
    source: str,
    node_type: str = "design_file",
) -> ParseTree:
    """
    >>> print(bracket_printed_vhdl_parse_tree(
    ...     vhdl_tree_from_str("unsigned(1 downto 0)", "subtype_indication")
    ... ))
    ['unsigned', ['(', ['1', 'downto', '0'], ')']]
    """
    return vhdl_tree_from_stream(InputStream(source), node_type=node_type)


# BracketParseTree = list["BracketParseTree"] | str
BracketParseTree = list[Any] | str


def bracketed_vhdl_tree(tree: ParseTree) -> BracketParseTree:
    node_text = Trees.getNodeText(tree, ruleNames=vhdlParser.ruleNames)

    if tree.getChildCount() == 0:
        return node_text
    else:
        return [node_text] + [
            bracketed_vhdl_tree(tree.getChild(child_index))
            for child_index in range(tree.getChildCount())
        ]


def reduced_bracketed_tree(bracketed_vhdl_tree: BracketParseTree) -> BracketParseTree:
    parts = []
    for child in bracketed_vhdl_tree[1:]:
        if isinstance(child, list):
            reduced_child = reduced_bracketed_tree(child)
        else:
            reduced_child = child

        if isinstance(reduced_child, list) and len(reduced_child) == 1:
            (reduced_child,) = reduced_child

        if reduced_child:
            parts.append(reduced_child)

    return parts


def bracket_printed_vhdl_parse_tree(tree: ParseTree, reduce_tree: bool = True) -> str:
    """
    Pretty print vhdl parse trees for debugging.
    >>> example_vhdl_source = \"\"\"
    ... entity example_circuit is
    ...   port (
    ...     En : in std_logic
    ...   );
    ... end entity;
    ... \"\"\"

    >>> print(bracket_printed_vhdl_parse_tree(vhdl_tree_from_str(example_vhdl_source)))
    [['context_clause',
      ['entity',
       'example_circuit',
       'is',
       ['port', '(', ['En', ':', 'in', 'std_logic'], ')', ';'],
       'entity_declarative_part',
       'end',
       'entity',
       ';']],
     '<EOF>']

    >>> print(bracket_printed_vhdl_parse_tree(vhdl_tree_from_str(example_vhdl_source), reduce_tree=False))
    ['design_file',
     ['design_unit',
      'context_clause',
      ['library_unit',
       ['primary_unit',
        ['entity_declaration',
         'entity',
         ['identifier', 'example_circuit'],
         'is',
         ['entity_header',
          ['port_clause',
           'port',
           '(',
           ['port_list',
            ['interface_port_list',
             ['interface_port_declaration',
              ['identifier_list', ['identifier', 'En']],
              ':',
              ['signal_mode', 'in'],
              ['subtype_indication',
               ['selected_name', ['identifier', 'std_logic']]]]]],
           ')',
           ';']],
         'entity_declarative_part',
         'end',
         'entity',
         ';']]]],
     '<EOF>']
    """
    bracketed_tree = bracketed_vhdl_tree(tree)
    if reduce_tree:
        bracketed_tree = reduced_bracketed_tree(bracketed_tree)

    return pformat(bracketed_tree)


BracketParseTreePath = list[int]


def bracketed_tree_locations(
    tree: BracketParseTree,
    path_prefix: BracketParseTreePath | None = None,
) -> Iterable[tuple[BracketParseTreePath, BracketParseTree]]:
    if path_prefix is None:
        path_prefix = []

    assert path_prefix is not None  # For MyPy.

    yield (path_prefix, tree)
    match tree:
        case [str(node_type), *children]:
            for child_index, child in enumerate(children):
                yield from bracketed_tree_locations(child, path_prefix + [child_index])
        case str(node_text):
            pass


def display_parse_tree(tree: ParseTree, comment: str = "ANTLR Parse Tree"):
    tree = bracketed_vhdl_tree(tree)

    graph = Digraph(comment="ANTLR Parse Tree", format="png")

    node_paths = set()
    for node_path, node_value in bracketed_tree_locations(tree):
        node_paths.add(tuple(node_path))

        parent_node_name = "".join(f"[{index}]" for index in node_path[:-1])
        node_name = "".join(f"[{index}]" for index in node_path)

        if isinstance(node_value, list):
            node_str = node_value[0]
            color_str = "black"
        else:
            node_str = node_value
            color_str = "blue"

        assert isinstance(node_str, str), node_str

        graph.node(node_name, node_str, color=color_str)
        graph.edge(parent_node_name, node_name)

    graph.render("/tmp/parser_tree_vis", view=True)


def display_example_program():
    vhdl_source_path = join(
        dirname(dirname(dirname(__file__))),  # redhdl/[parser/[vhdl]]
        "hdl_examples",
        f"{argv[1]}.vhdl",
    )

    try:
        vhdl_tree = vhdl_tree_from_file(vhdl_source_path)
    except SyntaxError as e:
        print("Failed to parse, dropping into debugger mode.")
        from pdb import post_mortem

        post_mortem(e.__traceback__)
        raise e

    print("Verbose parse tree:")
    print(bracket_printed_vhdl_parse_tree(vhdl_tree, reduce_tree=False))

    print("Pretty VHDL tree string:")
    print(bracket_printed_vhdl_parse_tree(vhdl_tree))

    print("Rendering graph...")
    display_parse_tree(vhdl_tree)


if __name__ == "__main__":
    display_example_program()
