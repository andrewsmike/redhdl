from pprint import pformat, pprint

import pytest

from redhdl.vhdl.parse_tree import (
    parse_tree_from_file,
    parse_tree_from_str,
    parsed,
    str_from_parse_tree,
)


@pytest.fixture(autouse=True)
def add_doctest_imports(doctest_namespace):
    doctest_namespace["parse_tree_from_file"] = parse_tree_from_file
    doctest_namespace["parse_tree_from_str"] = parse_tree_from_str
    doctest_namespace["parsed"] = parsed
    doctest_namespace["pprint"] = pprint
    doctest_namespace["pformat"] = pformat
    doctest_namespace["str_from_parse_tree"] = str_from_parse_tree
