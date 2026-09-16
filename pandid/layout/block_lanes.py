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
    """Prefer a smaller envelope when fewer columns also reduce its height.

    Nozzle counts can enlarge every uniform block. Filling all eight columns
    may therefore cost more width AND height than an arrangement with fewer
    columns and the same row count. Retain the existing plan unless an
    alternative improves its area without increasing either extent. Explicit
    column/row reservations and logical order still go through the same planner.
    """
    counts = defaultdict(int)
    for row in blocks:
        counts[row['lane']] += 1
    minimum = 4
    maximum = max(minimum, min(8, max(counts.values())))
    reserved = max((int(r.get('column') or 0) + 1 for r in blocks), default=1)
    baseline = _plan(blocks, streams, lanes, max(maximum, reserved))

    def extent(result):
        regions = result[1]
        return (max(r.x + r.w for r in regions) - min(r.x for r in regions),
                max(r.y + r.h for r in regions) - min(r.y for r in regions))

    width, height = extent(baseline)
    best, score = baseline, (width * height, height, width)
    for columns in range(minimum, maximum + 1):
        candidate = _plan(blocks, streams, lanes, columns)
        w, h = extent(candidate)
        rank = (w * h, h, w)
        if w <= width and h <= height and rank < score:
            best, score = candidate, rank
    return best


def _plan(blocks, streams, lanes, columns):
    by_lane = defaultdict(list)
    for row in blocks:
        by_lane[row['lane']].append(row)
    definitions = {r['id']: r for r in lanes}
    if set(by_lane) - set(definitions):
        raise ValueError('BFD lane is absent from the ordered lane vocabulary')
    # An outlying reserved slot widens the visible bands, but need not force
    # every other lane's automatic blocks to fill that many columns. Keep the
    # pin and the band around it while evaluating a more compact auto grid.
    extent_columns = max(columns, max((int(r.get('column') or 0) + 1 for r in blocks), default=1))
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
        # A 22-unit heading occupies 33 units below its four-unit inset.
        # Reserve a full 24-unit north-nozzle arrow lead and four-unit gap
        # below it. Extend the band into its existing inter-lane whitespace;
        # block positions and lane pitch stay fixed, with ten units between
        # adjacent bands. The former 45-unit header left only eight units.
        regions.append(Region('lane-' + lane['id'], -30, y - 65, extent_columns * (width + 130) - 130 + 60,
                              band_height + 20, lane['title'], 22))
        for key, (lane_id, row, col) in logical.items():
            if lane_id == lane['id']:
                positions[key] = {'x': col * (width + 130), 'y': y + row * (height + 110)}
        y += band_height + 30
    return positions, regions, faces, labels, width, height
