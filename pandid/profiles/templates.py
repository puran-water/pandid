"""Render engineering template appearances through pandid's typed unit API.

Database roles and UUIDs are opaque custody attributes. Symbol selection and
semantic port aliases live here, beside the engine that owns those symbols.
No position from a retired graphical backend is interpreted as engineering.
"""
from __future__ import annotations

import inspect
import re

from pandid import Block, Feed, Flowsheet, Instrument, Junction, Product
from pandid.render.symbols import default_registry
from pandid.spec import _resolve_kind

ALIASES = {
    'pump.centrifugal': ('pump', 'default'),
    'tank.vertical': ('tank', 'vertical'),
    'valve.gate': ('valve', 'gate'),
    'house.pump.rotary_lobe': ('pump', 'rotary_lobe'),
    'house.mbr.membrane_cage': ('membrane_cage', 'default'),
    'house.mbr.airlift': ('airlift', 'default'),
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
        return Instrument(full_tag, variant=variant)
    if symbol in {'boundary', 'boundary.reference'}:
        cls = Feed if not incoming else Product
        return cls(key, reference=row.get('reference', ''), width=190 if row.get('connector') else None, height=85 if row.get('connector') else None)
    if symbol in {'block', 'process.package', 'control.device'}:
        return Block(key, inputs=max(1, len(incoming)), outputs=max(1, len(outgoing)), label_pos='center')
    if symbol == 'process.junction':
        if not incoming and not outgoing:
            return Junction(key)
        return Junction(key, inputs=max(1, len(incoming)), outputs=max(1, len(outgoing)))
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


def from_template(name, nodes, edges, *, metadata, print_scale=2.7, pins=None):
    """Create one flowsheet from already projected engineering appearances.

    Each edge is a real semantic path, including paths collapsed by a PFD's
    detail policy. Optional pins are pandid's explicit override API.
    """
    fs = Flowsheet(name)
    fs.print_scale = print_scale
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
    streams = {}
    for edge in edges:
        source, target = units[edge['source']], units[edge['target']]
        kind = edge['kind']
        ends = []
        for side, unit, name, direction in [('out', source, edge['source_port'], 'outlet'),
                                           ('in', target, edge['target_port'], 'inlet')]:
            key = edge['source'] if side == 'out' else edge['target']
            slots = [e for e in ports[key][side] if e['kind'] == kind]
            ends.append(_port(unit, name, direction, kind, slots, slots.index(edge)))
        # An empty displayed label does not erase stream identity. Metadata
        # retains its semantic key; only the drawing label is suppressed.
        stream = fs.connect(*ends, name=edge['key'], kind=kind)
        streams[edge['key']] = stream
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
