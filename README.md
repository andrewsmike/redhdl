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


Architecture
------------

- redhdl.voxel: 3d data primitives and minecraft schematics.
- redhdl.search: Local and graph search algorithms.
- redhdl.vhdl: VHDL parsing and analysis.
- redhdl.netlist: Abstract circuit representation. Includes tools to generate netlists from schematics and VHDL files.
- redhdl.misc: Generic utilities and data types (such as custom caching, slicing, bitranges, etc).
- redhdl.bussing: Generate 3d busses for redstone circuits.
- redhdl.assembly: Putting it all together: synthesizing circuits using the previous modules' tooling.


### Detailed architecture

Misc. utilities:
- misc/ascii_dag.py: ASCII-art directed acyclic graph pretty printer.
- misc/caching.py: Custom caching decorators.
- misc/bitrange.py: Bit-range manipulation module.
- misc/slice.py: Provides Slice(), which is slice() but hashable.

Spatial stuff:
- voxel/positional_data.py: Fancy Dict[Pos, T] with helper tools.
- voxel/region.py: Positions in 3d space, regions (point/rectangular/compound), position sequences.
- voxel/schematic.py: Basic Block and Schematic representation, loading / saving.

vHDL stuff:
- vhdl/parse_tree.py: ANTLR AST harness and simplified AST tools, representation.
- vhdl/models.py: Simplified netlist-adjacent model of a VHDL file plus manipulations.
- vhdl/analysis.py: Mapping from AST to simpler models.py models.

Netlist stuff:
- netlist/netlist.py: Somewhat abstract Netlist, Interface, Port, Pin, PinSequence definitions.
- netlist/instances.py: Concrete schematic-based Instance (and RepeaterPortInterface).
- netlist/instance_template.py: Parse a carefully-formatted circuit schematic into an Instance.
    Searches for I/O annotating sign blocks and parses out descriptions for Ports / Pins / etc.
- netlist/netlist_template.py: Create Netlists from simple templates and a schematic library!
- netlist/vhdl_netlist.py: Create Netlists from simple VHDL files!

Search stuff:
- search/local_search.py: Local search algorithm, Problem interfaces and sim. annealing implementation.
- search/path_search.py: Path search algorithm, Problem interface and A* implementation.

Bussing:
- bussing/errors.py: Bussing error types.
- bussing/naive_bussing.py: Heuristic simple pathfinding problem methods.
    - Only routes a single block path, rather than a real redstone wire.
    - Has a variety of useful cost heuristics and Path definitions.
    - Has a collision-relaxed solver for searching multiple paths simultaneously.
- bussing/redstone_bussing.py: Experimental fully-featured redstone wire path search problem.

Assembly:
- assembly/placement.py: Bussing-naive component placement logic and solvers.
    - Placement definition (A Dict[InstanceId, Tuple[Position, Direction]])
    - (Placement U Netlist) methods (including Schematic generation)
    - Pin position localization tools
    - Placement search methods (random and sim. annealing)
    - Placement quality heuristics
- assembly/assembly.py: Heuristic joint placement and (naive-wire-only) bus search.


WHAT'S MISSING:
- schematic_instance: Support for diagonal circuits.
- region.py: Supporting polyhedral regions for diagonal circuits would allow us to switch
    from PointRegions to a more efficient representation.

- redstone_bussing.py:
    - Current representation is insufficiently efficient
        - Optimizing this will be challenging - busses have more state than simple paths.
        - Busses are also _rather_ complicated in their constraints.
        - Might be able to use naive path-finding as a first-pass.
    - No multi-wire / relaxed / herd search.

- assembly.py:
    - Must be improved and adapted to handle real redstone_bussing.
    - Must be adapted to handle hierarchical Netlists (with proper deduplication).
        - Possibly consider repartitioning using minimum-cut hierarchical clustering or
            fancy force-based model.

- Schematic library: Must be built out!
- vhdl: Must get to the point where a hierarchical Netlist can be generated!
