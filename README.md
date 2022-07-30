====
IO types:

- Block (pulled by comparator or repeater)
- Repeater (pulled by block -> comparator/repeater/torch, wire, repeater, comparator)
- Torch (pulled by wire, comparator, repeater)

MVP:
- Repeater input, repeater output.
- No stacking. Stackable components (elem-wise stuff) comes later.
- No subsetting.
- No diagonal region support (yet). Keep it simple for the second.
- 

=====
Okay cool so
- We have a Netlist representation
- We have a proof of concept AABB Region concept [UNTESTED]
- We have a Placement concept [UNTESTED]

We need...
- A real schematic concept.
- A real Bussing concept
- A real Bussing+Placement concept

Algorithmic success:
- 

What are busses?
I need to connect schematics with networks.

"If I place <these schematics inc busses>, in this arrangement, does it match this subnetlist?"
Reducing further:
so think in undirected inferences:
- Let's say we have a composite rectangular prism region for busses and it works trivially
- Busses export "input[pos/type] -> outputs[pos/type]"
- Instance schematics export input[pos/type] and outputs[pos/type], identified as ports

So we're successful when:
- We have a superset netlist
- This netlist has a placement with no overlaps
- All added instances are bus-kind
- Every PortBlock input, once traced backwards through bus instances, is sourced from the correct output PortBlock.
- All bus instances are associated with at least one PortBlock

Need to resolve Ports v PinRuns.

Okay, so let's not overload the netlist concept.
Let's make a new concept:
- Regions + schematics
- PinIdRuns -> PinBlockRuns
- Busses

PinBlockRuns X PinBlockRuns (do these connect correctly?)
Components / BlockInstances / SchematicInstances

- Rename blocks -> schematic
- Create CircuitSchematic / InstanceSchematic / ComponentSchematic concept
    - Schematic
    - 3d port information
    - Occupied region

- Create Busses (a CircuitSchematic) with additional information: Port-slice-to-port-slice
    equivalence / equations.

    hmmm
    the final connectivity step is still missing.

IDEAS
====

Make pin groups whenever possible
Networks are the hard requirement. Busses are ways to achieve this. Network lines "piggy back" off of bus components, which fit together well.
This isn't enough to make bussing efficient - space is far too large. We'll want some simplifications.
- When there's a string of equispaced pins from the same port going to the same port, use stacked pattern.
- When there are multiple wires going through the same region, try to use the same stacked pattern.
... Hmmm...
The spaces between blocks are axis aligned.
Busses going roughly in the same direction could run in parallel.
The best busses use the fewest blocks and are delay-optimal for all points. (Is fewest blocks a strictly stronger condition?)
Divert when there's a block in the way.
Heuristics to make branching bus search remain fewest-block-optimal in the face of restricted graphs
... wait, it's still a 2d graph. I'm just A*'ing. How represent bias towards minimal in branching model?

====
Generate hierarchically from bottom up. Only place a few components simultaneously, wire the ins and outs to the nearest points at the edge of the AABB region defined by the sub component

Develop a fast greedy wiring method. Flat-bussing never needs diagonal motion, vertical busing does need diagonal motion and may need interesting heuristic.

This mostly solves wire generation order stuff. May still be worth randomizing order in each subcomponent routing run.

Once inefficient map is generated, begin small mutations and checking.

Maybe don't deal with signal strength just yet?

Find ways to cache pathfinding results for subgraphs - local area constraints based on efficiency

Huh. Caching arbitrary subsets of the circuit with really efficient routing and placement across runs could be helpful for cached building




## ABCD

Bus: set[Region] -> Pos -> Pos --slow/cached--> BusSpec, BusSpec -> list[Blocks]
- Bus: A wire (~3x2) moving through 3d space.
    - Defined by a continuous path (diagonals not included in x/y directions)
    - Generates appropriate regionsfor collisions
    - May be generated with any number of heuristics. When multiple outputs, resembles [Steiner Tree Problem](https://en.wikipedia.org/wiki/Steiner_tree_problem).


Netlist:
- Abstract (no block details, no placement/orientation, no wires.)
- Basic logical description of blocks; no busses.


Okay, so:
- Template: (config -> Instance)


Instance
    (AKA Block)
    We'll use Block, Blocks, etc to refer to actual minecraft blocks.

Pin
- 
Network
