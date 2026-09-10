"""Physical process drafting profile shared by all process templates.

The title strip retains its own paper scale. The diagram uses one fixed scale,
never the amount of spare space on a particular sheet. Capacity is checked before
export; a busy sheet must be arranged again, never shrunk into smaller lettering.
"""
PROFILE = "circle-h2o.process-drafting/1"
DRAWING_SCALE = .44
PRINT_SCALE = 2.7
UNIT_SIZES = {"membrane_cage": (100, 134), "air_diffuser": (128, 64),
              "basin_agitator": (64, 180), "submersible_mixer": (100, 70)}


def apply(fs):
    fs.print_scale = PRINT_SCALE
    fs.drawing_scale = DRAWING_SCALE
    fs.stream_labels.font_size = 14
    fs.layout_options.aligned_boundaries = True
    fs.layout_options.band_width = 2200
    fs.layout_options.instrument_clearance = 4
    return fs


def align_boundaries(fs):
    """Reserve a left inlet column and a right outlet column before routing."""
    from dataclasses import replace
    from pandid.portgeom import unit_box
    boundaries = [u for u in fs.units if u.kind in {"feed", "product"}]
    core = [u for u in fs.units if u.kind not in {"feed", "product", "instrument"} and u.frame]
    if not core or not boundaries:
        return
    left = min(unit_box(u, u.frame)[0] for u in core) - 110
    right = max(unit_box(u, u.frame)[2] for u in core) + 110
    for kind in ("feed", "product"):
        cursor = float("-inf")
        for unit in sorted((u for u in boundaries if u.kind == kind), key=lambda u: (u.frame.cy, u.name)):
            f = unit.frame
            y = max(f.y, cursor)
            x = left - 50 if kind == "feed" else right
            if unit.pin_ and unit.pin_.x is not None and abs(unit.pin_.x - x) > .01:
                raise ValueError("BOUNDARY_COLUMN_PIN_CONFLICT: " + unit.name)
            unit.frame = replace(f, x=x, y=y)
            cursor = y + f.h + 24


def inspect_drawio(document):
    """Check repeated printed primitives across an A1 process/legend document.

    XML is measured in its final native paper units. Equipment containers may
    grow around their internals; balloons, flags and lettering do not grow with
    topology density. The report is suitable for a publication manifest.
    """
    import xml.etree.ElementTree as ET
    root=ET.fromstring(document) if isinstance(document,(str,bytes)) else document
    samples={}
    def record(key, value, page, uid):
        value=tuple(round(float(n),4) for n in value)
        old=samples.setdefault(key, {'value':value, 'appearances':0})
        if old['value'] != value:
            raise ValueError(f'INCONSISTENT_PRINTED_SIZE: {key}; {page}/{uid}: {value} differs from {old["value"]}')
        old['appearances']+=1
    for page in root.findall('diagram'):
        by_id={c.get('id'):(c,c.find('mxCell')) for c in page.findall('.//object') if c.find('mxCell') is not None}
        left,right=[],[]
        for uid,(obj,cell) in by_id.items():
            kind=obj.get('puran-kind')
            style=dict(v.split('=',1) for v in cell.get('style','').split(';') if '=' in v)
            geo=cell.find('mxGeometry')
            symbol=obj.get('symbol-key','')
            if kind in {'connection','legend-line'}:
                line_kind=obj.get('connection-kind','material')
                line_class=(line_kind+':'+obj.get('flow-class','main')) if line_kind in {'material','energy'} else line_kind
                record('lineweight:'+line_class,[style.get('strokeWidth',1)],page.get('id'),uid)
            if kind in {'entity','legend-symbol'} and symbol in {'instrument.field','instrument.control-room','controller.plc','boundary.reference'}:
                record('symbol:'+symbol, [geo.get('width',0),geo.get('height',0)],page.get('id'),uid)
            text=obj.get('label',cell.get('value',''))
            if text and 'fontSize' in style and style.get('noLabel') != '1':
                category=None
                owner=by_id.get(obj.get('for-cell'),(None,None))[0]
                if owner is not None and owner.get('puran-kind')=='equipment-data':
                    category='equipment-data-body'
                elif owner is not None and owner.get('puran-kind')=='connection':
                    category='line-label'
                if kind in {'equipment-data','equipment-data-heading'}:
                    category=kind
                elif kind in {'connection','legend-line'}:
                    category='line-label'
                elif (symbol.startswith('instrument.') or symbol=='controller.plc') and kind in {'entity','legend-symbol'}:
                    category='instrument-inscription'
                elif kind=='entity' and symbol not in {'boundary','boundary.reference','process.junction'}:
                    category='equipment-tag'
                elif uid.endswith('-code') or uid.endswith('-description'):
                    category='connector-'+uid.rsplit('-',1)[1]
                if category:
                    record('text:'+category,[style['fontSize']],page.get('id'),uid)
            if kind=='entity' and symbol=='boundary.reference':
                # Native arrow orientation is the same; source/target ownership
                # identifies whether this is a feed or an outlet.
                used_as_source=any(c.get('source')==uid and c.get('visible')!='0' for _,c in by_id.values())
                (left if used_as_source else right).append(round(float(geo.get('x',0)),4))
        if len(set(left))>1 or len(set(right))>1:
            raise ValueError('BOUNDARY_COLUMNS_MISALIGNED: '+page.get('id',''))
    return {'profile':PROFILE,'native_units_per_inch':100,'samples':samples}
