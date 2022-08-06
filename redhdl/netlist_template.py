"""
>>> from pprint import pprint
>>> netlist = netlist_from_simple_spec(example_instance_config, example_networks)
>>> pprint(netlist)
Netlist(instances={'and': SchematicInstance(...),
                   'not_a': SchematicInstance(...),
                   'not_b': SchematicInstance(...),
                   'not_out': SchematicInstance(...)},
        networks={0: Network(input_pin_id_seq=PinIdSequence(port_id=('not_a',
                                                                     'out'),
                                                            slice=Slice(0, 8, 1)),
                             output_pin_id_seqs={PinIdSequence(port_id=('and',
                                                                        'a'),
                                                               slice=Slice(0, 8, 1))}),
                  ...
                  2: Network(input_pin_id_seq=PinIdSequence(port_id=('and',
                                                                     'out'),
                                                            slice=Slice(0, 8, 1)),
                             output_pin_id_seqs={PinIdSequence(port_id=('not_out',
                                                                        'in'),
                                                               slice=Slice(0, 8, 1))})})
"""
from typing import cast

from redhdl.instance_template import schematic_instance_from_schem
from redhdl.netlist import Instance, Netlist, Network, PinIdSequence
from redhdl.schematic import load_schem
from redhdl.slice import Slice

example_instance_config = {
    "and": {"schem_name": "and_h8b"},  # Eventually: Break out the and, horiz, 8b parts.
    "not_a": {"schem_name": "not_h8b"},
    "not_b": {"schem_name": "not_h8b"},
    "not_out": {"schem_name": "not_h8b"},
}

example_networks = {
    (("not_a", "out"), Slice(8)): {(("and", "a"), Slice(8))},
    (("not_b", "out"), Slice(8)): {(("and", "b"), Slice(8))},
    (("and", "out"), Slice(8)): {(("not_out", "in"), Slice(8))},
}


def netlist_from_simple_spec(instance_schem_name, networks) -> Netlist:
    instances = {
        name: schematic_instance_from_schem(
            load_schem(f"schematic_examples/hdl_{config['schem_name']}.schem")
        )
        for name, config in instance_schem_name.items()
    }
    networks = {
        i: Network(
            input_pin_id_seq=PinIdSequence(*driver_seq),
            output_pin_id_seqs={PinIdSequence(*dest_seq) for dest_seq in dest_seqs},
        )
        for i, (driver_seq, dest_seqs) in enumerate(networks.items())
    }

    return Netlist(cast(dict[str, Instance], instances), networks)
