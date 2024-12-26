from pprint import pprint

from pytest import fixture


@fixture(autouse=True)
def add_doctest_pprint(doctest_namespace):
    doctest_namespace["pprint"] = pprint
