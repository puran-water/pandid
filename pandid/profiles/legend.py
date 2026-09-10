"""Discipline-wide grouped panels with adjacent symbols and meanings."""
from collections import OrderedDict
from pandid.units import Unit
from pandid.render.symbols import Symbol, default_registry
from pandid.render.furniture import text_width
from pandid.drawing_regions import Caption, Region
from pandid.profiles.templates import from_template


class _LegendAnchor(Unit):
    kind = 'legend_anchor'
    def __init__(self, name, inlet_face='W'):
        super().__init__(name)
        self.inlet_face = inlet_face
        for name, direction, role in [('p_in', 'inlet', 'process'), ('p_out', 'outlet', 'process'),
                                       ('s_in', 'inlet', 'signal'), ('s_out', 'outlet', 'signal')]:
            self._add_port(name, direction, role)

    @property
    def tag(self):
        return ''

    def symbol(self):
        return Symbol(svg='<g id="sym_legend_anchor"/>', width=1, height=1,
            ports={name: ((.5,0) if self.inlet_face == 'N' else (0,.5)) if p.direction == 'inlet'
                   else (1,.5) for name, p in self.ports.items()},
            faceless_ports=frozenset(self.ports))


def _wrap(text, width, font):
    result, line = [], ''
    for word in text.split():
        candidate = (line + ' ' + word).strip()
        if line and text_width(candidate, font) > width:
            result.append(line)
            line = word
        else:
            line = candidate
    return result + [line]


def pages(entries, *, metadata_factory, title='SYMBOLS AND CONVENTIONS'):
    """Cover the complete admitted inventory in one multi-sheet document.

    Nanded informs the sectioned arrangement. Actual engine units and streams
    illustrate symbols and line types; no separate pictures or XML assemblies.
    """
    groups = OrderedDict((name, []) for name in ('PROCESS EQUIPMENT', 'VALVES AND ACTUATORS',
        'PIPING AND CONNECTIONS', 'INSTRUMENTATION', 'PROCESS AND SIGNAL LINES',
        'HOUSE TAGGING AND CONVENTIONS', 'EQUIPMENT DATA BLOCKS', 'ABBREVIATIONS'))
    for entry in entries:
        if entry['kind'] == 'symbol':
            category = entry.get('category', 'equipment')
            group = ('VALVES AND ACTUATORS' if category == 'valve-body' else
                     'PIPING AND CONNECTIONS' if category in {'piping', 'junction', 'boundary'} else
                     'INSTRUMENTATION' if category in {'instrument', 'control-loop'} else 'PROCESS EQUIPMENT')
        else:
            group = {'line': 'PROCESS AND SIGNAL LINES', 'profile': 'EQUIPMENT DATA BLOCKS',
                     'abbreviation': 'ABBREVIATIONS'}.get(entry['kind'], 'HOUSE TAGGING AND CONVENTIONS')
        groups[group].append(entry)
    material = next(e for e in entries if e['kind'] == 'line' and e['key'] == 'material')
    groups['PROCESS AND SIGNAL LINES'].insert(1, {**material, 'id': material['id'] + '-secondary',
        'key': 'secondary', 'meaning': 'Secondary process / utility line; same connected piping semantics, lighter lineweight.'})
    line_order = ['material','secondary','energy','electric','pneumatic','hydraulic','capillary','data','software']
    groups['PROCESS AND SIGNAL LINES'].sort(key=lambda e: (line_order.index(e['key']) if e['key'] in line_order else 99, e['key']))
    columns = []
    for heading, items in groups.items():
        column, height = [], 44
        for entry in items:
            symbol = entry['kind'] in {'symbol', 'line'}
            text = entry['meaning'] if symbol else entry['key'].replace('-', ' ').upper() + ' — ' + entry['meaning']
            wrapped = _wrap(text, 446 if symbol else 646, 14)
            row_height = max(78 if symbol else 30, len(wrapped) * 17 + 16)
            if entry['key'] in {'boundary', 'boundary.reference'}:
                row_height = max(row_height, 94)
            if entry['key'] in {'house.mixer.agitator', 'house.mbr.membrane_cage'}:
                row_height = max(row_height, 210)
            if entry['key'] == 'stencil.pid.flow_sensors.magnetic':
                row_height = max(row_height, 130)
            if height + row_height > 1300 and column:
                columns.append((heading, column, height))
                column, height = [], 44
            column.append((entry, wrapped, row_height))
            height += row_height
        if column:
            columns.append((heading, column, height))
    result = []
    for start in range(0, len(columns), 3):
        meta = metadata_factory(len(result) + 1)
        rows, pins, specimens, descriptions, panels = [], {}, [], [], []
        for col, (heading, items, height) in enumerate(columns[start:start+3]):
            x, y = col * 700, 44
            panel_key = f'panel-{start+col}'
            panels.append(Region(panel_key, x, 0, 684, height, heading, 20))
            meta['cells']['region-' + panel_key] = {'id': panel_key,
                'attributes': {'puran-kind': 'legend-panel', 'legend-category': heading}}
            for entry, wrapped, row_height in items:
                key = 'entry-' + entry['id']
                is_symbol = entry['kind'] in {'symbol', 'line'}
                reference = entry['key'] in {'boundary', 'boundary.reference'}
                if reference:
                    wrapped = _wrap(entry['meaning'], 446, 14)
                descriptions.append(Caption(key, x + (220 if is_symbol else 12), y + 8,
                    446 if is_symbol else 646, row_height - 12, '\n'.join(wrapped), 14))
                meta['cells']['region-' + key] = {'id': entry['id'] + '-caption',
                    'attributes': {'puran-kind': 'legend-entry', 'legend-key': entry['key'], 'meaning': entry['meaning']}}
                if entry['kind'] == 'symbol':
                    rows.append({'key': key, 'id': entry['id'], 'symbol': entry['key'], 'label': '',
                        'instrument_function': 'FIC' if entry['key'] == 'instrument.control-room' else 'FIT',
                        'instrument_loop': f'{len(rows)+1:02}',
                        'attributes': {'puran-kind': 'legend-symbol', 'symbol-key': entry['key'], 'legend-key': entry['key'], 'meaning': entry['meaning']},
                        **({'connector': {'code': 'A', 'description': 'WATER\nTO SHEET 2'}} if entry['key'] == 'boundary.reference' else {})})
                    pins[key] = {'x': x + 16, 'y': y + 12}
                    specimens.append((entry, key, x, y, row_height))
                elif entry['kind'] == 'line':
                    specimens.append((entry, key, x, y, row_height))
                y += row_height
        fs = from_template(title, rows, [], metadata=meta, pins=pins)
        fs.regions, fs.captions = panels, descriptions
        fs.layout_options.aligned_boundaries = False
        fs.stream_labels.enclosure = 'none'
        for entry, key, x, y, row_height in specimens:
            if entry['kind'] == 'symbol':
                unit = next(u for u in fs.units if fs.drawio_metadata['units'].get(u.name, {}).get('id') == entry['id'])
                sym = default_registry.for_unit(unit)
                scale = min(180 / sym.width, (row_height - 24) / sym.height, 1.0)
                unit.width, unit.height = sym.width * scale, sym.height * scale
                from pandid.profiles.process import UNIT_SIZES
                if unit.kind in UNIT_SIZES:
                    unit.width, unit.height = UNIT_SIZES[unit.kind]
                if unit.kind == "instrument":
                    unit.width, unit.height = 44, 44
                if unit.kind in {'feed', 'product'}:
                    unit.width, unit.height = 190, 85
                    unit.pin(x=x + 12 + (140 if unit.kind == 'feed' else 0), y=y + row_height/2)
                    if getattr(unit, 'reference_code', ''):
                        unit.display_label = 'WATER\nTO SH. 2'
                if unit.kind == 'instrument':
                    unit.pin(x=x + 30, y=y + 12)
                if unit.kind == 'junction':
                    unit.pin(x=x+50, y=y+row_height/2-2)
                    positions = [(x+15,y+row_height/2),(x+94,y+row_height/2),(x+52,y+row_height-8)]
                    for i,(port,position) in enumerate(zip(unit.ports.values(),positions)):
                        anchor=fs.add(_LegendAnchor(key+'-branch-'+str(i), 'N' if i==2 else 'W')).pin(x=position[0],y=position[1])
                        ends=(anchor.p_out,port) if port.direction=='inlet' else (port,anchor.p_in)
                        line=fs.connect(*ends,name=key+'-branch-'+str(i));line.display_label=''
                if entry['key'] == 'stencil.pid.flow_sensors.magnetic':
                    from pandid import Instrument
                    unit.pin(x=x + 34, y=y + 96)
                    balloon = fs.add(Instrument('250-FIT-01'))
                    balloon.attach(unit, at='N', offset=55)
                    fs.drawio_metadata['units'][balloon.name] = {'id': entry['id'] + '-balloon',
                        'attributes': {'puran-kind': 'legend-symbol', 'legend-key': 'magnetic-fit-assembly'}}
            else:
                a, b = fs.add(_LegendAnchor(key + '-a')), fs.add(_LegendAnchor(key + '-b'))
                a.pin(x=x+15, y=y+row_height/2)
                b.pin(x=x+94, y=y+row_height/2)
                kind = 'material' if entry['key'] == 'secondary' else entry['key']
                from pandid.streams import SIGNAL_KINDS
                signal = kind in SIGNAL_KINDS
                line = fs.connect(a.s_out if signal else a.p_out, b.s_in if signal else b.p_in,
                                  name=key, kind=kind)
                line.flow_class = 'secondary' if entry['key'] == 'secondary' else 'main'
                line.display_label = ''
                fs.drawio_metadata['streams'][key] = {'id': entry['id'],
                    'attributes': {'puran-kind': 'legend-line', 'legend-key': entry['key'],
                        'connection-kind': kind, 'flow-class': line.flow_class}}
        result.append(fs)
    return result
