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
            for j in range(2, len(points)-3):
                a, b = points[j:j+2]
                axis = 1 if a[0] == b[0] else 0
                other = 1-axis
                if (a[other] != b[other] or not 0 < abs(a[axis]-b[axis]) <= 1
                        or points[j-1][axis] != a[axis] or points[j+2][axis] != b[axis]):
                    continue
                for indices, at in (((j-1, j), b[axis]), ((j+1, j+2), a[axis])):
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
            # Every repair write goes through the anchoring helper, including
            # this one. Today it is a no-op here: the loop runs
            # `range(2, len(points)-3)` and moves `j-1, j` or `j+1, j+2`, so the
            # lowest reachable index is 1 and the highest is len-2, and the
            # anchors are preserved by construction. But that invariant lives in
            # two numbers inside a range expression and nothing names it, and
            # this range is the first thing anyone tuning jog aggressiveness
            # would widen. A route that starts a unit off its nozzle still
            # routes, still exports and still looks right on the sheet, which is
            # the worst class of defect here. Stating the invariant costs
            # nothing and makes all three repair writes identical.
            stream.route.waypoints = anchored_waypoints(stream, accepted)
