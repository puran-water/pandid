"""Physical process drafting profile shared by all process templates.

The title strip retains its own paper scale. The diagram uses one fixed scale,
never the amount of spare space on a particular sheet. Capacity is checked before
export; a busy sheet must be arranged again, never shrunk into smaller lettering.
"""
PROFILE = "circle-h2o.process-drafting/1"
DRAWING_SCALE = .44
PRINT_SCALE = 2.7
#: The one page this profile draws, and so the band its rails are placed against.
PAGE = "A1"
#: Paper kept inside the band for ink that sits just outside the equipment:
#: route bends, leaders and the approach to a boundary flag. The same figure
#: ``layout/coordinates.py`` reserves when it fills a band's columns, so the
#: two agree about how much of the band is actually spendable.
ESCAPE_LANE = 50.0
#: Clear pipe run between the padded core and each flag's nozzle rail.
BOUNDARY_APPROACH = 110.0
UNIT_SIZES = {"membrane_cage": (100, 134), "air_diffuser": (128, 64),
              "basin_agitator": (64, 180), "submersible_mixer": (100, 70)}


def apply(fs):
    fs.print_scale = PRINT_SCALE
    fs.drawing_scale = DRAWING_SCALE
    fs.layout_options.boundary_page = PAGE
    fs.stream_labels.font_size = 14
    fs.layout_options.aligned_boundaries = True
    fs.layout_options.fill_columns = True
    fs.layout_options.band_width = 2200
    fs.layout_options.instrument_clearance = 4
    fs.layout_options.stream_label_bands = 24
    fs.layout_options.strict_label_clearance = True
    return fs


def align_boundaries(fs):
    """Reserve a left inlet column and a right outlet column before routing.

    Hanging the rails off the core's own extent puts them wherever the content
    happens to end, and a fixed page then centres the whole drawing in the band
    left for it -- so the flags land mid-sheet and the clearance to the frame is
    whatever slack remains. On the 2026-09-10 library that was 34 to 279 mm, and
    no sheet reached the boundary. With ``boundary_span`` set, the rails are
    placed so the pennants' outer edges meet the band instead.
    """
    from dataclasses import replace
    from pandid.layout.halo import balloon_pads, core_extent
    boundaries = [u for u in fs.units if u.kind in {"feed", "product"}]
    extent = core_extent(((u, u.frame) for u in fs.units), balloon_pads(fs))
    if extent is None or not boundaries:
        return
    left = extent[0] - BOUNDARY_APPROACH
    right = extent[1] + BOUNDARY_APPROACH
    page = getattr(fs.layout_options, "boundary_page", None)
    if page:
        from pandid.render.drawio import fitted_band

        # The band is what the dock leaves; it is not all spendable. Route
        # bends and leaders sit a little outside the equipment they serve,
        # and a fixed-scale export measures that ink like any other -- so
        # rails hung on the last unit of the band guarantee an overflow the
        # moment a corner turns outboard of a flag. ``_filled_gap`` already
        # reserves exactly this lane when it spends a band's spare paper
        # (``layout/coordinates.py``, "one nozzle escape lane at either
        # end"); the rails were the one place it was not applied, which is
        # why uhp-1 overflowed by the 15 units of a single waypoint.
        span = fitted_band(fs, page)[0] - ESCAPE_LANE
        # The span names the pennants' outer edges, and a pennant reaches its own
        # width past the rail it hangs on -- ``boundary_flag`` draws a feed back
        # from its anchor and a product forward from it. Reach is therefore the
        # widest flag on each rail, not a constant: a library whose flags carry a
        # reference code is wider than one whose flags do not.
        reach_l = max((u.frame.w for u in boundaries if u.kind == "feed" and u.frame), default=0.0)
        reach_r = max((u.frame.w for u in boundaries if u.kind == "product" and u.frame), default=0.0)
        # Never pull a rail in through the core: a sheet whose content already
        # fills the band keeps its own extent, and the capacity check downstream
        # is what reports that.
        half = max((span - reach_l - reach_r) / 2, (right - left) / 2)
        centre = (left + right) / 2
        left, right = centre - half, centre + half
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
