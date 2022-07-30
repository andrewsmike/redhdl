from glob import glob
from os import chdir
from os.path import dirname
from subprocess import run

from setuptools import Command, setup


class RegenerateParserCommand(Command):
    description = "regenerate the antlr4-based VHDL parser"
    user_options = []  # type: ignore

    def initialize_options(self):
        pass

    def finalize_options(self):
        pass

    def run(self):
        chdir(dirname(__file__))
        chdir("redhdl/parser")
        antlr_command_parts = [
            "antlr4",
            "-Dlanguage=Python3",
            "-lib",
            ".",
            "-o",
            "autogen",
            "-visitor",
            "-listener",
            "vhdl.g4",
        ]

        print("Running `" + " ".join(antlr_command_parts) + "`.")
        run(antlr_command_parts)

        chdir("../parser")
        run(["cp"] + glob("autogen/*.py") + ["."])


# See setup.cfg for metadata, options, and setup tools.
setup(
    cmdclass={"gen_parser": RegenerateParserCommand},
)
