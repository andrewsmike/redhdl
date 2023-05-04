"""
Create a netlist of schematic-backed instances from a simple spec.

Describe your instances and their configuration (here, schematic path):
>>> pprint(example_instance_configs)
{'and': {'schem_name': 'and_h8b'},
 'not_a': {'schem_name': 'not_h8b'},
 'not_b': {'schem_name': 'not_h8b'},
 'not_out': {'schem_name': 'not_h8b'}}

Specify the I/O relationships between your instances:
>>> pprint(example_network_specs)
{(('and', 'out'), Slice(0, 8, 1)): {(('not_out', 'in'), Slice(0, 8, 1))},
 (('input', 'a'), Slice(0, 8, 1)): {(('not_a', 'in'), Slice(0, 8, 1))},
 (('input', 'b'), Slice(0, 8, 1)): {(('not_b', 'in'), Slice(0, 8, 1))},
 (('not_a', 'out'), Slice(0, 8, 1)): {(('and', 'a'), Slice(0, 8, 1))},
 (('not_b', 'out'), Slice(0, 8, 1)): {(('and', 'b'), Slice(0, 8, 1))},
 (('not_out', 'out'), Slice(0, 8, 1)): {(('output', 'out'), Slice(0, 8, 1))}}

Generate a thoroughly-typed Netlist object, with SchematicInstances, representing your netlist.
>>> netlist = netlist_from_simple_spec(example_instance_configs, example_network_specs)
>>> pprint(netlist)
Netlist(instances={'and': SchematicInstance(...),
                   'input': Instance(ports={}),
                   'not_a': SchematicInstance(...),
                   'not_b': SchematicInstance(...),
                   'not_out': SchematicInstance(...),
                   'output': Instance(ports={})},
        networks={0: Network(input_pin_id_seq=PinIdSequence(port_id=('not_a',
                                                                     'out'),
                                                            slice=Slice(0, 8, 1)),
                             output_pin_id_seqs={PinIdSequence(port_id=('and',
                                                                        'a'),
                                                               slice=Slice(0, 8, 1))}),
                  ...})

>>> netlist.display_ascii()  # doctest: +NORMALIZE_WHITESPACE
            +-------+
            | input |
            +-------+
            **      **
           *          *
          *            *
    +-------+       +-------+
    | not_a |       | not_b |
    +-------+       +-------+
            **      **
              *    *
               *  *
             +-----+
             | and |
             +-----+
                *
                *
                *
           +---------+
           | not_out |
           +---------+
                *
                *
                *
            +--------+
            | output |
            +--------+
"""
from typing import cast

from redhdl.instance_template import schematic_instance_from_schem
from redhdl.netlist import (
    Instance,
    InstanceId,
    Netlist,
    Network,
    PinIdSequence,
    Port,
    PortId,
)
from redhdl.schematic import load_schem
from redhdl.slice import Slice

InstanceConfig = dict[str, str | int]

example_instance_configs: dict[InstanceId, InstanceConfig] = {
    "and": {"schem_name": "and_h8b"},  # Eventually: Break out the and, horiz, 8b parts.
    "not_a": {"schem_name": "not_h8b"},
    "not_b": {"schem_name": "not_h8b"},
    "not_out": {"schem_name": "not_h8b"},
}

NetworkSpecs = dict[tuple[PortId, Slice], set[tuple[PortId, Slice]]]

example_network_specs: NetworkSpecs = {
    (("not_a", "out"), Slice(8)): {(("and", "a"), Slice(8))},
    (("not_b", "out"), Slice(8)): {(("and", "b"), Slice(8))},
    (("and", "out"), Slice(8)): {(("not_out", "in"), Slice(8))},
    (("input", "a"), Slice(8)): {(("not_a", "in"), Slice(8))},
    (("input", "b"), Slice(8)): {(("not_b", "in"), Slice(8))},
    (("not_out", "out"), Slice(8)): {(("output", "out"), Slice(8))},
}


def netlist_from_simple_spec(
    instance_config: dict[InstanceId, InstanceConfig],
    network_specs: NetworkSpecs,
    input_port_bitwidths: dict[str, int] | None = None,
    output_port_bitwidths: dict[str, int] | None = None,
) -> Netlist:
    instances = {
        name: schematic_instance_from_schem(
            load_schem(f"schematic_examples/hdl_{config['schem_name']}.schem")
        )
        for name, config in instance_config.items()
    }
    io_instances = {
        "input": Instance(
            {
                name: Port("out", bitwidth)
                for name, bitwidth in (input_port_bitwidths or {}).items()
            },
        ),
        "output": Instance(
            {
                name: Port("in", bitwidth)
                for name, bitwidth in (output_port_bitwidths or {}).items()
            },
        ),
    }
    networks = {
        i: Network(
            input_pin_id_seq=PinIdSequence(*driver_seq),
            output_pin_id_seqs={PinIdSequence(*dest_seq) for dest_seq in dest_seqs},
        )
        for i, (driver_seq, dest_seqs) in enumerate(network_specs.items())
    }

    return Netlist(cast(dict[str, Instance], instances | io_instances), networks)
