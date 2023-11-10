#!/usr/bin/env python

from argparse import ArgumentParser
from string import ascii_uppercase
from subprocess import run

from redhdl.netlist.vhdl_netlist import netlist_template_from_vhdl_path
from redhdl.voxel.schematic import display_schematic, save_schem
from redhdl.assembly.assembly import assembled_circuit_schem

def _camel_case(value: str) -> str:
    return "_".join(
        ((part[0].upper() + part[1:]) if part else "")
        for part in value.split("_")
    )

def assemble_module(module_name: str):

    vhdl_path = f"build/{module_name}.vhdl"
    sv_to_vhdl_command_parts = [
        "iverilog",
        "-g2012",
        "-tvhdl",
        f"-o{vhdl_path}",
        "build/stubs.sv",
        f"modules/{_camel_case(module_name)}.sv",
    ]
    result = run(sv_to_vhdl_command_parts)
    if result.returncode != 0:
        raise RuntimeError(
            "Failed to translate generic SystemsVerilog to simple VHDL;\n"
            + f"command `{' '.join(sv_to_vhdl_command_parts)}` returned "
            + f"nonzero exit code {result.returncode}."
        )

    instance_configs, port_slice_assignments = (
        netlist_template_from_vhdl_path(vhdl_path, module_name)
    )

    print(f"Assembling {module_name}")
    schem = assembled_circuit_schem(
        instance_configs,
        port_slice_assignments,
    )

    schem_path = f"{module_name}.schem"
    print(f"Saving to {schem_path}.")
    save_schem(schem, schem_path)


def arg_parser() -> ArgumentParser:
    parser = ArgumentParser(
        description="Synthesize redstone circuitry from SystemsVerilog modules.",
    )
    parser.add_argument(
        "module_name",
        help="the root SV module to compile"
    )
    parser.add_argument(
        "--list-modules",
        help="list the available modules",
    )
    return parser

def main():
    args = arg_parser().parse_args()

    assemble_module(args.module_name)



if __name__ == "__main__":
    main()
