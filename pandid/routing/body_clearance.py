"""Keep final automatic tracks off equipment after parallel-track separation.

The router's separation pass can shift a previously clear track into a nearby
balloon. This bounded repair changes only automatic interior tracks, preserves
nozzles and manual waypoints, and accepts only fewer body intersections without
new parallel overlaps. Unresolved cases remain publication holds.
"""

from pandid.portgeom import COMPASS, port_anchor, unit_box
from pandid.routing.crossing_clearance import _overlaps
from pandid.routing.visibility import Rect


def repair(fs, *, max_passes=8):
    lines = {i: list(s.route.waypoints) for i, s in enumerate(fs.streams) if s.route}
    bodies = {
        u: Rect(x0, x1, y0, y1)
        for u in fs.units
        if u.frame is not None
        for x0, y0, x1, y1 in [unit_box(u, u.frame)]
    }

    def hits(key, points):
        stream = fs.streams[key]
        from pandid.containment import accessible
        allowed = accessible(fs, stream)
        endpoints = {stream.source.owner, stream.dest.owner}
        return {
            u
            for u, box in bodies.items()
            if u not in endpoints and u.name not in allowed
            and any(box.intersects_segment(*a, *b) for a, b in zip(points, points[1:]))
        }

    spacing = max(4, fs.layout_options.stream_spacing)
    for _ in range(max_passes):
        changed = False
        for key, points in list(lines.items()):
            stream = fs.streams[key]
            if stream.route.manual:
                continue
            before = hits(key, points)
            if not before:
                continue
            old_overlap = _overlaps(lines)
            source_normal = COMPASS[
                port_anchor(stream.source.owner, stream.source.owner.frame, stream.source.name)[2]
            ]
            dest_normal = COMPASS[
                port_anchor(stream.dest.owner, stream.dest.owner.frame, stream.dest.name)[2]
            ]
            candidates = []
            for j in range(1, len(points) - 2):
                a, b = points[j : j + 2]
                axis = 0 if a[0] == b[0] else 1
                for unit in fs.units:
                    if unit not in before:
                        continue
                    box = bodies[unit]
                    if not box.intersects_segment(*a, *b):
                        continue
                    tracks = [
                        (priority, track)
                        for priority, margin in enumerate(dict.fromkeys((spacing, spacing / 2, 4)))
                        for track in (
                            (box.x_min - margin, box.x_max + margin)
                            if axis == 0
                            else (box.y_min - margin, box.y_max + margin)
                        )
                    ]
                    for priority, track in tracks:
                        proposal = list(points)
                        for k in (j, j + 1):
                            point = list(points[k])
                            point[axis] = track
                            proposal[k] = tuple(point)
                        # Interior legs keep their direction. Terminal legs
                        # follow the actual nozzle normal: separation may have
                        # overshot a goal and made its previous approach wrong.
                        if any(
                            sum((b[n] - a[n]) * (d[n] - c[n]) for n in (0, 1)) <= 0
                            for (a, b), (c, d) in zip(
                                zip(points[1:-2], points[2:-1]), zip(proposal[1:-2], proposal[2:-1])
                            )
                        ):
                            continue
                        if (
                            sum(
                                (proposal[1][n] - proposal[0][n]) * source_normal[n] for n in (0, 1)
                            )
                            <= 0
                            or sum(
                                (proposal[-1][n] - proposal[-2][n]) * (-dest_normal[n])
                                for n in (0, 1)
                            )
                            <= 0
                        ):
                            continue
                        after = hits(key, proposal)
                        if (
                            not after < before
                            or _overlaps({**lines, key: proposal}) > old_overlap + 1e-6
                        ):
                            continue
                        candidates.append(
                            (len(after), priority, abs(track - points[j][axis]), j, track, proposal)
                        )
            if candidates:
                proposal = min(candidates, key=lambda row: row[:5])[-1]
                lines[key] = proposal
                stream.route.waypoints = proposal
                changed = True
        if not changed:
            return
