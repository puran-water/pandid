"""Uniform block layout in ordered process roll-up lanes.

The engine receives lane membership and logical order, chooses the grid, and
pins its own blocks. Named nozzles and all stream routing remain pandid's.
No coordinates or legacy routes are accepted from a project drawing.
"""
import math
from collections import defaultdict
from pandid.drawing_regions import Region
from pandid.render.furniture import text_width


def wrap_label(text, width=252, font_size=22):
    lines = []
    for paragraph in text.splitlines():
        line = ""
        for word in paragraph.split():
            candidate = (line + " " + word).strip()
            if line and text_width(candidate, font_size) > width:
                lines.append(line)
                line = word
            else:
                line = candidate
        lines.append(line)
    return "\n".join(lines)


def plan(blocks, streams, lanes):
    by_lane = defaultdict(list)
    for row in blocks:
        by_lane[row['lane']].append(row)
    definitions = {r['id']: r for r in lanes}
    if set(by_lane) - set(definitions):
        raise ValueError('BFD lane is absent from the ordered lane vocabulary')
    columns = max(4, min(8, max(len(v) for v in by_lane.values())))
    columns = max(columns, max((int(r.get('column') or 0) + 1 for r in blocks), default=1))
    positions, regions, y = {}, [], 0
    labels = {r['key']: wrap_label(r['label']) for r in blocks}
    width, height = 280, max(150, max(len(s.splitlines()) for s in labels.values()) * 26.4 + 18)
    logical = {}
    lane_rows = {}
    for lane in lanes:
        rows = sorted(by_lane.get(lane['id'], []), key=lambda r: (r.get('order') if r.get('order') is not None else math.inf, r['key']))
        occupied = set()
        for row in sorted(rows, key=lambda r: r.get('column') is None):
            slot = (int(row.get('row') or 0), int(row['column'])) if row.get('column') is not None else None
            if slot is None:
                slot = next((n // columns, n % columns) for n in range(len(rows) + columns * 5) if (n // columns, n % columns) not in occupied)
            if slot in occupied:
                raise ValueError('Two BFD blocks claim the same logical lane slot')
            occupied.add(slot)
            logical[row['key']] = (lane['id'], *slot)
        if rows:
            lane_rows[lane['id']] = 1 + max(r for r, c in occupied)
    # Faces follow the peer's lane/slot. Cross-lane services use roof/floor
    # nozzles instead of crowding every stream onto one vertical face.
    faces = {r['key']: {'in': [], 'out': []} for r in blocks}
    rank = {r['id']: n for n, r in enumerate(lanes)}
    for stream in streams:
        a, b = logical[stream['source']], logical[stream['target']]
        ya, yb = (rank[a[0]], a[1]), (rank[b[0]], b[1])
        if ya != yb:
            af, bf = ('S', 'N') if ya < yb else ('N', 'S')
        else:
            af, bf = ('E', 'W') if a[2] <= b[2] else ('W', 'E')
        faces[stream['source']]['out'].append(af)
        faces[stream['target']]['in'].append(bf)
    for sides in faces.values():
        both = sides['in'] + sides['out']
        width = max(width, 30 * max(both.count('N'), both.count('S')))
        height = max(height, 30 * max(both.count('W'), both.count('E')))
    for lane in lanes:
        count = lane_rows.get(lane['id'])
        if not count:
            continue
        band_height = count * (height + 110) - 110 + 65
        regions.append(Region('lane-' + lane['id'], -30, y - 45, columns * (width + 130) - 130 + 60,
                              band_height, lane['title'], 22))
        for key, (lane_id, row, col) in logical.items():
            if lane_id == lane['id']:
                positions[key] = {'x': col * (width + 130), 'y': y + row * (height + 110)}
        y += band_height + 30
    return positions, regions, faces, labels, width, height
