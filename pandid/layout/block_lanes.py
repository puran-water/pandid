"""Block layout in ordered process roll-up lanes.

The engine receives lane membership and logical order, chooses the grid, and
pins its own blocks. A lane may compact its blocks while remaining uniform
within that lane. Named nozzles and all stream routing remain pandid's.
No coordinates or legacy routes are accepted from a project drawing.
"""
import math
from collections import defaultdict
from dataclasses import dataclass
from pandid.drawing_regions import Region
from pandid.render.furniture import text_width


@dataclass(frozen=True)
class BlockLanePlan:
    """A measured block-lane plan in pandid's nominal CSS-pixel units."""

    positions: dict
    regions: list
    faces: dict
    labels: dict
    sizes: dict

    @property
    def width(self):
        return (max(r.x + r.w for r in self.regions) - min(r.x for r in self.regions)
                if self.regions else 0.0)

    @property
    def height(self):
        return (max(r.y + r.h for r in self.regions) - min(r.y for r in self.regions)
                if self.regions else 0.0)

    def legacy_tuple(self):
        widths = {size[0] for size in self.sizes.values()}
        heights = {size[1] for size in self.sizes.values()}
        if len(widths) > 1 or len(heights) > 1:
            raise ValueError('A per-lane block plan has no uniform legacy block size')
        return (self.positions, self.regions, self.faces, self.labels,
                next(iter(widths), 0.0), next(iter(heights), 0.0))


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


def plan_details(blocks, streams, lanes, *, band_width=2100.0,
                 column_gap=130.0, row_gap=110.0, band_gap=10.0):
    """Prefer a smaller envelope when fewer columns also reduce its height.

    Nozzle counts can enlarge the full-size block. Filling every available column
    may therefore cost more width AND height than an arrangement with fewer
    columns and the same row count. Retain the existing plan unless an
    alternative improves its area without increasing either extent. Explicit
    column/row reservations and logical order still go through the same planner.
    """
    counts = defaultdict(int)
    for row in blocks:
        counts[row['lane']] += 1
    if not isinstance(band_width, (int, float)) or not math.isfinite(band_width) or band_width <= 0:
        raise ValueError('BFD lane band_width must be positive and finite')
    if not blocks:
        return BlockLanePlan({}, [], {}, {}, {})
    # First put every lane on one row. That establishes its port-driven and
    # label-driven size before the paper width decides its own column count.
    provisional_columns = {lane_id: max(1, count) for lane_id, count in counts.items()}
    provisional = _plan_details(
        blocks, streams, lanes, provisional_columns, column_gap=column_gap,
        row_gap=row_gap, band_gap=band_gap)
    maximum = {}
    for lane_id, count in counts.items():
        key = next(row['key'] for row in blocks if row['lane'] == lane_id)
        block_width = provisional.sizes[key][0]
        fitting = max(
            1, int((band_width - 60 + column_gap) // (block_width + column_gap)))
        maximum[lane_id] = min(count, fitting)
    baseline = _plan_details(
        blocks, streams, lanes, maximum, column_gap=column_gap,
        row_gap=row_gap, band_gap=band_gap)

    width, height = baseline.width, baseline.height
    best, score = baseline, (width * height, height, width)
    # A lower column count is considered lane by lane. It is accepted only
    # when the whole drawing improves without consuming more of either sheet
    # axis, preserving the dominated-arrangement rule.
    for lane_id, lane_maximum in maximum.items():
        minimum = min(4, lane_maximum)
        for columns in range(minimum, lane_maximum + 1):
            candidate_columns = dict(maximum)
            candidate_columns[lane_id] = columns
            candidate = _plan_details(
                blocks, streams, lanes, candidate_columns,
                column_gap=column_gap, row_gap=row_gap, band_gap=band_gap)
            w, h = candidate.width, candidate.height
            rank = (w * h, h, w)
            if w <= width and h <= height and rank < score:
                best, score = candidate, rank
    return best


def plan(blocks, streams, lanes, *, band_width=2100.0,
         column_gap=130.0, row_gap=110.0, band_gap=10.0):
    """Compatibility tuple for callers that require one uniform block size."""
    return plan_details(blocks, streams, lanes, band_width=band_width,
                        column_gap=column_gap, row_gap=row_gap,
                        band_gap=band_gap).legacy_tuple()


def _plan(blocks, streams, lanes, columns, *, column_gap=130.0,
          row_gap=110.0, band_gap=10.0):
    """Compatibility entrypoint for the former single-column-count planner."""
    return _plan_details(
        blocks, streams, lanes,
        {lane['id']: columns for lane in lanes}, column_gap=column_gap,
        row_gap=row_gap, band_gap=band_gap).legacy_tuple()


def _lane_scale(definition, name):
    value = definition.get(name, 1.0)
    if (isinstance(value, bool) or not isinstance(value, (int, float))
            or not math.isfinite(value) or not 0 < value <= 1):
        raise ValueError(f'BFD lane {name} must be positive, finite and no greater than 1')
    return float(value)


def _plan_details(blocks, streams, lanes, columns, *, column_gap=130.0,
                  row_gap=110.0, band_gap=10.0):
    by_lane = defaultdict(list)
    for row in blocks:
        by_lane[row['lane']].append(row)
    definitions = {r['id']: r for r in lanes}
    if set(by_lane) - set(definitions):
        raise ValueError('BFD lane is absent from the ordered lane vocabulary')
    positions, regions, y = {}, [], 0
    logical = {}
    lane_rows = {}
    for lane in lanes:
        lane_columns = columns.get(lane['id'], 1)
        rows = sorted(by_lane.get(lane['id'], []), key=lambda r: (r.get('order') if r.get('order') is not None else math.inf, r['key']))
        occupied = set()
        for row in sorted(rows, key=lambda r: r.get('column') is None):
            slot = (int(row.get('row') or 0), int(row['column'])) if row.get('column') is not None else None
            if slot is None:
                slot = next((n // lane_columns, n % lane_columns)
                            for n in range(len(rows) + lane_columns * 5)
                            if (n // lane_columns, n % lane_columns) not in occupied)
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
    base_labels = {r['key']: wrap_label(r['label']) for r in blocks}
    width = 280
    height = max(150, max(len(s.splitlines()) for s in base_labels.values()) * 26.4 + 18)
    for sides in faces.values():
        both = sides['in'] + sides['out']
        width = max(width, 30 * max(both.count('N'), both.count('S')))
        height = max(height, 30 * max(both.count('W'), both.count('E')))
    lane_sizes = {}
    labels = {}
    for lane in lanes:
        rows = by_lane.get(lane['id'], [])
        if not rows:
            continue
        lane_width = width * _lane_scale(lane, 'block_width_scale')
        lane_height = height * _lane_scale(lane, 'block_height_scale')
        wrapped = {row['key']: wrap_label(row['label'], width=max(1, lane_width - 28))
                   for row in rows}
        line_width = max(
            (text_width(line, 22) for label in wrapped.values()
             for line in label.splitlines()), default=0)
        lane_width = max(lane_width, line_width + 28)
        label_height = max(
            (len(label.splitlines()) * 26.4 + 18 for label in wrapped.values()),
            default=0)
        lane_height = max(lane_height, label_height)
        for row in rows:
            both = faces[row['key']]['in'] + faces[row['key']]['out']
            lane_width = max(lane_width, 30 * max(both.count('N'), both.count('S')))
            lane_height = max(lane_height, 30 * max(both.count('W'), both.count('E')))
        lane_sizes[lane['id']] = (lane_width, lane_height)
        labels.update(wrapped)
    sizes = {row['key']: lane_sizes[row['lane']] for row in blocks}
    for lane in lanes:
        count = lane_rows.get(lane['id'])
        if not count:
            continue
        lane_width, lane_height = lane_sizes[lane['id']]
        lane_columns = columns.get(lane['id'], 1)
        reserved = max((int(row.get('column') or 0) + 1
                        for row in by_lane[lane['id']]), default=1)
        # An outlying reserved slot widens this visible band, but need not
        # force automatic blocks in another lane to claim empty columns.
        extent_columns = max(lane_columns, reserved)
        band_height = count * (lane_height + row_gap) - row_gap + 65
        # A 22-unit heading occupies 33 units below its four-unit inset.
        # Reserve a full 24-unit north-nozzle arrow lead and four-unit gap
        # below it. Extend the band into its existing inter-lane whitespace;
        # block positions and lane pitch stay fixed, with ten units between
        # adjacent bands. The former 45-unit header left only eight units.
        regions.append(Region('lane-' + lane['id'], -30, y - 65,
                              extent_columns * (lane_width + column_gap) - column_gap + 60,
                              band_height + 20, lane['title'], 22))
        for key, (lane_id, row, col) in logical.items():
            if lane_id == lane['id']:
                positions[key] = {'x': col * (lane_width + column_gap),
                                  'y': y + row * (lane_height + row_gap)}
        y += band_height + 20 + band_gap
    return BlockLanePlan(positions, regions, faces, labels, sizes)
