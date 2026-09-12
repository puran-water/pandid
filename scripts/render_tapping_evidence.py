"""Render the dense tapping comparison through the selected pandid checkout.

Use the same input with the parent and corrected engines. The parent does not
understand along or host declarations, which is the before behaviour being
measured; this entrypoint never changes either engine's layout or emitted XML.
"""

import argparse
import hashlib
import json
from pathlib import Path

from pandid.profiles.templates import from_template
from pandid.render.svg import tap_lines
from pandid.spec import _read_title_block


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--label', required=True)
    args = parser.parse_args()
    source = json.loads(args.input.read_text())
    fs = from_template(source['name'], source['nodes'], source['edges'],
                       metadata=source['metadata'], pins=source['pins'])
    fs.title_block = _read_title_block(source['title_block'], 'title_block')
    fs.equipment_data = source['equipment_data']
    geometry = source['evidence_geometry']
    for unit in fs.units:
        if unit.name in geometry['unit_widths']:
            unit.width = geometry['unit_widths'][unit.name]
    fs.layout_options.fill_columns = geometry['fill_columns']
    args.out.mkdir(parents=True, exist_ok=True)
    xml = fs.to_drawio(diagram='p&id', page_size='A1', border='zone')
    (args.out / f'{args.label}.drawio').write_text(xml)
    (args.out / f'{args.label}-engine.svg').write_text(fs.to_svg(diagram='p&id'))
    report = {
        'label': args.label, 'units': len(fs.units), 'streams': len(fs.streams),
        'route_converged': fs.route_converged, 'drawing_scale': fs.drawing_scale,
        'print_scale': fs.print_scale, 'sha256': hashlib.sha256(xml.encode()).hexdigest(),
        'input_sha256': hashlib.sha256(args.input.read_bytes()).hexdigest(),
        'instruments': {}, 'segments': [], 'warnings': [str(w) for w in fs.warnings],
    }
    for unit in fs.units:
        if unit.kind == 'instrument':
            report['instruments'][unit.name] = {
                'tap': unit.tap, 'centre': [unit.frame.cx, unit.frame.cy],
                'size': [unit.frame.w, unit.frame.h], 'along': getattr(unit, 'along', None),
                'host': getattr(unit.host, 'name', None),
            }
    report['segments'] = [(u.name, a, b) for u, a, b in tap_lines(fs)]
    (args.out / f'{args.label}.json').write_text(json.dumps(report, indent=2) + '\n')
    print(args.label, report['units'], report['streams'], report['route_converged'])


if __name__ == '__main__':
    main()
