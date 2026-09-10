"""Individual equipment data blocks on a common horizontal, in engine coordinates.

The caller supplies text and source custody. This module owns measurement and
placement; both exporters consume the same plan. No engineering is inferred.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from pandid.document import Annotation
from pandid.render.furniture import measure_annotation, text_width


def validate(value, units=None):
    if not isinstance(value, dict):
        raise ValueError('equipment_data must be a mapping by unit name')
    allowed = {'tags', 'rows', 'side', 'width', 'font_size', 'heading_font_size'}
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
        sides.add(row.get('side', 'below'))
        for field, default in (('width', 220), ('font_size', 11), ('heading_font_size', 24)):
            number = row.get(field, default)
            if isinstance(number, bool) or not isinstance(number, (int, float)) or not math.isfinite(number) or number <= 0:
                raise ValueError('equipment_data ' + field + ' must be positive and finite')
    if sides - {'above', 'below'} or len(sides) > 1:
        raise ValueError('equipment data blocks must share one above/below horizontal')
    return value


def _wrapped(text, width, font):
    result = []
    for paragraph in text.splitlines() or ['']:
        line = ''
        for word in paragraph.split():
            candidate = (line + ' ' + word).strip()
            if line and text_width(candidate, font) > width:
                result.append(line)
                line = word
            else:
                line = candidate
        result.append(line)
    return result


def _aligned_positions(desired, widths, left, gap=20):
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
    result=[0.0]*len(desired)
    for start,end,total,count in pools:
        for index in range(start,end):result[index]=max(left,total/count)+offsets[index]
    return result


@dataclass(frozen=True)
class DataBlock:
    unit_index: int
    annotation: Annotation
    x: float
    y: float
    w: float
    h: float


def plan(fs, inner):
    records = validate(fs.equipment_data, {u.name for u in fs.units})
    if not records:
        return [], inner
    blocks = []
    for index, unit in sorted(enumerate(fs.units), key=lambda pair: (pair[1].frame.x, pair[0])):
        if unit.name not in records:
            continue
        row = records[unit.name]
        font = row.get('font_size', 11)
        heading = row.get('heading_font_size', max(font+1,24))
        width = max(row.get('width', 220), text_width(row['tags'], heading, bold=True) + 18)
        lines = [part for line in row['rows'] for part in _wrapped(line, width - 18, font)]
        annotation = Annotation(title=row['tags'], rows=lines, width=width, font_size=font,
                                title_align="left", title_font_size=heading)
        w, h = measure_annotation(annotation)
        x = unit.frame.x
        blocks.append(DataBlock(index, annotation, x, 0, w, h))
    positions=_aligned_positions([b.x for b in blocks],[b.w for b in blocks],inner[0])
    blocks=[DataBlock(b.unit_index,b.annotation,x,0,b.w,b.h) for b,x in zip(blocks,positions)]
    height = max(b.h for b in blocks)
    y = inner[3] + 65 if next(iter(records.values())).get('side', 'below') == 'below' else inner[1] - height - 65
    blocks = [DataBlock(b.unit_index, b.annotation, b.x, y, b.w, b.h) for b in blocks]
    return blocks, (min(inner[0], min(b.x for b in blocks)), min(inner[1], y),
                    max(inner[2], max(b.x + b.w for b in blocks)), max(inner[3], y + height))
