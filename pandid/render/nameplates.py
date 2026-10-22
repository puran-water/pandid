"""Individual equipment data blocks on a common horizontal, in engine coordinates.

The caller supplies text and source custody. This module owns measurement and
placement; both exporters consume the same plan. No engineering is inferred.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, replace
from pandid.document import Annotation
from pandid.render.furniture import measure_annotation, text_width


def validate(value, units=None):
    if not isinstance(value, dict):
        raise ValueError('equipment_data must be a mapping by unit name')
    allowed = {'tags', 'rows', 'side', 'width', 'font_size', 'heading_font_size', 'gap', 'clearance', 'fit_width'}
    sides = set()
    for key, row in value.items():
        if not isinstance(key, str) or not isinstance(row, dict) or set(row) - allowed:
            raise ValueError('invalid equipment_data record')
        if units is not None and key not in units:
            raise ValueError('equipment_data names absent unit: ' + key)
        if not isinstance(row.get('tags'), str) or not row['tags']:
            raise ValueError('equipment_data needs all equipment tags as text')
        if not isinstance(row.get('rows'), list) or any(not isinstance(s, str) for s in row['rows']):
            raise ValueError('equipment_data rows must be text')
        if type(row.get('fit_width', False)) is not bool:
            raise ValueError('equipment_data fit_width must be boolean')
        sides.add(row.get('side', 'below'))
        for field, default in (('width', 220), ('font_size', 11), ('heading_font_size', 24), ('gap', 20), ('clearance', 65)):
            number = row.get(field, default)
            if isinstance(number, bool) or not isinstance(number, (int, float)) or not math.isfinite(number) or number <= 0:
                raise ValueError('equipment_data ' + field + ' must be positive and finite')
    if sides - {'above', 'below'} or len(sides) > 1:
        raise ValueError('equipment data blocks must share one above/below horizontal')
    if len({row.get('gap', 20) for row in value.values()}) > 1:
        raise ValueError('equipment data blocks must share one horizontal gap')
    if len({row.get('clearance', 65) for row in value.values()}) > 1:
        raise ValueError('equipment data blocks must share one vertical clearance')
    return value


def _wrapped(text, width, font):
    result = []
    for paragraph in text.splitlines() or ['']:
        line = ''
        # A rating and its unit are one typographic token. Keep source text
        # intact while preventing a line break between e.g. 41.37 and bar.
        tokens = re.findall(r'\S+(?:[ \t]+(?:m³/h|m3/h|m²|m2|m³|m3|bar|barg|kPa|MPa|kW|µm|mm|m|L/h|°C))?(?=\s|$)', paragraph)
        for word in tokens:
            candidate = (line + ' ' + word).strip()
            if line and text_width(candidate, font) > width:
                result.append(line)
                line = word
            else:
                line = candidate
        result.append(line)
    return result


def _aligned_positions(desired, widths, left, gap=20, right=None):
    """Least-squares alignment without the former one-way rightward drift.

    Subtract cumulative box widths, then use pooled adjacent violators to
    solve the ordered coordinates. All boxes stay on one horizontal and near
    their equipment; a wide early heading cannot push every later box east.
    """
    offsets, pools, offset = [], [], 0
    for index, (x, width) in enumerate(zip(desired, widths)):
        offsets.append(offset)
        pools.append([index, index+1, x-offset, 1])
        while len(pools)>1 and pools[-2][2]/pools[-2][3] > pools[-1][2]/pools[-1][3]:
            b=pools.pop();a=pools.pop()
            pools.append([a[0],b[1],a[2]+b[2],a[3]+b[3]])
        offset += width+gap
    # Use available paper on both sides. A heading can move toward its unit
    # only within the existing drawing width (or the minimum width needed by
    # the row). Otherwise a late unit needlessly enlarges the whole A1 sheet.
    upper = max(left, right - (offset-gap)) if right is not None else math.inf
    result=[0.0]*len(desired)
    for start,end,total,count in pools:
        for index in range(start,end):result[index]=min(upper,max(left,total/count))+offsets[index]
    return result


@dataclass(frozen=True)
class DataBlock:
    unit_index: int
    annotation: Annotation
    x: float
    y: float
    w: float
    h: float


def label_boxes(tags, numbers):
    """Occupied text/leader extents for fitting and the common data row."""
    boxes = (list(tags.plates) if tags is not None else []) + [number.box for number in numbers]
    for number in numbers:
        if number.leader:
            a,b=number.leader
            boxes.append((min(a[0],b[0]),min(a[1],b[1]),max(a[0],b[0]),max(a[1],b[1])))
    return boxes


def extend_bounds(inner, boxes):
    if not boxes:
        return inner
    return (min(inner[0],*(b[0] for b in boxes)),min(inner[1],*(b[1] for b in boxes)),
            max(inner[2],*(b[2] for b in boxes)),max(inner[3],*(b[3] for b in boxes)))


def plan(fs, inner, *, fit_to_ink=False):
    records = validate(fs.equipment_data, {u.name for u in fs.units})
    if not records:
        return [], inner
    if getattr(fs, '_dense_nameplates', None):
        blocks = fixed_blocks(fs)
        if fit_to_ink:
            # Packing reserves a common row at the paper's bottom. Once all
            # routed pipes and captions are measured, reclaim only the empty
            # gap above that row. Overhead route detours must not cause an
            # overflow while this unused paper remains below the process.
            clearance = next(iter(records.values())).get('clearance', 65)
            top = inner[3]+clearance
            if top < min(b.y for b in blocks):
                fs._dense_nameplates = {name: replace(block,y=top)
                                       for name,block in fs._dense_nameplates.items()}
                blocks = fixed_blocks(fs)
        return blocks, extend_bounds(inner, [(b.x,b.y,b.x+b.w,b.y+b.h) for b in blocks])
    blocks = []
    equipment = [(i, u) for i, u in enumerate(fs.units) if u.name in records]
    for index, unit in sorted(equipment, key=lambda pair: (pair[1].frame.x, pair[0])):
        row = records[unit.name]
        font = row.get('font_size', 11)
        heading = row.get('heading_font_size', max(font+1,24))
        # An unbreakable engineering value (for example a drive-type token)
        # cannot wrap. Reserve its measured width at the fixed body type size;
        # the complete row still goes through the ordinary capacity gate.
        fit_width = row.get('fit_width', False)
        pad = 7. if fit_width else 9.
        word_width = max((text_width(word, font) for line in row['rows']
                          for word in _wrapped(line, 0, font)), default=0)
        width = max(0 if fit_width else row.get('width', 220),
                    text_width(row['tags'], heading, bold=True) + 2*pad, word_width + 2*pad)
        lines = [part for line in row['rows'] for part in _wrapped(line, width - 2*pad, font)]
        annotation = Annotation(title=row['tags'], rows=lines, width=width, font_size=font,
                                title_align="left", title_font_size=heading,horizontal_padding=pad)
        w, h = measure_annotation(annotation)
        x = unit.frame.x
        blocks.append(DataBlock(index, annotation, x, 0, w, h))
    gap = next(iter(records.values())).get('gap', 20)
    page = fs.layout_options.boundary_page
    if page:
        from pandid.render.drawio import fitted_band
        width = fitted_band(fs, page)[0] - 50
        from pandid.layout.subsystems import declared
        if (declared(fs) or any(r.get('fit_width') for r in records.values())) and sum(b.w for b in blocks) + gap*(len(blocks)-1) <= width:
            blocks = _fit_cards(fs, records, blocks, width, gap)
    positions=_aligned_positions([b.x for b in blocks],[b.w for b in blocks],inner[0],right=inner[2], gap=gap)
    blocks=[DataBlock(b.unit_index,b.annotation,x,0,b.w,b.h) for b,x in zip(blocks,positions)]
    height = max(b.h for b in blocks)
    clearance = next(iter(records.values())).get('clearance', 65)
    y = inner[3] + clearance if next(iter(records.values())).get('side', 'below') == 'below' else inner[1] - height - clearance
    blocks = [DataBlock(b.unit_index, b.annotation, b.x, y, b.w, b.h) for b in blocks]
    return blocks, (min(inner[0], min(b.x for b in blocks)), min(inner[1], y),
                    max(inner[2], max(b.x + b.w for b in blocks)), max(inner[3], y + height))


def fixed_blocks(fs):
    blocks = getattr(fs, '_dense_nameplates', {})
    if not blocks:
        return []
    if fs.equipment_data != getattr(fs, '_dense_nameplate_source', None):
        raise ValueError('EQUIPMENT_DATA_LAYOUT_STALE: lay out the changed source fields again')
    if set(blocks) != set(fs.equipment_data):
        raise ValueError('EQUIPMENT_DATA_LAYOUT_INCOMPLETE')
    return list(blocks.values())


def fixed_boxes(fs):
    """Data already placed inside the diagram is solid lettering, not free paper."""
    return [(b.x,b.y,b.x+b.w,b.y+b.h) for b in fixed_blocks(fs)]


def _fit_cards(fs, records, blocks, width, gap):
    """Spend unused row width on complete values, at unchanged lettering.

    Every card retains one column and its complete tag heading on one line.
    Choose the lowest common row height that fits all measured cards, without
    shrinking type or breaking a value away from its unit.
    """
    choices = []
    for block in blocks:
        row = records[fs.units[block.unit_index].name]
        font, heading = row.get('font_size', 11), row.get('heading_font_size', 24)
        pad=block.annotation.horizontal_padding
        natural = max((text_width(text, font) for text in row['rows']), default=0) + 2*pad
        options = [block]
        maximum = min(width, max(block.w, natural))
        sizes = [block.w + 24*i for i in range(int((maximum-block.w)/24)+1)] + [maximum]
        for candidate_width in sizes:
            lines = [part for text in row['rows']
                     for part in _wrapped(text, candidate_width-2*pad, font)]
            annotation = Annotation(title=block.annotation.title, rows=lines,
                width=candidate_width, font_size=font, title_align='left', title_font_size=heading,
                horizontal_padding=pad)
            w, h = measure_annotation(annotation)
            options.append(DataBlock(block.unit_index, annotation, block.x, 0, w, h))
        choices.append(options)
    for height in sorted({b.h for options in choices for b in options}):
        proposed = []
        for options in choices:
            eligible = [b for b in options if b.h <= height]
            if not eligible:
                break
            proposed.append(min(eligible, key=lambda b: (b.w, b.h)))
        if len(proposed) == len(blocks) and sum(b.w for b in proposed)+gap*(len(proposed)-1) <= width:
            return proposed
    return blocks
