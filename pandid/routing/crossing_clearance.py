"""Give automatic interior tracks enough room for native crossings and gaps.

Terminal protection and parallel separation can leave a bend just beside a
crossing. Native draw.io gives a whole edge one stacking order, so those local
constraints can form a cycle. Move an interior track only when that strictly
reduces overlaps or unsatisfied crossing constraints, without moving nozzles or authored
waypoints, entering equipment, or adding collinear overlaps.
"""
from functools import lru_cache
from pandid.render.crossings import crossing_order, CrossingPlan


@lru_cache(maxsize=65536)
def _segment_overlaps(a, b, peer_points, clearance):
    """Immutable per-segment contributions, in the original summation order."""
    axis = 0 if a[1] == b[1] else 1
    if a[1-axis] != b[1-axis]:
        return ()
    return tuple(
        max(0, min(max(a[axis], b[axis]), max(c[axis], d[axis]))
            - max(min(a[axis], b[axis]), min(c[axis], d[axis])))
        for c, d in zip(peer_points, peer_points[1:])
        if c[1-axis] == d[1-axis]
        and abs(a[1-axis] - c[1-axis]) <= max(0, clearance - 1e-6)
    )


def _overlaps(lines, clearance=0):
    # Repair changes one automatic track per trial. All other segment pairs
    # recur unchanged; caching their contributions avoids repeating geometric
    # arithmetic for the entire sheet. Keep the original nested summation and
    # exact candidate scores, rather than estimating a trial by a delta.
    paths = [tuple(tuple(point) for point in points) for points in lines.values()]
    total = 0.0
    for i, points in enumerate(paths):
        for a, b in zip(points, points[1:]):
            for peer in paths[i+1:]:
                for value in _segment_overlaps(a, b, peer, clearance):
                    total += value
    return total


class _OverlapPlan:
    """Reuse unaffected contributions when a trial moves one route."""
    def __init__(self, lines, clearance=0):
        self.paths = {k: tuple(tuple(p) for p in v) for k, v in lines.items()}
        self.clearance = clearance
        self.entries, self.chunks = [], []
        self.affected = {k: [] for k in lines}
        keys = list(lines)
        for i, left in enumerate(keys):
            for segment, (a, b) in enumerate(zip(self.paths[left], self.paths[left][1:])):
                for right in keys[i+1:]:
                    index = len(self.entries)
                    self.entries.append((left, right, segment))
                    self.affected[left].append(index)
                    self.affected[right].append(index)
                    self.chunks.append(_segment_overlaps(a, b, self.paths[right], clearance))

    def score(self, key, points):
        from itertools import chain
        path = tuple(tuple(p) for p in points)
        if len(path) != len(self.paths[key]):
            raise ValueError("An overlap trial must retain its waypoint count")
        chunks = self.chunks[:]
        for index in self.affected[key]:
            left, right, segment = self.entries[index]
            apts = path if left == key else self.paths[left]
            bpts = path if right == key else self.paths[right]
            chunks[index] = _segment_overlaps(apts[segment], apts[segment+1], bpts, self.clearance)
        total = 0.0
        for value in chain.from_iterable(chunks):
            total += value
        return total


def repair(fs, *, radius=5, max_passes=None):
    from pandid.portgeom import unit_box
    from pandid.routing.terminal_clearance import anchored_waypoints
    from pandid.render.svg import stream_polyline
    from pandid.routing.visibility import Rect
    from pandid.drawing_regions import captions

    lines = {i: stream_polyline(s) for i, s in enumerate(fs.streams) if s.route}
    # Each pass accepts only ONE track adjustment across the whole sheet.
    # Eight passes therefore cap the number of repairs, not convergence
    # rounds. Dense sheets can have more than eight independent defects even
    # when every remaining move is legal and strictly improves the geometry.
    # Scale the default finite budget with the routed stream count; retain an
    # explicit caller limit and the unchanged fail-closed crossing gate.
    if max_passes is None:
        max_passes = max(8, len(lines))
    lost = crossing_order(lines, radius)[1]
    spacing = max(fs.layout_options.stream_spacing, 2*radius+2)
    if not lost and not _overlaps(lines, spacing):
        return
    boxes = [Rect(x0,x1,y0,y1) for u in fs.units if u.frame is not None
             for x0,y0,x1,y1 in [unit_box(u,u.frame)]]
    boxes += [Rect(c.x,c.x+c.w,c.y,c.y+c.h) for c in captions(fs)]
    for _ in range(max_passes):
        accepted = None
        old_overlaps = _overlaps(lines, spacing)
        old_exact_overlaps = _overlaps(lines)
        overlap_plan = _OverlapPlan(lines, spacing)
        exact_plan = _OverlapPlan(lines)
        crossing_plan = CrossingPlan(lines, radius)
        affected = {v for a,b,_,_ in lost for v in (a,b)}
        for key in sorted(lines):
            if not old_overlaps and None not in affected and key not in affected:
                continue
            stream = fs.streams[key]
            if fs.containments or getattr(fs.layout_options, 'instrument_clearance', 0):
                from pandid.containment import route_obstacles
                boxes = route_obstacles(fs, stream)
            if stream.route.manual:
                continue
            points = lines[key]
            for j in range(1,len(points)-2):
                a,b = points[j:j+2]
                axis = 1 if a[1] == b[1] else 0
                for shift in (-spacing,spacing,-2*spacing,2*spacing,-3*spacing,3*spacing,-4*spacing,4*spacing):
                    proposed = list(points)
                    for k in (j,j+1):
                        point=list(points[k]);point[axis]+=shift;proposed[k]=tuple(point)
                    old = list(zip(points,points[1:]))
                    new = list(zip(proposed,proposed[1:]))
                    changed = [(left,right) for left,right in zip(old,new) if left != right]
                    # No reversal, new zero segment, or new equipment penetration.
                    if any(sum((b[n]-a[n])*(d[n]-c[n]) for n in (0,1)) <= 0
                           for (a,b),(c,d) in changed):
                        continue
                    if any(sum(box.intersects_segment(*a,*b) for _,(a,b) in changed) >
                           sum(box.intersects_segment(*a,*b) for (a,b),_ in changed) for box in boxes):
                        continue
                    overlap = overlap_plan.score(key, proposed)
                    # Most dense-sheet candidates cannot improve either metric.
                    # Reject them before rebuilding the global crossing order;
                    # this keeps the same candidates and tie-breaking score.
                    if (overlap > old_overlaps + 1e-6
                            or exact_plan.score(key, proposed) > old_exact_overlaps + 1e-6
                            or (not lost and overlap >= old_overlaps - 1e-6)):
                        continue
                    remaining=crossing_plan.with_path(key, proposed)[1]
                    # Horizontal and vertical separation are computed from the
                    # same original routes. Moving horizontal tracks can make
                    # two formerly disjoint vertical spans overlap afterwards.
                    # Near-coincident tracks also merge native crossing gaps,
                    # so retain the requested parallel spacing after repair.
                    # Resolve that residual overlap as well as crossing gaps;
                    # neither metric may get worse to improve the other.
                    if (len(remaining) > len(lost)
                            or (len(remaining) == len(lost) and overlap >= old_overlaps - 1e-6)):
                        continue
                    score=(overlap,len(remaining),abs(shift),key,j,shift)
                    if accepted is None or score<accepted[0]:
                        accepted=(score,key,proposed,remaining)
        if accepted is None:
            return  # The export gate retains the unresolved hold.
        _,key,points,lost=accepted
        lines[key]=points
        fs.streams[key].route.waypoints=anchored_waypoints(fs.streams[key], points)
        if not lost and not _overlaps(lines, spacing):
            return
