"""
Simplified parse-tree to replace antlr's overly-robust ParseTree implementation.
"""
from dataclasses import dataclass, field
from typing import Optional

@dataclass
class ParseTree:
    """
    Simple python representation of the verible parse tree.
    Text only provived for terminal nodes.
    Children are slots; not all slots are filled (Nones.)
    Start / end may or may not be available for nonterminals.
    """

    node_type: str
    children: list[Optional["ParseTree"]] = field(default_factory=list)
    start: int | None = None
    end: int | None = None

    source_name: str | None = None
    text: str | None = None

    def terminal(self):
        return len(self.children) == 0
