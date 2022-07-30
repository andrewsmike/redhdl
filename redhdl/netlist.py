"""
Represent netlists, or circuits made of instances, with ports, that are collections of (I/O)
pins and the networks (connections between them).

These are abstract / logical netlists: They don't represent schematic blocks, regions,
placements, or bussing. This information is stored in separate datastructures that may
reference abstract netlists, or may be attached as part of the InstanceContext generic.

>>> from pprint import pprint

>>> from redhdl.netlist import example_adder_instance
>>> pprint(example_adder_instance)
Instance(ports={'a': Port(port_type='in', pin_count=4),
                'b': Port(port_type='in', pin_count=4),
                'cin': Port(port_type='in', pin_count=1),
                'cout': Port(port_type='out', pin_count=1),
                'out': Port(port_type='out', pin_count=4)},
         context={'gen_params': {'bit_width': 4},
                  'orientation': 'north',
                  'placement': None,
                  'template_schematic': 'rsw_carry_cut_adder',
                  'type': 'adder'})


>>> from redhdl.netlist import example_netlist
>>> pprint(example_netlist, width=120)
Netlist(instances={'adder': Instance(...),
                   'constant_a': Instance(ports={'out': Port(port_type='out', pin_count=4)},
                                          context={'gen_params': {'bit_width': 4, 'constant': 1},
                                                   'orientation': 'north',
                                                   'placement': None,
                                                   'type': 'constant'}),
                   'constant_b': Instance(...)},
        networks={0: Network(input_pin_id_run=PinIdRun(port_id=('constant_a', 'output'), slice=Slice(0, 4, 1)),
                             output_pin_id_runs={PinIdRun(port_id=('adder', 'a'), slice=Slice(0, 4, 1))}),
                  1: Network(input_pin_id_run=PinIdRun(port_id=('constant_b', 'output'), slice=Slice(0, 4, 1)),
                             output_pin_id_runs={PinIdRun(port_id=('adder', 'b'), slice=Slice(0, 4, 1))})})

>>> example_netlist.display_ascii()  # doctest: +NORMALIZE_WHITESPACE
+------------+         +------------+
| constant_a |         | constant_b |
+------------+         +------------+
            ***        ***
               *      *
                **  **
              +-------+
              | adder |
              +-------+
"""

from copy import deepcopy
from dataclasses import dataclass
from functools import cache
from itertools import groupby
from typing import Any, Generic, Literal, Optional, TypeVar

from frozendict import frozendict

from redhdl.ascii_dag import draw

PortType = Literal["in", "out"]


@dataclass
class Port:
    """Ports have a type and pin count."""

    port_type: PortType
    pin_count: int


# The more frozen structures, the better.
InstanceContext = TypeVar("InstanceContext")
"""
Arbitrary (meta)data attached to instances.
This makes abstractnetlists reusable for a variety of purposes.
"""


@dataclass
class Instance(Generic[InstanceContext]):
    ports: dict[str, Port]

    context: InstanceContext
    # Things that may be stored outside the network:
    # configuration, region data, placement data, block data, cached properties, etc


InstanceId = str
PortId = tuple[InstanceId, str]
PinId = tuple[PortId, int]


class Slice:
    """
    Hashable slice type, because slice() is unhashable to avoid accidental
    dict assignments.

    >>> Slice(4)
    Slice(0, 4, 1)

    >>> Slice(1, 3)
    Slice(1, 3, 1)

    >>> Slice(10, 0, -1)
    Slice(10, 0, -1)

    >>> Slice(4).values()
    [0, 1, 2, 3]

    >>> Slice(3, -1, -1).values()
    [3, 2, 1, 0]
    """

    start: int
    stop: int
    step: int

    def __init__(self, *args: int):
        if len(args) not in (1, 2, 3):
            raise ValueError("Slice usage: Slice(stop) or Slice(start, stop[, step]).")

        if len(args) == 1:
            self.stop = args[0]
            self.start = 0
            self.step = 1
        elif len(args) == 2:
            self.start = args[0]
            self.stop = args[1]
            self.step = 1
        elif len(args) == 3:
            self.start = args[0]
            self.stop = args[1]
            self.step = args[2]

    def values(self) -> list[int]:
        return list(range(self.start, self.stop, self.step))

    def __str__(self) -> str:
        return f"Slice({self.start}, {self.stop}, {self.step})"

    def __repr__(self) -> str:
        return f"Slice({self.start}, {self.stop}, {self.step})"

    def __hash__(self) -> int:
        return hash(repr(self))

    def __eq__(self, other) -> bool:
        return (
            self.start == other.start
            and self.stop == other.stop
            and self.step == other.step
        )


# A sequence of pins on the same port.
@dataclass(frozen=True)
class PinIdRun:
    port_id: PortId
    slice: Slice

    @property
    def pin_ids(self) -> list[PinId]:
        return [(self.port_id, pin_id) for pin_id in self.slice.values()]

    def __len__(self):
        return len(self.pin_ids)


@dataclass
class Network:
    """
    A network is a set of connected pins across the netlist.
    Because we frequently wire things on a byte, word, or other bit-width
    basis, we say a network connects one output 'pin run' to other input
    'pin runs'.
    Exactly one must be a driver / output pin.

    TODO: This should be frozen, but it makes the specification much more
        clunky. Consider alternatives, or whether hashability is a priority.
    """

    input_pin_id_run: PinIdRun
    output_pin_id_runs: set[PinIdRun]

    def __post_init__(self):
        # For debugging only.
        assert (
            len(
                set(self.input_pin_id_run.pin_ids)
                & {
                    output_pin_id
                    for output_pin_run in self.output_pin_id_runs
                    for output_pin_id in output_pin_run.pin_ids
                }
            )
            == 0
        ), "Attempted to create cyclic network."

        assert (
            len(self.input_pin_id_run) > 0
        ), "Attempted to create network without any pins."

        assert all(
            len(output_pin_run) == len(self.input_pin_id_run)
            for output_pin_run in self.output_pin_id_runs
        ), "Attempted to create network with mismatching bit_widths."

    @property
    def bit_width(self) -> int:
        return len(self.input_pin_id_run)

    @cache
    def all_pin_ids(self) -> set[PinId]:
        return set(self.input_pin_id_run.pin_ids) | {
            output_pin_id
            for output_pin_run in self.output_pin_id_runs
            for output_pin_id in output_pin_run.pin_ids
        }

    def subnetwork(self, instance_ids: set[InstanceId]) -> Optional["Network"]:
        if self.input_pin_id_run.port_id[0] not in instance_ids:
            return None

        subnet_output_pin_runs = {
            output_pin_id_run
            for output_pin_id_run in self.output_pin_id_runs
            if output_pin_id_run.port_id[0] in instance_ids
        }

        if len(subnet_output_pin_runs) == 0:
            return None

        return Network(
            input_pin_id_run=self.input_pin_id_run,
            output_pin_id_runs=subnet_output_pin_runs,
        )


NetworkId = int


@dataclass
class Netlist(Generic[InstanceContext]):
    """
    Instance: A module with defined input and output ports.
        Has an additional InstanceContext object for external usage.
    Port: An ordered collection of pins. Part of one instance.
    Pin: A one-bit input or output. Part of one port. Connected to one network.
    Network: A set of pins. Only one pin may be an 'output' (from an Instance) / driver
        pin, rest must be inputs (to Instances).

    This semantic graph is not nicely represented by a plain-old-data DAG in its own right.
    Instead of allowing potentially-deduplicated diamond-shaped references (which may be more
    compute-efficient, but more complicated), this is a minimal, moderately encoded format
    (which is more storage-efficient, might not be less compute efficient, and is much less
    stateful.)

    Instances breaks out into details such as type, port-pincounts, and more.
    Ports and pins are identified by (<instance_id>, <port_index>) and (<port_id>, <pin_index>)
    respectively.

    The top level netlist represents instances and available networks.
    Here we use dictionaries from ID -> <object> to avoid tricky vector-packing logic and
    IDs for everything to reduce the amount of state and simplify reasoning.
    """

    instances: dict[InstanceId, Instance[InstanceContext]]
    "Dictionary so we don't have to pack a vector when manipulating netlists."
    networks: dict[NetworkId, Network]
    "Dictionary so we don't have to pack a vector when manipulating netlists."

    @property  # type: ignore
    @cache
    def pin_networks(self) -> frozendict[PinId, frozenset[NetworkId]]:
        """For _any_ I/O pin, the associated networks."""
        pin_id_network_id_pairs = sorted(
            (pin_id, network_id)
            for network_id, network in self.networks.items()
            for pin_id in network.all_pin_ids()
        )

        return frozendict(
            (pin_id, frozenset(network_id for pin_id, network_id in pin_id_network_ids))
            for pin_id, pin_id_network_ids in groupby(
                sorted(pin_id_network_id_pairs),
                key=lambda pair: pair[0],
            )
        )

    @property
    def next_network_id(self) -> NetworkId:
        """Next available Network for netlist manipulations."""
        return (max(self.networks.keys()) + 1) if self.networks else 0

    def display_ascii(self) -> None:
        vertices = sorted(str(instance_id) for instance_id in self.instances.keys())
        to_from_edges = sorted(
            {
                (
                    output_pin_id_run.port_id[0],
                    network.input_pin_id_run.port_id[0],
                )
                for network in self.networks.values()
                for output_pin_id_run in network.output_pin_id_runs
            }
        )
        draw(vertices, to_from_edges)

    def is_subset(self, other) -> bool:
        """
        Is this network a subset of another network?

        >>> subnetlist = example_netlist.subnetlist({"adder", "constant_a"})

        >>> subnetlist.is_subset(example_netlist)
        True
        >>> example_netlist.is_subset(subnetlist)
        False

        is_subset is not strict:
        >>> example_netlist.is_subset(example_netlist)
        True
        >>> subnetlist.is_subset(subnetlist)
        True
        """
        return (
            set(self.instances.keys()).issubset(set(other.instances.keys()))
            and set(self.networks.keys()).issubset(set(other.networks.keys()))
            and all(
                instance == other.instances[instance_id]
                for instance_id, instance in self.instances.items()
            )
            and all(
                network.subnetwork(set(other.instances.keys()))
                == other.networks[network_id]
                for network_id, network in self.networks.items()
            )
        )

    def subnetlist(self, instance_ids: set[InstanceId]) -> "Netlist":
        """
        >>> subnetlist = example_netlist.subnetlist({"adder", "constant_a"})
        >>> subnetlist.display_ascii()  # doctest: +NORMALIZE_WHITESPACE
        +------------+
        | constant_a |
        +------------+
               *
               *
               *
          +-------+
          | adder |
          +-------+
        >>> from pprint import pprint
        >>> pprint(subnetlist, width=120)
        Netlist(instances={'adder': Instance(...),
                           'constant_a': Instance(...)},
                networks={0: Network(input_pin_id_run=PinIdRun(port_id=('constant_a', 'output'), slice=Slice(0, 4, 1)),
                                     output_pin_id_runs={PinIdRun(port_id=('adder', 'a'), slice=Slice(0, 4, 1))})})
        """
        return Netlist(
            instances={
                instance_id: instance
                for instance_id, instance in self.instances.items()
                if instance_id in instance_ids
            },
            networks={
                network_id: subnetwork
                for network_id, network in self.networks.items()
                if (subnetwork := network.subnetwork(instance_ids)) is not None
            },
        )


example_adder_instance: Instance[dict[str, Any]] = Instance(
    ports={
        "a": Port("in", pin_count=4),
        "b": Port("in", pin_count=4),
        "cin": Port("in", pin_count=1),
        "out": Port("out", pin_count=4),
        "cout": Port("out", pin_count=1),
    },
    context={
        "type": "adder",
        "template_schematic": "rsw_carry_cut_adder",
        "gen_params": {"bit_width": 4},
        "orientation": "north",  # For example.
        "placement": None,
    },
)
example_constant_instance: Instance[dict[str, Any]] = Instance(
    ports={"out": Port("out", pin_count=4)},
    context={
        "type": "constant",
        "gen_params": {"constant": 1, "bit_width": 4},
        "orientation": "north",
        "placement": None,
    },
)

example_netlist: Netlist[dict[str, Any]] = Netlist(
    instances={
        "constant_a": deepcopy(example_constant_instance),
        "constant_b": deepcopy(example_constant_instance),
        "adder": deepcopy(example_adder_instance),
    },
    networks={
        0: Network(
            input_pin_id_run=PinIdRun(("constant_a", "output"), Slice(4)),
            output_pin_id_runs={PinIdRun(("adder", "a"), Slice(4))},
        ),
        1: Network(
            input_pin_id_run=PinIdRun(("constant_b", "output"), Slice(4)),
            output_pin_id_runs={PinIdRun(("adder", "b"), Slice(4))},
        ),
    },
)
