"""Keep a final automatic bend outside the native terminal arrow's footprint."""
from pandid.portgeom import unit_box
from pandid.routing.visibility import Rect


def square_micro_jogs(fs):
    """Remove subpixel terminal jogs that mxGraph coalesces into diagonals.

    The nozzle stays exact. Only an automatic adjacent track within one
    drawing pixel is straightened; authored waypoints remain untouched.
    """
    from pandid.render.svg import stream_polyline
    for stream in fs.streams:
        if not stream.route or stream.route.manual:
            continue
        points = stream_polyline(stream)
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
        stream.route.waypoints = proposed
