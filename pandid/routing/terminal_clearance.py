"""Keep a final automatic bend outside the native terminal arrow's footprint."""
from pandid.portgeom import unit_box
from pandid.routing.visibility import Rect


def anchored_waypoints(stream, points):
    """Return a repaired drawn line to the router's anchor coordinates.

    Repair measures the line between its drawn nozzles, which may sit inside
    the equipment box. The route itself starts and ends on that box; keeping
    the nozzle points here would change what every later routing pass reads.
    The renderer adds the nozzle-to-anchor stubs back when it draws the line.
    """
    # The incoming route already owns those anchors. Keeping them also leaves
    # clearance repair a geometry operation, without asking it to resolve ports.
    waypoints = stream.route.waypoints
    return [waypoints[0], *points[1:-1], waypoints[-1]]


def square_micro_jogs(fs):
    """Remove subpixel terminal jogs that mxGraph coalesces into diagonals.

    The nozzle stays exact. Only an automatic adjacent track within one
    drawing pixel is straightened; authored waypoints remain untouched.
    """
    for stream in fs.streams:
        if not stream.route or stream.route.manual:
            continue
        points = list(stream.route.waypoints)
        for reverse in (False, True):
            if reverse:
                points.reverse()
            if len(points) == 3:
                a, b, c = points
                axis = 0 if a[1] == b[1] else 1
                other = 1 - axis
                span = c[other] - a[other]
                if (a[other] == b[other] and b[axis] == c[axis]
                        and 0 < abs(a[axis] - b[axis]) <= 1 and abs(span) > 48):
                    # An L whose first leg is subpixel cannot be flattened
                    # without moving a nozzle. Give it a full dogleg instead;
                    # Desktop otherwise drops the elbow and draws a diagonal.
                    far = a[axis] + (24 if b[axis] > a[axis] else -24)
                    near = c[other] - (24 if span > 0 else -24)
                    first, middle, last = list(a), list(a), list(c)
                    first[axis] = middle[axis] = far
                    middle[other] = last[other] = near
                    proposed = [a, tuple(first), tuple(middle), tuple(last), c]
                    source, target = ((stream.dest.owner, stream.source.owner) if reverse
                                      else (stream.source.owner, stream.dest.owner))
                    def hits(unit, path):
                        x0, y0, x1, y1 = unit_box(unit, unit.frame)
                        box = Rect(x0, x1, y0, y1)
                        return sum(box.intersects_segment(*p, *q)
                                   for i, (p, q) in enumerate(zip(path, path[1:]))
                                   if not (unit is source and i == 0)
                                   and not (unit is target and i == len(path)-2))
                    if not any(hits(u, proposed) > hits(u, points) for u in fs.units if u.frame):
                        points = proposed
            if len(points) >= 4:
                a, b, c = points[:3]
                axis = 0 if a[1] == b[1] else 1
                other = 1-axis
                if (a[other] == b[other] and b[axis] == c[axis]
                        and 0 < abs(a[axis]-b[axis]) <= 1):
                    shifted = list(c); shifted[axis] = a[axis]
                    points = [a, tuple(shifted), *points[3:]]
            if reverse:
                points.reverse()
        stream.route.waypoints = points


def protect(fs):
    from pandid.render.svg import draws_arrowheads, stream_polyline
    from pandid.render.symbols import default_registry, wears_arrowhead
    if not draws_arrowheads(getattr(fs, '_drawn_as', None)):
        return
    boxes = [Rect(x0,x1,y0,y1) for x0,y0,x1,y1 in (unit_box(u,u.frame) for u in fs.units)]
    from pandid.drawing_regions import captions
    boxes += [Rect(c.x,c.x+c.w,c.y,c.y+c.h) for c in captions(fs)]
    for stream in fs.streams:
        if not stream.route or stream.route.manual or not wears_arrowhead(stream,default_registry):
            continue
        if fs.containments or getattr(fs.layout_options, 'instrument_clearance', 0):
            from pandid.containment import route_obstacles
            boxes = route_obstacles(fs, stream)
        points = stream_polyline(stream)
        if len(points) < 4:
            continue
        anchor, corner, neighbour = points[-1], points[-2], points[-3]
        axis = 0 if abs(anchor[1]-corner[1]) < .01 else 1
        distance = abs(anchor[axis]-corner[axis])
        if distance >= 24 or distance < 1e-6 or abs(corner[axis]-neighbour[axis]) > .01:
            continue
        track = anchor[axis] + (24 if corner[axis] > anchor[axis] else -24)
        proposed = list(points)
        for n in (-2,-3):
            moved = list(proposed[n]); moved[axis] = track; proposed[n] = tuple(moved)
        old, new = list(zip(points,points[1:])), list(zip(proposed,proposed[1:]))
        changed = [(a,b) for a,b in zip(old,new) if a != b]
        if any(sum(box.intersects_segment(*a,*b) for _,(a,b) in changed) >
               sum(box.intersects_segment(*a,*b) for (a,b),_ in changed) for box in boxes):
            continue
        stream.route.waypoints = anchored_waypoints(stream, proposed)


def short_terminal_stubs(fs, stream, points, minimum):
    """The ends of ``points`` that turn back along their own block nearer its face than ``minimum``.

    ``0`` for the source end, ``-1`` for the destination. A lead out of (into)
    a block runs square off its face; the first turn after it runs parallel
    to that face. Where the corner stands nearer the face than ``minimum``
    and the turned leg passes back over the block, the line reads as the
    block's own outline, and a lead under Desktop's 1.5-unit floor is dropped
    on export, so the run leaves on a slant. A turn that heads straight off
    the block's corner passes over nothing and is not counted.
    """
    from pandid.portgeom import unit_box

    found = []
    for end, unit in ((0, stream.source.owner), (-1, stream.dest.owner)):
        if unit is None or unit.frame is None or len(points) < 3:
            continue
        anchor, corner, turned = (points[0], points[1], points[2]) if end == 0 else \
            (points[-1], points[-2], points[-3])
        axis = 0 if abs(anchor[1] - corner[1]) <= 1e-6 < abs(anchor[0] - corner[0]) else \
            1 if abs(anchor[0] - corner[0]) <= 1e-6 < abs(anchor[1] - corner[1]) else None
        if axis is None:
            continue
        along = 1 - axis
        box = unit_box(unit, unit.frame)
        low, high = box[axis], box[axis + 2]
        stand_off = max(low - corner[axis], corner[axis] - high, 0.0)
        span_low, span_high = sorted((corner[along], turned[along]))
        over = min(span_high, box[along + 2]) - max(span_low, box[along])
        if stand_off < minimum - 1e-6 and over > 1e-6:
            found.append(end)
    return found


def hold_terminal_stubs(fs, *, minimum, preferred=None, unplaced=None, spacing=None, radius=5):
    """Stand each automatic route's first turn at least ``minimum`` off the block it leaves or enters.

    A later repair can slide a route's first track up against its own end
    block (a crossing move left one 0.9 units over the face it left), where
    nothing else looks: a block's outline is checked only against the runs of
    streams it does not end. Each such end (:func:`short_terminal_stubs`) has
    its track moved out to ``preferred`` from the face, else ``minimum``, the
    two corners together the way crossing repair moves a track. Where the new
    track comes within ``spacing`` of a parallel interior run beyond it, that
    run steps on by the spacing, in the same direction, and so on, none more
    than four spacings past the stub. The set is taken only if every leg keeps
    its direction, nothing enters a unit or caption, no parallel overlap or
    unresolved crossing gap is added, no full arrow lead is shortened, no end
    is left short that was not, and, with ``unplaced`` (a callable counting the
    sheet's stream numbers with no position), no more numbers are unplaced.
    Where none is taken the route stays and the export gates decide. The
    caller passes the bounds; nothing here infers them. Returns the names of
    the streams moved, once per move.
    """
    from pandid.drawing_regions import captions
    from pandid.portgeom import unit_box
    from pandid.render.crossings import crossing_order
    from pandid.render.svg import stream_polyline
    from pandid.routing.crossing_clearance import _overlaps

    preferred = minimum if preferred is None else preferred
    spacing = max(fs.layout_options.stream_spacing, 2 * radius + 2) if spacing is None else spacing
    lines = {i: stream_polyline(s) for i, s in enumerate(fs.streams) if s.route}
    boxes = [Rect(x0, x1, y0, y1) for u in fs.units if u.frame is not None
             for x0, y0, x1, y1 in [unit_box(u, u.frame)]]
    boxes += [Rect(c.x, c.x + c.w, c.y, c.y + c.h) for c in captions(fs)]

    def heading(a, b):
        return tuple(0 if abs(b[k] - a[k]) <= 1e-6 else (1 if b[k] > a[k] else -1) for k in (0, 1))

    def obstacles(key):
        if fs.containments or getattr(fs.layout_options, 'instrument_clearance', 0):
            from pandid.containment import route_obstacles
            return route_obstacles(fs, fs.streams[key])
        return boxes

    def lead(route):
        return abs(route[-1][0] - route[-2][0]) + abs(route[-1][1] - route[-2][1])

    def shifted(route, index, axis, track):
        proposal = list(route)
        for at in (index, index + 1):
            point = list(proposal[at])
            point[axis] = track
            proposal[at] = tuple(point)
        return proposal

    def pushed(trial, key, index, axis, sense, ceiling):
        """``trial`` with every interior run crowding ``key``'s moved run stepped on, or None."""
        along = 1 - axis
        queue, settled = [(key, index, trial[key][index][axis])], 0
        while queue:
            mover, at, held = queue.pop(0)
            settled += 1
            if settled > 4 * len(trial):
                return None
            low, high = sorted((trial[mover][at][along], trial[mover][at + 1][along]))
            for other in sorted(trial):
                if other == mover:
                    continue
                for j, (c, d) in enumerate(zip(trial[other], trial[other][1:])):
                    if not abs(c[axis] - d[axis]) <= 1e-6 < abs(c[along] - d[along]):
                        continue  # not parallel
                    if min(high, max(c[along], d[along])) - max(low, min(c[along], d[along])) <= 1e-6:
                        continue  # not beside the moved run
                    if not 0 <= sense * (c[axis] - held) < spacing - 1e-6:
                        continue  # behind it, or a spacing clear
                    target = held + sense * spacing
                    if (fs.streams[other].route.manual or not 0 < j < len(trial[other]) - 2
                            or sense * (target - ceiling) > 1e-6):
                        return None  # authored, a nozzle's own leg, or out past the corridor
                    trial[other] = shifted(trial[other], j, axis, target)
                    queue.append((other, j, target))
        return trial

    def taken(trial, key, end, before):
        changed = sorted(other for other in trial if trial[other] != lines[other])
        for other in changed:
            old, new = lines[other], trial[other]
            stream = fs.streams[other]
            if [heading(a, b) for a, b in zip(new, new[1:])] != [heading(a, b) for a, b in zip(old, old[1:])]:
                return False  # a leg turned round or shrank to nothing
            if any(sum(box.intersects_segment(*a, *b) for a, b in zip(new, new[1:])) >
                   sum(box.intersects_segment(*a, *b) for a, b in zip(old, old[1:])) for box in obstacles(other)):
                return False  # into a unit or a caption
            if lead(old) >= 24 > lead(new):
                return False  # a full arrow lead shortened
            short_old = short_terminal_stubs(fs, stream, old, minimum)
            short_new = short_terminal_stubs(fs, stream, new, minimum)
            if len(short_new) > len(short_old) or (other == key and (end in short_new
                                                                     or len(short_new) >= len(short_old))):
                return False
        if (_overlaps(trial, spacing) > before[0] + 1e-6 or _overlaps(trial) > before[1] + 1e-6
                or len(crossing_order(trial, radius)[1]) > before[2]):
            return False
        if unplaced is not None:
            saved = {other: fs.streams[other].route.waypoints for other in changed}
            for other in changed:
                fs.streams[other].route.waypoints = anchored_waypoints(fs.streams[other], trial[other])
            try:
                if unplaced(fs) > before[3]:
                    return False
            finally:
                for other, waypoints in saved.items():
                    fs.streams[other].route.waypoints = waypoints
        return True

    moved = []
    for key in sorted(lines):
        stream = fs.streams[key]
        if stream.route.manual:
            continue
        for end in (0, -1):
            points = lines[key]
            if end not in short_terminal_stubs(fs, stream, points, minimum) or len(points) < 4:
                continue  # clear, or an L whose corner the far nozzle holds
            unit = stream.source.owner if end == 0 else stream.dest.owner
            box = unit_box(unit, unit.frame)
            anchor, corner = (points[0], points[1]) if end == 0 else (points[-1], points[-2])
            index = 1 if end == 0 else len(points) - 3
            axis = 0 if abs(anchor[1] - corner[1]) <= 1e-6 else 1
            sense = 1 if corner[axis] > anchor[axis] else -1
            face = box[axis + 2] if sense > 0 else box[axis]
            before = (_overlaps(lines, spacing), _overlaps(lines), len(crossing_order(lines, radius)[1]),
                      unplaced(fs) if unplaced is not None else 0)
            for track in dict.fromkeys(face + sense * d for d in (preferred, minimum)):
                trial = {**lines, key: shifted(points, index, axis, track)}
                accepted = trial if taken(trial, key, end, before) else None
                if accepted is None:
                    trial = pushed(dict(trial), key, index, axis, sense, track + sense * 4 * spacing)
                    accepted = trial if trial is not None and taken(trial, key, end, before) else None
                if accepted is None:
                    continue
                for other in sorted(accepted):
                    if accepted[other] != lines[other]:
                        lines[other] = accepted[other]
                        fs.streams[other].route.waypoints = anchored_waypoints(fs.streams[other], accepted[other])
                        moved.append(fs.streams[other].name)
                break
    return moved


def square_interior_micro_jogs(fs):
    """Collapse tiny internal steps that Desktop otherwise exports diagonally.

    Only automatic tracks move, by at most one drawing unit. A step can be
    flattened onto either neighbouring track, provided endpoints, direction,
    equipment/caption clearance, parallel spacing and crossing gaps survive.
    Each accepted move removes points, so this pass terminates without a cap.
    """
    from pandid.render.svg import stream_polyline
    from pandid.render.crossings import crossing_order
    from pandid.routing.crossing_clearance import _overlaps
    from pandid.drawing_regions import captions

    lines = {i: stream_polyline(s) for i, s in enumerate(fs.streams) if s.route}
    boxes = [Rect(x0, x1, y0, y1) for u in fs.units if u.frame is not None
             for x0, y0, x1, y1 in [unit_box(u, u.frame)]]
    boxes += [Rect(c.x, c.x+c.w, c.y, c.y+c.h) for c in captions(fs)]
    spacing = max(fs.layout_options.stream_spacing, 12)
    for key in lines:
        stream = fs.streams[key]
        if stream.route.manual:
            continue
        if fs.containments or getattr(fs.layout_options, 'instrument_clearance', 0):
            from pandid.containment import route_obstacles
            obstacles = route_obstacles(fs, stream)
        else:
            obstacles = boxes
        while True:
            points = lines[key]
            accepted = None
            for j in range(1, len(points)-2):
                a, b = points[j:j+2]
                axis = 1 if a[0] == b[0] else 0
                other = 1-axis
                if (a[other] != b[other] or not 0 < abs(a[axis]-b[axis]) <= 1
                        or points[j-1][axis] != a[axis] or points[j+2][axis] != b[axis]):
                    continue
                for indices, at in (((j-1, j), b[axis]), ((j+1, j+2), a[axis])):
                    if min(indices) == 0 or max(indices) == len(points)-1:
                        continue
                    proposed = list(points)
                    for index in indices:
                        point = list(proposed[index]); point[axis] = at; proposed[index] = tuple(point)
                    old, new = list(zip(points, points[1:])), list(zip(proposed, proposed[1:]))
                    if any(n != j and sum((b[k]-a[k])*(d[k]-c[k]) for k in (0, 1)) <= 0
                           for n, ((a, b), (c, d)) in enumerate(zip(old, new))):
                        continue
                    # Do not shorten an existing full terminal-arrow lead.
                    distance = lambda a, b: abs(a[0]-b[0]) + abs(a[1]-b[1])
                    if distance(*old[-1]) >= 24 and distance(*new[-1]) < 24:
                        continue
                    simplified = []
                    for point in proposed:
                        if simplified and point == simplified[-1]:
                            continue
                        while len(simplified) >= 2 and (
                            simplified[-2][0] == simplified[-1][0] == point[0]
                            or simplified[-2][1] == simplified[-1][1] == point[1]
                        ):
                            simplified.pop()
                        simplified.append(point)
                    segments = list(zip(simplified, simplified[1:]))
                    if any(sum(box.intersects_segment(*a, *b) for a, b in segments) >
                           sum(box.intersects_segment(*a, *b) for a, b in old) for box in obstacles):
                        continue
                    trial = {**lines, key: simplified}
                    if (_overlaps(trial, spacing) > _overlaps(lines, spacing) + 1e-6
                            or _overlaps(trial) > _overlaps(lines) + 1e-6
                            or not crossing_order(trial, 5)[1] <= crossing_order(lines, 5)[1]):
                        continue
                    accepted = simplified
                    break
                if accepted is not None:
                    break
            if accepted is None:
                break
            lines[key] = accepted
            # Endpoint-adjacent micro steps are eligible on their interior
            # side only. The index guard above and this helper both preserve
            # the original nozzle anchors.
            stream.route.waypoints = anchored_waypoints(stream, accepted)
