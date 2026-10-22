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
        from math import fsum
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
        self.totals = [fsum(chunk) for chunk in self.chunks]
        self.total = fsum(self.totals)

    def score(self, key, points):
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
        for chunk in chunks:
            for value in chunk:
                total += value
        return total


def repair(fs, *, radius=5, max_passes=None):
    from pandid.portgeom import unit_box
    from pandid.routing.terminal_clearance import anchored_waypoints
    from pandid.render.native_routes import stream_polyline
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
        max_passes = max(8, 4*len(lines))
    lost = crossing_order(lines, radius)[1]
    spacing = max(fs.layout_options.stream_spacing, 2*radius+2)
    if not lost and not _overlaps(lines, spacing):
        return
    # Resolve the native hold before spending the finite pass budget on
    # optional nearby-track improvements. A dense sheet can otherwise use
    # every pass moving harmless parallel spans while a solvable hold stays.
    from pandid.layout.subsystems import declared
    if lost and hasattr(fs,'drawio_metadata') and declared(fs):
        from pandid.routing.crossing_reroute import repair_one
        for _ in range(len(lost)):
            candidate=repair_one(fs,lines,lost,spacing,radius)
            if candidate is None:
                break
            _,key,points,lost=candidate
            fs.streams[key].route.waypoints=anchored_waypoints(fs.streams[key],points)
            lines[key]=stream_polyline(fs.streams[key])
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
                    if ((not lost and overlap > old_overlaps + 1e-6)
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
                    # A hard crossing hold outranks nearby parallel tracks;
                    # with equal hold counts, spacing must strictly improve.
                    if (len(remaining) > len(lost)
                            or (len(remaining) == len(lost) and overlap >= old_overlaps - 1e-6)):
                        continue
                    score=(len(remaining),overlap,abs(shift),key,j,shift)
                    if accepted is None or score<accepted[0]:
                        accepted=(score,key,proposed,remaining)
        if accepted is None:
            accepted = _detour(fs, lines, lost, spacing, radius)
        if accepted is None and lost:
            from pandid.layout.subsystems import declared
            if hasattr(fs,'drawio_metadata') and declared(fs):
                from pandid.routing.crossing_reroute import repair_one
                accepted = repair_one(fs, lines, lost, spacing, radius)
        if accepted is None:
            return  # The export gate retains the unresolved hold.
        _,key,points,lost=accepted
        lines[key]=points
        fs.streams[key].route.waypoints=anchored_waypoints(fs.streams[key], points)
        if not lost and not _overlaps(lines, spacing):
            return


def _detour(fs, lines, lost, spacing, radius):
    """Add a local dogleg when a short terminal span has no movable track.

    Only unresolved native crossings trigger this fallback. A proposal must
    remove a hold without adding overlaps, touching protected ink or creating
    a self crossing. Endpoints and authored routes remain fixed.
    """
    from pandid.containment import route_obstacles
    old_overlap, old_exact = _overlaps(lines, spacing), _overlaps(lines)
    plan = CrossingPlan(lines, radius)
    accepted = None
    for key, points in lines.items():
        stream = fs.streams[key]
        if stream.route.manual:
            continue
        boxes = route_obstacles(fs, stream)
        for j, (a, b) in enumerate(zip(points, points[1:])):
            axis = 0 if a[1] == b[1] else 1
            other = 1-axis
            if a[other] != b[other]:
                continue
            lo, hi = sorted((a[axis], b[axis]))
            cuts = {p[axis] for _, _, *p in lost
                    if abs(p[other]-a[other]) < 1e-6 and lo < p[axis] < hi}
            for cut in sorted(cuts):
                gap = max(2*radius+2, spacing)
                first, last = max(lo+gap,cut-gap), min(hi-gap,cut+gap)
                if first >= last:
                    continue
                if a[axis] > b[axis]:
                    first, last = last, first
                for shift in (-gap,gap,-2*gap,2*gap,-4*gap,4*gap):
                    corners = []
                    for along, across in ((first,a[other]),(first,a[other]+shift),
                                          (last,a[other]+shift),(last,a[other])):
                        p=list(a);p[axis]=along;p[other]=across;corners.append(tuple(p))
                    proposed = [*points[:j+1], *corners, *points[j+1:]]
                    new = list(zip([a,*corners,b],[*corners,b]))
                    if any(sum(box.intersects_segment(*c,*d) for c,d in new) >
                           box.intersects_segment(*a,*b) for box in boxes):
                        continue
                    self_lines = {n:[c,d] for n,(c,d) in enumerate(zip(proposed,proposed[1:]))}
                    from pandid.render.crossings import _pair_constraints
                    if any(_pair_constraints(tuple(self_lines[l]),tuple(self_lines[r]),1e9,1e9)
                           for l in self_lines for r in self_lines if r > l+1):
                        continue
                    trial = {**lines,key:proposed}
                    overlap = _overlaps(trial,spacing)
                    if _overlaps(trial) > old_exact+1e-6:
                        continue
                    remaining = plan.with_path(key,proposed)[1]
                    if len(remaining) >= len(lost):
                        continue
                    score=(len(remaining),overlap,abs(shift),key,j,shift)
                    if accepted is None or score < accepted[0]:
                        accepted=(score,key,proposed,remaining)
    return accepted
