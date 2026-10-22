"""Reroute automatic paths that a track-separation pass pushed into equipment.

Moving one interior track cannot repair a short route, or a path requiring an
extra bend around a nearby header. Reuse the native visibility graph for those
cases; keep nozzles, manual paths and every downstream clearance gate intact.
"""


def repair(fs):
    from pandid.layout.subsystems import declared
    if not declared(fs):
        return
    from pandid.containment import accessible
    from pandid.portgeom import unit_box
    from pandid.routing import _clamp_projection
    from pandid.routing.astar import CrossingIndex, find_path
    from pandid.routing.visibility import Rect, VisibilityGraph, share_escape_room
    from pandid.routing.captions import equipment_tags
    from pandid.routing.captions import foreign_line_plates
    from pandid.routing.crossing_clearance import _overlaps
    from pandid.streams import Route
    from pandid.render.native_routes import NATIVE_BODY_MARGIN as pad

    bodies = {u: Rect(x0-pad, x1+pad, y0-pad, y1+pad) for u in fs.units if u.frame is not None
              for x0, y0, x1, y1 in [unit_box(u, u.frame)]}
    tags = equipment_tags(fs,settled=True)
    fs._resolved_tag_boxes=tags
    from pandid.render.nameplates import fixed_boxes
    cards = [Rect(x0,x1,y0,y1) for x0,y0,x1,y1 in fixed_boxes(fs)]
    lines = {i: list(s.route.waypoints) for i, s in enumerate(fs.streams) if s.route}

    def hits(stream, points):
        allowed = accessible(fs, stream)
        result = set()
        for index,box in enumerate(cards):
            if any(box.intersects_segment(*a,*b) for a,b in zip(points,points[1:])):
                result.add(('equipment-data',index))
        for unit, box in bodies.items():
            if unit.name in allowed:
                continue
            if any(box.intersects_segment(*a, *b) for j, (a, b) in enumerate(zip(points, points[1:]))
                   if not (unit is stream.source.owner and j == 0)
                   and not (unit is stream.dest.owner and j == len(points)-2)):
                result.add(('body', unit.name))
        for unit, box in tags.items():
            if any(box.intersects_segment(*a, *b) for a, b in zip(points, points[1:])):
                result.add(('tag', unit.name))
        for index,box in enumerate(foreign_line_plates(fs,stream)):
            if any(box.intersects_segment(*a,*b) for a,b in zip(points,points[1:])):
                result.add(('line-caption',index))
        return result

    graphs = {}
    trace=getattr(fs,'_obstacle_repair_trace',[])
    fs._obstacle_repair_trace=trace
    for key, points in list(lines.items()):
        stream = fs.streams[key]
        before = hits(stream, points)
        if stream.route.manual or not before:
            continue
        allowed = accessible(fs, stream)
        if allowed not in graphs:
            graphs[allowed] = VisibilityGraph(fs, accessible=allowed)
        graph = graphs[allowed]
        source = (stream.source.owner.name, stream.source.name)
        target = (stream.dest.owner.name, stream.dest.name)
        start, goal = graph.port_anchors[source], graph.port_anchors[target]
        sd, gd = graph.port_dirs[source], graph.port_dirs[target]
        sp, gp = graph.port_projs[source], graph.port_projs[target]
        sp = _clamp_projection(start, sp, sd, gp, graph.nodes)
        gp = _clamp_projection(goal, gp, gd, sp, graph.nodes)
        sp, gp = share_escape_room(start, sd, sp, goal, gd, gp, graph.obstacles)
        index = CrossingIndex()
        for other, path in lines.items():
            if other != key:
                index.record(path)
        path = find_path(graph, sp, gp, sd, gd, {}, stream.is_recycle, index,
                         forbidden=foreign_line_plates(fs,stream),overlap_weight=100.)
        if not path:
            trace.append({'stream':stream.name,'status':'no_path','hits':sorted(before)})
            continue
        proposal = [start] + path + [goal]
        after = hits(stream, proposal)
        def severity(hits):
            return (sum(kind in {'body','equipment-data'} for kind,_ in hits),
                    sum(kind not in {'body','equipment-data'} for kind,_ in hits))
        # A temporary shared track is repairable by the following separation
        # pass; it must not veto an escape from equipment or lettering.
        # Accept only a strict reduction in hard geometric defects. The
        # native body, overlap, crossing and lettering gates remain unchanged.
        if severity(after) >= severity(before):
            trace.append({'stream':stream.name,'status':'no_improvement','before':sorted(before),'after':sorted(after)})
            continue
        simplified = []
        for point in proposal:
            if simplified and simplified[-1] == point:
                continue
            while len(simplified) > 1 and (
                    simplified[-2][0] == simplified[-1][0] == point[0]
                    or simplified[-2][1] == simplified[-1][1] == point[1]):
                simplified.pop()
            simplified.append(point)
        stream.route = Route(waypoints=simplified)
        lines[key] = simplified
        trace.append({'stream':stream.name,'status':'repaired','before':sorted(before),'after':sorted(after)})
