RedHDL: Verilog -> Redstone Circuits.
=====================================
[![Imports: isort](https://img.shields.io/badge/%20imports-isort-%231674b1?style=flat&labelColor=ef8336)](https://pycqa.github.io/isort/)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![Checked with mypy](http://www.mypy-lang.org/static/mypy_badge.svg)](http://mypy-lang.org/)

Redstone circuit synthesizer for the rapid prototyping of large-scale redstone circuits.
Nearing MVP of "can place and bus moderately sized circuits from an existing library in a not-braindead way".


Setting up
----------
```sh
$ pip install -e .
$ pip install pre-commit; pre-commit install
```

Running tests:
```sh
$ pytest -k my_test_name
```

Concept Overview
----------------

There are multiple conceptual stacks this codebase must build and unify:
- Position, region, and other basic 3d data utilities.
    - This is extended to include minecraft-specific Block and Schematic concepts.
- The abstract concepts of Netlists, Instances, Networks, Ports, and Pins, and their manipulations.
- Path search and local search methods.
- Region placement search and methods
    - This is extended to include complex bussing search methods.
- vHDL parsing and translation into a Netlist.


Quick tour, building upwards:
Generic utilities:
- slice.py: Provides Slice(), which is slice() but hashable.
- ascii_dag.py: ASCII-art directed acyclic graph pretty printer.

Spatial stuff:
- region.py: Positions in 3d space, regions (point/rectangular/compound), position sequences.
- positional_data.py: Fancy Dict[Pos, T] with helper tools.
- schematic.py: Basic Block and Schematic representation, loading / saving.

Netlist stuff:
- netlist.py: Somewhat abstract Netlist, Interface, Port, Pin, PinSequence definitions.
- instances.py: Concrete schematic-based Instance (and RepeaterPortInterface).
- instance_template.py: Parse a carefully-formatted circuit schematic into an Instance.
    Searches for I/O annotating sign blocks and parses out descriptions for Ports / Pins / etc.
- netlist_template.py: Make Netlists using simple templates and a schematic library!

Search stuff:
- path_search.py: Path search algorithm, Problem interface and A* implementation.
- local_search.py: Local search algorithm, Problem interfaces and sim. annealing implementation.

Bussing:
- bussing.py: Heuristic simple pathfinding problem methods.
    - Only routes a single block path, rather than a real redstone wire.
    - Has a variety of useful cost heuristics and Path definitions.
    - Has a collision-relaxed solver for searching multiple paths simultaneously.
- redstone_bussing.py: Experimental fully-featured redstone wire path search problem.

Putting it all together:
- placement.py: Bussing-naive component placement logic and solvers.
    - Placement definition (A Dict[InstanceId, Tuple[Position, Direction]])
    - (Placement U Netlist) methods (including Schematic generation)
    - Pin position localization tools
    - Placement search methods (random and sim. annealing)
    - Placement quality heuristics
- assembly.py: Heuristic joint placement and (naive-wire-only) bus search.

vHDL stuff:
- vhdl/*: Basic AST available, synthesized hierarchical Netlist not implemented yet.


WHAT'S MISSING:
- region.py: Diagonal polyhedra are needed to support diag circuits.
- instance_template: Support for diagonal circuits.
- redstone_bussing.py:
    - Current representation is insufficiently efficient
        - Optimizing this will be challenging - busses have more state than simple paths.
        - Busses are also _rather_ complicated in their constraints.
        - Might be able to use naive path-finding as a first-pass.
    - No multi-wire / relaxed / herd search.
- assembly.py:
    - Must be improved and adapted to handle real redstone_bussing.
    - Must be adapted to handle hierarchical Netlists (with proper deduplication).

- Schematic library: Must be built out!
- vhdl: Must get to the point where a hierarchical Netlist can be generated!
