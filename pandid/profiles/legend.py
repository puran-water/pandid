"""Discipline-wide legend sheets rendered with the same symbol engine."""
from __future__ import annotations

import textwrap
from pandid import Annotation, Block, Flowsheet, Instrument
from pandid.streams import PROCESS_KINDS, STREAM_KINDS
from pandid.profiles.templates import from_template


def pages(entries, *, metadata_factory, title='SYMBOLS AND CONVENTIONS'):
    """Return one shared document's pages, with stable entry identities.

    Inputs are the complete admitted symbol and convention inventory, never an
    inventory clipped to whichever process area happened to render first.
    """
    symbols = [e for e in entries if e['kind'] == 'symbol']
    words = [e for e in entries if e['kind'] != 'symbol']
    result = []
    # Real connected units exercise the same stroke, dash and pneumatic
    # marks as a process sheet. No second table of illustrative line art.
    kinds = sorted(STREAM_KINDS)
    for start in range(0, len(kinds), 4):
        fs = Flowsheet(title + ' — PIPING AND SIGNALS')
        fs.print_scale = 2.7
        fs.drawio_metadata = metadata_factory(len(result) + 1)
        fs.drawio_metadata.update(units={}, streams={})
        captions = []
        for n, kind in enumerate(kinds[start:start+4]):
            first = 2 * (start + n) + 1
            cls = Block if kind in PROCESS_KINDS else Instrument
            names = (kind.upper(), 'DESTINATION') if cls is Block else (f'FIT-{first}', f'FIC-{first}')
            a, b = fs.add(cls(names[0])), fs.add(cls(names[1]))
            a.pin(x=0, y=n * 150)
            b.pin(x=480, y=n * 150)
            line = fs.connect(a.outlets[0] if cls is Block else a.sig_out,
                              b.inlets[0] if cls is Block else b.sig_in,
                              name=kind.upper(), kind=kind)
            for index, unit in enumerate((a, b)):
                fs.drawio_metadata['units'][unit.name] = {'id': f'line-{kind}-{index}',
                    'attributes': {'puran-kind': 'legend-symbol', 'legend-key': kind}}
            fs.drawio_metadata['streams'][line.name] = {'id': 'line-' + kind,
                'attributes': {'puran-kind': 'legend-entry', 'legend-key': kind}}
            captions.append(f'{names[0]} → {names[1]}: {kind} connection')
        fs.add_annotation(Annotation(title='CONNECTION TYPES', rows=captions, align='top-right'))
        result.append(fs)
    for start in range(0, len(symbols), 6):
        batch = symbols[start:start+6]
        page_number = len(result) + 1
        meta = metadata_factory(page_number)
        rows, pins = [], {}
        for n, entry in enumerate(batch):
            key = 'legend-' + str(start + n)
            caption = entry['key'].removeprefix('stencil.pid.').replace('_', ' ')
            rows.append({'key': key, 'id': entry['id'], 'symbol': entry['key'],
                'label': '\n'.join(textwrap.wrap(caption, width=25, break_long_words=False)),
                'instrument_function': 'FIT', 'instrument_loop': f'{start+n+1:02}',
                'attributes': {'puran-kind': 'legend-symbol', 'symbol-key': entry['key'], 'legend-key': entry['key'], 'meaning': entry['meaning']},
                **({'connector': {'code': 'A', 'description': 'SERVICE\nTO / FROM SHEET'}} if entry['key'] == 'boundary.reference' else {})})
            pins[key] = {'x': 120 + (n % 2) * 380, 'y': 70 + (n // 2) * 220}
        fs = from_template(title, rows, [], metadata=meta, pins=pins)
        result.append(fs)
    texts = symbols + words
    for start in range(0, len(texts), 10):
        fs = Flowsheet(title)
        fs.print_scale = 2.7
        fs.drawio_metadata = metadata_factory(len(result) + 1)
        fs.drawio_metadata['cells']['f1'] = {'id': 'legend-definitions-' + str(start),
            'attributes': {'puran-kind': 'legend-entry'}}
        rows = []
        for entry in texts[start:start+10]:
            caption = entry['key'].removeprefix('stencil.pid.').replace('_', ' ')
            rows += textwrap.wrap(caption + ': ' + entry['meaning'], width=110, break_long_words=False)
            rows.append('')
        fs.add_annotation(Annotation(title='SYMBOL MEANINGS AND HOUSE CONVENTIONS', rows=rows,
                                     font_size=11, align='top-left'))
        result.append(fs)
    return result
