#!/usr/bin/env python
import signal
from sys import argv
from time import sleep

import matplotlib.pyplot as plt

from redhdl.schematic import display_schematic, load_schem

def main(schem_path, desc_file_path: str):
    # Force PLT to respect interrupts.
    signal.signal(signal.SIGINT, signal.SIG_DFL)

    plt.ion()
    plt.title(schem_path)

    while True:
        try:
            schem = load_schem(schem_path)
            with open(desc_file_path, "r") as desc_file:
                desc = desc_file.read()
            display_schematic(schem, desc)
            plt.pause(0.1)

        except KeyboardInterrupt:
            raise

        except FileNotFoundError:
            sleep(0.2)


if __name__ == "__main__":
    if len(argv) != 3:
        raise ValueError("Usage: display_schem.py <schem_file> <desc_text_file>")
    main(argv[1], argv[2])
