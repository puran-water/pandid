"""Give nearly coincident automatic runs a separate native ink corridor."""


def repair_one(fs, lines, spacing, radius, minimum=4):
    from pandid.containment import accessible, route_obstacles
    from pandid.routing import _clamp_projection
    from pandid.routing.astar import CrossingIndex, find_path
    from pandid.routing.visibility import VisibilityGraph, Rect, share_escape_room
    from pandid.routing.captions import foreign_line_plates
    from pandid.routing.crossing_clearance import _overlaps
    from pandid.routing.terminal_clearance import arrow_lead_preserved
    from pandid.render.crossings import crossing_order

    old_ink = _overlaps(lines, minimum)
    if not old_ink:
        return None
    old_exact, old_lost = _overlaps(lines), crossing_order(lines, radius)[1]
    crowded = {}
    for left, points in lines.items():
        for right, peer in lines.items():
            if right <= left:
                continue
            for a,b in zip(points,points[1:]):
                axis = 0 if a[1] == b[1] else 1
                if a[1-axis] != b[1-axis]:
                    continue
                for c,d in zip(peer,peer[1:]):
                    if c[1-axis] != d[1-axis] or abs(a[1-axis]-c[1-axis]) >= minimum:
                        continue
                    low=max(min(a[axis],b[axis]),min(c[axis],d[axis]))
                    high=min(max(a[axis],b[axis]),max(c[axis],d[axis]))
                    if high-low <= minimum:
                        continue
                    for key,track in ((left,c[1-axis]),(right,a[1-axis])):
                        box=(Rect(low,high,track-spacing/2,track+spacing/2) if axis==0 else
                             Rect(track-spacing/2,track+spacing/2,low,high))
                        crowded.setdefault(key,[]).append(box)
    graphs={}
    for key in sorted(crowded,key=lambda k:(-len(crowded[k]),k)):
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
        blocked=[box for box in crowded[key] if not any(box.contains(*p) for p in (start,goal,sp,gp))]
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
        if not arrow_lead_preserved(fs,stream,lines[key],proposal):
            continue
        before,after=list(zip(lines[key],lines[key][1:])),list(zip(proposal,proposal[1:]))
        if any(sum(box.intersects_segment(*a,*b) for a,b in after) >
               sum(box.intersects_segment(*a,*b) for a,b in before)
               for box in route_obstacles(fs,stream)):
            continue
        trial={**lines,key:proposal}
        if _overlaps(trial,minimum) >= old_ink-1e-6 or _overlaps(trial)>old_exact+1e-6:
            continue
        remaining=crossing_order(trial,radius)[1]
        if not remaining <= old_lost:
            continue
        return ((len(remaining),_overlaps(trial,spacing),key),key,proposal,remaining)
    return None
