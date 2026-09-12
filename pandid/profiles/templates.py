"""Render engineering template appearances through pandid's typed unit API.

Database roles and UUIDs are opaque custody attributes. Symbol selection and
semantic port aliases live here, beside the engine that owns those symbols.
No position from a retired graphical backend is interpreted as engineering.
"""
from __future__ import annotations

import inspect
import re
from collections import defaultdict
from uuid import NAMESPACE_URL, uuid5

from pandid import Block, Feed, Flowsheet, Instrument, Junction, Product
from pandid.render.symbols import default_registry
from pandid.spec import _resolve_kind

ALIASES = {
    "house.basin.concrete": ("concrete_basin", "default"),
    "house.mixer.agitator": ("basin_agitator", "default"),
    "house.mixer.submersible": ("submersible_mixer", "default"),
    'pump.centrifugal': ('pump', 'default'),
    'tank.vertical': ('tank', 'vertical'),
    'valve.gate': ('valve', 'gate'),
    'house.pump.rotary_lobe': ('pump', 'rotary_lobe'),
    'house.mbr.membrane_cage': ('membrane_cage', 'default'),
    'house.mbr.airlift': ('airlift', 'default'),
    'house.air.diffuser_grid': ('air_diffuser', 'default'),
}


def symbol_type(symbol):
    if symbol in ALIASES:
        return ALIASES[symbol]
    if symbol.startswith('stencil.'):
        key = 'mxgraph.' + symbol.removeprefix('stencil.')
        matches = [(k, v) for (k, v), sym in default_registry._symbols.items() if sym.drawio_shape == key]
        if not matches:
            normalized = re.sub('[^a-z0-9]', '', key.lower())
            matches = [(k, v) for (k, v), sym in default_registry._symbols.items() if re.sub('[^a-z0-9]', '', sym.drawio_shape.lower()) == normalized]
        if matches:
            return min(matches, key=lambda kv: (kv[1] != 'default', len(kv[1]), kv))
    raise ValueError('PANDID_SYMBOL_UNMAPPED: ' + symbol)


def _unit(row, incoming, outgoing):
    key, symbol = row['key'], row['symbol']
    label = row.get('label', '')
    if symbol.startswith('instrument.') or symbol == 'controller.plc':
        variant = 'shared' if symbol == 'instrument.control-room' else 'sis' if symbol == 'controller.plc' else 'default'
        function = row['instrument_function']
        loop = row['instrument_loop']
        full_tag = label if re.fullmatch(r'\d+-[A-Za-z]+-.+', label) else function + '-' + loop
        unit = Instrument(full_tag, variant=variant)
        if row.get('measured_variable'):
            unit.annotate(variable=row.get('measured_variable'))
            # The house reference puts analyser descriptors at upper right.
            # This departs from ISO 15519-2 5.1.3's quadrant b for U tags;
            # it is a house convention, not a claim of general conformance.
            unit.quadrants['c'] = unit.quadrants.pop('b')
        return unit
    if symbol in {'boundary', 'boundary.reference'}:
        cls = Feed if not incoming else Product
        return cls(key, reference=row.get('reference', ''), width=190 if row.get('connector') else None, height=85 if row.get('connector') else None)
    if symbol in {'block', 'process.package', 'control.device'}:
        return Block(key, inputs=max(1, len(incoming)), outputs=max(1, len(outgoing)), label_pos='center')
    if symbol == 'process.junction':
        if not incoming and not outgoing:
            return Junction(key)
        return Junction(key, inputs=max(1, len(incoming)), outputs=max(1, len(outgoing)),
                        header=row.get('attributes',{}).get('semantic-class')=='PipeHeader'
                               and max(len(incoming),len(outgoing))>1)
    kind, variant = symbol_type(symbol)
    cls = _resolve_kind(kind, row['key'])
    kwargs = {'variant': variant}
    params = inspect.signature(cls).parameters
    if 'inputs' in params:
        kwargs['inputs'] = max(1, len(incoming))
    if 'outputs' in params:
        kwargs['outputs'] = max(1, len(outgoing))
    return cls(key, **kwargs)


def _port(unit, name, direction, kind, slots, index):
    if unit.kind == 'instrument':
        return unit.sig_out if direction == 'outlet' else unit.sig_in
    if kind not in {'material', 'energy'}:
        if direction == 'inlet' and 'actuator' in unit.ports:
            return unit.actuator
        if name in unit.ports and unit.ports[name].role != 'process':
            return unit.ports[name]
        raise ValueError(f'PANDID_SIGNAL_PORT_UNMAPPED: {unit.name}/{name}')
    aliases = {'membrane': 'suction', 'permeate': 'discharge'} if unit.kind == 'pump' else {}
    if unit.kind == 'cooling_tower':
        aliases.update(inlet='water_in', outlet='water_out')
    port = aliases.get(name, name)
    if port in unit.ports and unit.ports[port].direction == direction:
        return unit.ports[port]
    candidates = [p for p in unit.ports.values() if p.direction == direction and p.role in {'process', 'feed', 'product', 'utility', 'energy'}]
    # Variable families expose a deterministic tuple of real nozzles. Their
    # declaration, not obsolete x/y fractions, decides the attachment point.
    if len(candidates) == 1:
        return candidates[0]
    family = getattr(unit, 'outlets' if direction == 'outlet' else 'inlets', ())
    if len(family) >= len(slots):
        return family[index]
    raise ValueError(f'PANDID_PROCESS_PORT_UNMAPPED: {unit.name}/{name}; available: {[p.name for p in candidates]}')


def from_template(name, nodes, edges, *, metadata, print_scale=2.7, pins=None, fixed_drafting=True):
    """Create one flowsheet from already projected engineering appearances.

    Each edge is a real semantic path, including paths collapsed by a PFD's
    detail policy. Optional pins are pandid's explicit override API.
    """
    fs = Flowsheet(name)
    fs.print_scale = print_scale
    if fixed_drafting:
        from pandid.profiles.process import apply
        apply(fs)
    # The process profile uses compact columns; labels and instrument halos
    # still reserve their measured space before routing.
    fs.layout_options.column_gap = 20
    fs.layout_options.stream_spacing = 14
    fs.layout_options.control_passes = 16
    fs.layout_options.control_grid = 1
    fs.layout_options.parallel_trains = True
    fs.stream_labels.enclosure = 'none'
    fs.drawio_metadata = {'units': {}, 'streams': {}, **metadata}
    ports = {row['key']: {'in': [], 'out': []} for row in nodes}
    for edge in edges:
        ports[edge['source']]['out'].append(edge)
        ports[edge['target']]['in'].append(edge)
    units = {}
    for row in nodes:
        key = row['key']
        material = {side: [e for e in group if e['kind'] in {'material', 'energy'}] for side, group in ports[key].items()}
        unit = _unit(row, material['in'], material['out'])
        if fixed_drafting:
            from pandid.profiles.process import UNIT_SIZES
            if unit.kind in UNIT_SIZES:
                unit.width, unit.height = UNIT_SIZES[unit.kind]
        if unit.kind != 'instrument':
            unit.display_label = row.get('label', '')
        if row.get('connector'):
            unit.reference_code = row['connector']['code']
            unit.display_label = row['connector']['description']
            unit.reference = ''
        fs.add(unit)
        units[key] = unit
        fs.drawio_metadata['units'][unit.name] = {'id': row['id'], 'attributes': row['attributes']}
        if key in (pins or {}):
            unit.pin(**pins[key])
    for row in nodes:
        if row.get('contained_by'):
            fs.contain(units[row['key']], units[row['contained_by']])
    # Resolve ports before connecting. A grouped PFD appearance can receive
    # several distinct member paths at one nominal nozzle. Give that appearance
    # an explicit pipe fan; do not connect two streams to one physical port or
    # silently delete a member path. Fans are presentation-only metadata.
    endpoints, uses = {}, defaultdict(list)
    for edge in edges:
        kind = edge['kind']
        ends = []
        for side, unit, name, direction in [('out', units[edge['source']], edge['source_port'], 'outlet'),
                                           ('in', units[edge['target']], edge['target_port'], 'inlet')]:
            key = edge['source'] if side == 'out' else edge['target']
            slots = [e for e in ports[key][side] if (e['kind'] in {'material', 'energy'}
                     if kind in {'material', 'energy'} else e['kind'] == kind)]
            ends.append(_port(unit, name, direction, kind, slots, slots.index(edge)))
            uses[(key,ends[-1].name)].append((edge,len(ends)-1))
        endpoints[edge['key']]=ends
    by_key={row['key']:row for row in nodes}
    for (key,port_name), paths in uses.items():
        if len(paths)<2:
            continue
        row=by_key[key]
        if not row['attributes'].get('equipment-group'):
            raise ValueError(f'PANDID_DUPLICATE_PROCESS_PORT: {key}/{port_name}; declare distinct ports or a junction')
        kinds={edge['kind'] for edge,_ in paths}
        if len(kinds)!=1 or not kinds <= {'material','energy'}:
            raise ValueError('Grouped appearance port fans require one material or energy kind')
        direction=paths[0][1]
        if any(side!=direction for _,side in paths):
            raise ValueError('Grouped appearance port fan has contradictory flow directions')
        port=units[key].ports[port_name]
        fan_key='projection-'+str(uuid5(NAMESPACE_URL,str(row['id'])+':'+port_name))
        fan=Junction(fan_key,inputs=1 if direction==0 else len(paths),outputs=len(paths) if direction==0 else 1,header=True)
        fs.add(fan)
        attrs={'puran-kind':'projection-junction','projection-for':str(row['id']),'projection-port':port_name}
        fs.drawio_metadata['units'][fan.name]={'id':fan_key,'attributes':attrs}
        common_kind=next(iter(kinds))
        common=fs.connect(port,fan.inlets[0],name=fan_key+'-stem',kind=common_kind) if direction==0 else fs.connect(fan.outlets[0],port,name=fan_key+'-stem',kind=common_kind)
        common.display_label=''
        common.flow_class='secondary' if all(edge.get('flow_class')=='secondary' for edge,_ in paths) else 'main'
        fs.drawio_metadata['streams'][common.name]={'id':fan_key+'-stem','attributes':{
            **attrs,'puran-kind':'projection-connection','member-paths':[edge['key'] for edge,_ in paths]}}
        for index,(edge,side) in enumerate(paths):
            endpoints[edge['key']][side]=(fan.outlets if direction==0 else fan.inlets)[index]
    streams = {}
    for edge in edges:
        kind=edge['kind']
        # An empty displayed label does not erase stream identity. Metadata
        # retains its semantic key; only the drawing label is suppressed.
        stream = fs.connect(*endpoints[edge['key']], name=edge['key'], kind=kind)
        streams[edge['key']] = stream
        stream.representation = edge.get('representation', 'pipe')
        stream.flow_class = edge.get('flow_class') or 'main'
        stream.display_label = edge.get('label', '')
        fs.drawio_metadata['streams'][stream.name] = {'id': edge['id'],
                                                     'attributes': edge['attributes']}
        if edge.get('via'):
            stream.via(edge['via'])
    for row in nodes:
        if row.get('attachment'):
            attachment = row['attachment']
            target = (units if attachment['kind'] == 'unit' else streams)[attachment['target']]
            units[row['key']].attach(target, at=attachment.get('at'), offset=attachment.get('offset', 60))
    return fs
