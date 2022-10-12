"""
Simplified parse-tree to replace antlr's overly-robust ParseTree implementation.
"""
@dataclass
class ParseTree:
    """
    Simple python representation of the verible parse tree.
    Text only provived for terminal nodes.
    Children are slots; not all slots are filled (Nones.)
    Start / end may or may not be available for nonterminals.
    """

    node_type: str = field(metadata=config(field_name="tag"))
    children: list[Optional["ParseTree"]] = field(default_factory=list)
    start: Optional[int] = None
    end: Optional[int] = None

    source_name: Optional[str] = None
    text: Optional[str] = None

    def terminal(self):
        return len(self.children) == 0
