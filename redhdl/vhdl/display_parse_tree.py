from redhdl.vhdl.antlr_parser import display_parse_tree, vhdl_tree_from_file


def main():
    hdl_tree = vhdl_tree_from_file("hdl_examples/adder_chain.vhdl")
    display_parse_tree(hdl_tree)


if __name__ == "__main__":
    main()
