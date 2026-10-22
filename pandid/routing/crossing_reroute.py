"""Search a complete alternate path when a local crossing jog cannot move.

The native crossing calculation remains the acceptance test. This fallback
changes an automatic route only after it reduces the held crossing count,
without adding equipment penetrations or collinear overlaps.
"""
from collections import Counter


def repair_one(fs, lines, lost, spacing, radius):
    from pandid.containment import accessible, route_obstacles
    from pandid.routing import _clamp_projection
    from pandid.routing.astar import CrossingIndex, find_path
    from pandid.routing.visibility import VisibilityGraph, Rect, share_escape_room
    from pandid.routing.captions import foreign_line_plates
    from pandid.routing.crossing_clearance import _overlaps
    from pandid.render.crossings import CrossingPlan
    points_by_key={}
    for a,b,x,y in lost:
        keys=(a,b) if a is not None else [k for k,path in lines.items() if any(
            (abs(p[0]-q[0])<1e-6 and abs(x-p[0])<1e-6 and min(p[1],q[1])<y<max(p[1],q[1]))
            or (abs(p[1]-q[1])<1e-6 and abs(y-p[1])<1e-6 and min(p[0],q[0])<x<max(p[0],q[0]))
            for p,q in zip(path,path[1:]))]
        for key in keys:
            points_by_key.setdefault(key,set()).add((x,y))
    counts={k:len(v) for k,v in points_by_key.items()}
    old_overlap,old_exact=_overlaps(lines,spacing),_overlaps(lines)
    plan=CrossingPlan(lines,radius)
    graphs={}
    for key in sorted(counts,key=lambda k:(-counts[k],k)):
        stream=fs.streams[key]
        if stream.route.manual:
            continue
        allowed=accessible(fs,stream)
        if allowed not in graphs:
            graphs[allowed]=VisibilityGraph(fs,accessible=allowed)
        graph=graphs[allowed]
        source=(stream.source.owner.name,stream.source.name)
        target=(stream.dest.owner.name,stream.dest.name)
        start,goal=graph.port_anchors[source],graph.port_anchors[target]
        sd,gd=graph.port_dirs[source],graph.port_dirs[target]
        sp,gp=graph.port_projs[source],graph.port_projs[target]
        sp=_clamp_projection(start,sp,sd,gp,graph.nodes)
        gp=_clamp_projection(goal,gp,gd,sp,graph.nodes)
        sp,gp=share_escape_room(start,sd,sp,goal,gd,gp,graph.obstacles)
        blocked=[]
        for x,y in sorted(points_by_key[key]):
            box=Rect(x-spacing,x+spacing,y-spacing,y+spacing)
            if not any(box.contains(*p) for p in (start,goal,sp,gp)):
                blocked.append(box)
        if not blocked:
            continue
        index=CrossingIndex()
        for other,path in lines.items():
            if other!=key:
                index.record(path)
        path=find_path(graph,sp,gp,sd,gd,{},stream.is_recycle,index,
            forbidden=[*foreign_line_plates(fs,stream),*blocked],overlap_weight=100.)
        if not path:
            continue
        proposal=[]
        for point in [start,*path,goal]:
            if proposal and point==proposal[-1]:
                continue
            while len(proposal)>1 and (proposal[-2][0]==proposal[-1][0]==point[0]
                                      or proposal[-2][1]==proposal[-1][1]==point[1]):
                proposal.pop()
            proposal.append(point)
        before,after=list(zip(lines[key],lines[key][1:])),list(zip(proposal,proposal[1:]))
        from pandid.routing.terminal_clearance import arrow_lead_preserved
        if not arrow_lead_preserved(fs,stream,lines[key],proposal):
            continue
        if any(sum(box.intersects_segment(*a,*b) for a,b in after)>
               sum(box.intersects_segment(*a,*b) for a,b in before)
               for box in route_obstacles(fs,stream)):
            continue
        trial={**lines,key:proposal}
        overlap=_overlaps(trial,spacing)
        # Native crossing failures outrank nearby parallel tracks. Requiring
        # both soft spacing and hard crossing counts to improve at once can
        # trap a route whose only clear escape temporarily uses a closer
        # parallel lane. Exact coincident ink remains forbidden, and the
        # following local pass improves spacing without reintroducing holds.
        if _overlaps(trial)>old_exact+1e-6:
            continue
        remaining=plan.with_path(key,proposal)[1]
        if len(remaining)<len(lost):
            return ((len(remaining),overlap,key),key,proposal,remaining)
    return None
