"""
Represent netlists, or circuits made of instances, with ports, that are collections of (I/O)
pins and the networks (connections between them).

These are abstract / logical netlists: They don't represent schematic blocks, regions,
placements, or bussing. Instances should be subclassed to provide this extra context.

Concepts:
- Pin: An individual input/output bit on an instance.

- Port: A sequence of input/output bits on an instance, typically a word vector of some length.
    All pins are part of exactly one port. All pins within the same port are either 'input' or
    'output', never mixed. Pins are identified by their index in their associated port, and are
    otherwise unnamed.

- Instance: A component / black-box chunk of circuitry that has inputs and outputs.
    Inputs/outputs are specified as ports. Ports are identified by their name, IE "A", "B",
    "cin", "cout", "dout", "clock", etc.

- Network: A connection from one output (or 'driver') port on one instance to a set of input
    ports on other instances. This is how we represent network wire connections.
    Networks may connect the same instance to itself.

    Networks actually specify both port _and_ a pin ID slice, allowing subsets of a port's
    pins to drive subsets of other ports' pins. In python notation, for example, we can
    use a single network to specify:
        'a[0:4] = b[4:8] = out[0:8:2]'

    This implies that a single port may be used as the driver in multiple networks, and that
    a single pin may be used as a driver pin in any subset of the networks its port drives.
    A port may be driven by multiple networks, but each individual pin may not.

- Netlist: A set of instances and the networks that connect them.
    Netlists may have two special instances: "input" and "output".
    These instances specify, though their outputs and inputs respectively, the inputs
    and outputs to the netlist circuit as a whole.
    Netlists are the fundamental unity of circuit assembly, and may be used hierarchically
    to construct complex circuits. Netlist inherits from Instance.


>>> from redhdl.netlist.netlist import example_adder_instance
>>> pprint(example_adder_instance)
ExampleInstanceType(ports={'a': Port(port_type='in', pin_count=4),
                           'b': Port(port_type='in', pin_count=4),
                           'cin': Port(port_type='in', pin_count=1),
                           'cout': Port(port_type='out', pin_count=1),
                           'out': Port(port_type='out', pin_count=4)},
                    context={'gen_params': {'bit_width': 4},
                             'orientation': 'north',
                             'placement': None,
                             'template_schematic': 'rsw_carry_cut_adder',
                             'type': 'adder'})


>>> from redhdl.netlist.netlist import example_netlist
>>> pprint(example_netlist, width=120)
Netlist(instances={'adder': ExampleInstanceType(...),
                   'constant_a': ExampleInstanceType(ports={'out': Port(port_type='out', pin_count=4)},
                                                     context={'gen_params': {'bit_width': 4, 'constant': 1},
                                                              'orientation': 'north',
                                                              'placement': None,
                                                              'type': 'constant'}),
                   'constant_b': ExampleInstanceType(...)},
        networks={0: Network(input_pin_id_seq=PinIdSequence(port_id=('constant_a', 'output'), slice=Slice(0, 4, 1)),
                             output_pin_id_seqs={PinIdSequence(port_id=('adder', 'a'), slice=Slice(0, 4, 1))}),
                  1: Network(input_pin_id_seq=PinIdSequence(port_id=('constant_b', 'output'), slice=Slice(0, 4, 1)),
                             output_pin_id_seqs={PinIdSequence(port_id=('adder', 'b'), slice=Slice(0, 4, 1))}),
                  2: Network(input_pin_id_seq=PinIdSequence(port_id=('adder', 'output'), slice=Slice(0, 4, 1)),
                             output_pin_id_seqs={PinIdSequence(port_id=('output', 'out'), slice=Slice(0, 4, 1))})})

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
                  *
                  *
                  *
              +--------+
              | output |
              +--------+
"""

from collections.abc import Iterable
from copy import deepcopy
from dataclasses import dataclass
from functools import wraps
from itertools import groupby
from typing import Any, Literal, Optional

from frozendict import frozendict

from redhdl.misc.ascii_dag import draw
from redhdl.misc.slice import Slice

PortType = Literal["in", "out"]


@dataclass
class Port:
    """Ports have a type and pin count."""

    port_type: PortType
    pin_count: int


@dataclass
class Instance:
    """Instances have a named set of ports."""

    ports: dict[str, Port]


PortName = str
InstanceId = str
PortId = tuple[InstanceId, PortName]
PinId = tuple[PortId, int]


# A sequence of pins on the same port.
@dataclass(frozen=True)
class PinIdSequence:
    port_id: PortId
    slice: Slice

    @property
    def pin_ids(self) -> list[PinId]:
        return [(self.port_id, pin_index) for pin_index in self.slice]

    def __len__(self):
        return len(self.pin_ids)


def instance_cache(func):
    func._cache = {}

    @wraps(func)
    def wrapper(self, *args, **kwargs):
        key = (id(self), tuple(args), tuple(kwargs.items()))
        if key not in func._cache:
            func._cache[key] = func(self, *args, **kwargs)

        return func._cache[key]

    return wrapper


@dataclass
class Network:
    """
    A network is a set of connected pins across the netlist.
    Because we frequently wire things on a byte, word, or other bit-width
    basis, we say a network connects one driving output pin sequence to
    downstream input pin sequences.

    TODO: This should be frozen, but it makes the specification much more
        clunky. Consider alternatives, or whether hashability is a priority.
    """

    input_pin_id_seq: PinIdSequence
    output_pin_id_seqs: set[PinIdSequence]

    def __post_init__(self):
        # For debugging only.
        assert (
            len(
                set(self.input_pin_id_seq.pin_ids)
                & {
                    output_pin_id
                    for output_pin_seq in self.output_pin_id_seqs
                    for output_pin_id in output_pin_seq.pin_ids
                }
            )
            == 0
        ), "Attempted to create cyclic network."

        assert (
            len(self.input_pin_id_seq) > 0
        ), "Attempted to create network without any pins."

        assert all(
            len(output_pin_seq) == len(self.input_pin_id_seq)
            for output_pin_seq in self.output_pin_id_seqs
        ), "Attempted to create network with mismatching bit_widths."

    @property
    def bit_width(self) -> int:
        return len(self.input_pin_id_seq)

    @instance_cache
    def all_pin_ids(self) -> set[PinId]:
        """
        >>> pprint(example_network.all_pin_ids())
        {(('accumulator', 'in'), 0),
         (('accumulator', 'in'), 1),
         (('accumulator', 'in'), 2),
         (('accumulator', 'in'), 3),
         (('adder', 'output'), 0),
         (('adder', 'output'), 1),
         (('adder', 'output'), 2),
         (('adder', 'output'), 3),
         (('registers', 'in'), 0),
         (('registers', 'in'), 1),
         (('registers', 'in'), 2),
         (('registers', 'in'), 3)}
        """
        return set(self.input_pin_id_seq.pin_ids) | {
            output_pin_id
            for output_pin_seq in self.output_pin_id_seqs
            for output_pin_id in output_pin_seq.pin_ids
        }

    def subnetwork(self, instance_ids: set[InstanceId]) -> Optional["Network"]:
        if self.input_pin_id_seq.port_id[0] not in instance_ids:
            return None

        subnet_output_pin_seqs = {
            output_pin_id_seq
            for output_pin_id_seq in self.output_pin_id_seqs
            if output_pin_id_seq.port_id[0] in instance_ids
        }

        if len(subnet_output_pin_seqs) == 0:
            return None

        return Network(
            input_pin_id_seq=self.input_pin_id_seq,
            output_pin_id_seqs=subnet_output_pin_seqs,
        )


NetworkId = int


@dataclass
class Netlist:
    """
    See top-level module __doc__ for background.

    Instance: A module with defined input and output ports.
    Port: An ordered collection of pins. Part of one instance.
    Pin: A one-bit input or output. Part of one port. Connected to one network.
    Network: A set of pins. Only one pin may be an 'output' (from an Instance) / driver
        pin, rest must be inputs (to Instances).

    This semantic graph is not nicely represented by a plain-old-data DAG in its own right.
    Instead of allowing potentially-deduplicated diamond-shaped data structures (which may
    be more compute-efficient, but more complicated), this is a minimal, moderately encoded
    format (which is more storage-efficient, might not be less compute efficient, and is much
    less stateful).

    Instances breaks out into details such as type, port-pincounts, and more.
    Ports and pins are identified by (<instance_id>, <port_index>) and (<port_id>, <pin_index>)
    respectively.

    Netlists may be partial / have inputs and outputs.
    The special instances "input" and "output" have corresponding ports describing
    the I/O ports of the entire netlist.

    The top level netlist represents instances and available networks.
    Here we use dictionaries from NetworkId: int -> <object> to avoid tricky vector-packing logic
    and use IDs for everything to reduce the amount of state / simplify reasoning.
    """

    instances: dict[InstanceId, Instance]
    networks: dict[NetworkId, Network]
    "Dictionary so we don't have to pack a vector when manipulating netlists."

    @property  # type: ignore
    @instance_cache
    def pin_networks(self) -> frozendict[PinId, frozenset[NetworkId]]:
        """
        For _any_ I/O pin, the associated networks.

        >>> pprint({**example_netlist.pin_networks})
        {(('adder', 'a'), 0): frozenset({0}),
         ...
         (('adder', 'a'), 3): frozenset({0}),
         (('adder', 'b'), 0): frozenset({1}),
         ...
         ...
         (('constant_a', 'output'), 3): frozenset({0}),
         (('constant_b', 'output'), 0): frozenset({1}),
         ...
         (('constant_b', 'output'), 3): frozenset({1}),
         (('output', 'out'), 0): frozenset({2}),
         ...
         (('output', 'out'), 3): frozenset({2})}
        """
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

    def port(self, port_id: PortId) -> Port:
        instance_id, port_name = port_id
        return self.instances[instance_id].ports[port_name]

    @property
    def next_network_id(self) -> NetworkId:
        """Next available Network ID for netlist manipulations."""
        return (max(self.networks.keys()) + 1) if self.networks else 0

    def display_ascii(self) -> None:
        vertices = sorted(str(instance_id) for instance_id in self.instances.keys())
        to_from_edges = sorted(
            {
                (
                    output_pin_id_seq.port_id[0],
                    network.input_pin_id_seq.port_id[0],
                )
                for network in self.networks.values()
                for output_pin_id_seq in network.output_pin_id_seqs
            }
        )
        draw(vertices, to_from_edges)

    @instance_cache
    def io_ports(self) -> dict[str, Port]:
        """
        The I/O ports for a given Netlist.

        >>> from redhdl.netlist.netlist import example_netlist
        >>> pprint(example_netlist.io_ports())
        {'out': Port(port_type='out', pin_count=4)}
        """
        if "input" in self.instances:
            input_ports = {
                name: Port("in", pin_count=port.pin_count)
                for name, port in self.instances["input"].ports.items()
                if port.port_type == "out"
            }
        else:
            input_ports = {}

        if "output" in self.instances:
            output_ports = {
                name: Port("out", pin_count=port.pin_count)
                for name, port in self.instances["output"].ports.items()
                if port.port_type == "in"
            }
        else:
            output_ports = {}

        return input_ports | output_ports

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
        >>> pprint(subnetlist, width=120)
        Netlist(instances={'adder': ExampleInstanceType(...),
                           'constant_a': ExampleInstanceType(...)},
                networks={0: Network(input_pin_id_seq=PinIdSequence(port_id=('constant_a', 'output'), slice=Slice(0, 4, 1)),
                                     output_pin_id_seqs={PinIdSequence(port_id=('adder', 'a'), slice=Slice(0, 4, 1))})})
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

    def source_dest_pin_id_seq_pairs(
        self,
    ) -> Iterable[tuple[PinIdSequence, PinIdSequence]]:
        """All non-I/O PinIdSequence -> PinIdSequence pairs."""

        for _network_id, network in self.networks.items():
            instance_id, port_name = network.input_pin_id_seq.port_id
            if instance_id == "input":
                continue

            for dest_pin_id_seq in network.output_pin_id_seqs:
                instance_id, port_name = dest_pin_id_seq.port_id
                if instance_id == "output":
                    continue

                yield (network.input_pin_id_seq, dest_pin_id_seq)


@dataclass
class ExampleInstanceType(Instance):
    context: dict[str, Any]


example_adder_instance: Instance = ExampleInstanceType(
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
example_constant_instance: Instance = ExampleInstanceType(
    ports={"out": Port("out", pin_count=4)},
    context={
        "type": "constant",
        "gen_params": {"constant": 1, "bit_width": 4},
        "orientation": "north",
        "placement": None,
    },
)

example_network = Network(
    input_pin_id_seq=PinIdSequence(("adder", "output"), Slice(4)),
    output_pin_id_seqs={
        PinIdSequence(("accumulator", "in"), Slice(4)),
        PinIdSequence(("registers", "in"), Slice(4)),
    },
)

example_netlist: Netlist = Netlist(
    instances={
        "constant_a": deepcopy(example_constant_instance),
        "constant_b": deepcopy(example_constant_instance),
        "adder": deepcopy(example_adder_instance),
        "output": Instance({"out": Port("in", 4)}),
    },
    networks={
        0: Network(
            input_pin_id_seq=PinIdSequence(("constant_a", "output"), Slice(4)),
            output_pin_id_seqs={PinIdSequence(("adder", "a"), Slice(4))},
        ),
        1: Network(
            input_pin_id_seq=PinIdSequence(("constant_b", "output"), Slice(4)),
            output_pin_id_seqs={PinIdSequence(("adder", "b"), Slice(4))},
        ),
        2: Network(
            input_pin_id_seq=PinIdSequence(("adder", "output"), Slice(4)),
            output_pin_id_seqs={PinIdSequence(("output", "out"), Slice(4))},
        ),
    },
)
