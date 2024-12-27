#!/usr/bin/env python
from sys import argv
from time import sleep

import matplotlib.pyplot as plt

from redhdl.voxel.schematic import display_schematic, load_schem


def main(schem_path, desc_file_path: str | None):
    plt.ion()

    while True:
        try:
            schem = load_schem(schem_path)

            if desc_file_path is not None:
                with open(desc_file_path) as desc_file:
                    desc = desc_file.read()
            else:
                desc = ""

            display_schematic(schem, schem_path + "\n" + desc)
            plt.pause(0.1)

        except KeyboardInterrupt:
            raise

        except FileNotFoundError:
            sleep(0.2)


if __name__ == "__main__":
    if len(argv) == 2:
        main(argv[1], None)
    if len(argv) != 3:
        raise ValueError("Usage: display_schem.py <schem_file> <desc_text_file>")
    main(argv[1], argv[2])
