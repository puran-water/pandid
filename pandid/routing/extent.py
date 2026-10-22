"""Fit automatic escape tracks to a renderer's measured fixed paper band."""


def fit(fs, *, width, height, measure):
    """Reduce overflow without moving a nozzle, symbol, card or manual path.

    Bounds are measured, never assumed to start at zero. A trial retains
    segment directions, symbol/caption clearance, parallel spacing, crossing
    clearance and arrow leads. The usual final gates still decide the sheet.
    """
    from pandid.render.native_routes import stream_polyline
    from pandid.render.crossings import crossing_order
    from pandid.routing.crossing_clearance import _overlaps, _IntersectionPlan
    from pandid.routing.terminal_clearance import anchored_waypoints, arrow_lead_preserved
    from pandid.routing.captions import equipment_tags, foreign_line_plates
    from pandid.routing.visibility import Rect
    from pandid.portgeom import unit_box
    from pandid.render.nameplates import fixed_boxes

    def overflow(box):
        return sum(max(0., box[k+2]-box[k]-limit) for k,limit in enumerate((width,height)))

    if overflow(measure(fs)) < 1e-6:
        return []
    boxes=[Rect(x0,x1,y0,y1) for u in fs.units if u.frame
           for x0,y0,x1,y1 in [unit_box(u,u.frame)]]
    boxes += list(equipment_tags(fs,settled=True).values())
    boxes += [Rect(x0,x1,y0,y1) for x0,y0,x1,y1 in fixed_boxes(fs)]
    lines={i:stream_polyline(s) for i,s in enumerate(fs.streams) if s.route}
    spacing=max(fs.layout_options.stream_spacing,12.)
    moved=[]
    for _ in range(2*len(lines)):
        bounds=measure(fs)
        before=overflow(bounds)
        if before<1e-6:
            break
        metrics=(_overlaps(lines,spacing),_overlaps(lines),len(crossing_order(lines,5)[1]))
        candidates=[]
        for key,points in lines.items():
            stream=fs.streams[key]
            if stream.route.manual or any(getattr(u,'host',None) is stream for u in fs.units):
                # This pass follows the control-placement fixed point. A
                # balloon tapped along a stream must keep that exact path.
                continue
            obstacles=_IntersectionPlan([*boxes,*foreign_line_plates(fs,stream)])
            for axis,limit in enumerate((width,height)):
                low,high=bounds[axis],bounds[axis+2]
                if high-low <= limit+1e-6:
                    continue
                for j in range(1,len(points)-2):
                    a,b=points[j:j+2]
                    if abs(a[axis]-b[axis])>1e-6:
                        continue
                    target=high-limit if abs(a[axis]-low)<1e-6 else low+limit if abs(a[axis]-high)<1e-6 else None
                    if target is None:
                        continue
                    proposal=list(points)
                    for at in (j,j+1):
                        p=list(proposal[at]);p[axis]=target;proposal[at]=tuple(p)
                    pairs=list(zip(zip(points,points[1:]),zip(proposal,proposal[1:])))
                    if any(sum((b[k]-a[k])*(d[k]-c[k]) for k in (0,1))<=0
                           for (a,b),(c,d) in pairs):
                        continue
                    if obstacles.adds([(old,new) for old,new in pairs if old!=new]):
                        continue
                    if not arrow_lead_preserved(fs,stream,points,proposal):
                        continue
                    trial={**lines,key:proposal}
                    if (_overlaps(trial,spacing)>metrics[0]+1e-6 or _overlaps(trial)>metrics[1]+1e-6
                            or len(crossing_order(trial,5)[1])>metrics[2]):
                        continue
                    saved=stream.route.waypoints
                    stream.route.waypoints=anchored_waypoints(stream,proposal)
                    try:
                        after=overflow(measure(fs))
                    finally:
                        stream.route.waypoints=saved
                    if after<before-1e-6:
                        candidates.append((after,abs(target-a[axis]),key,j,proposal))
        if not candidates:
            break
        _,_,key,_,proposal=min(candidates,key=lambda row:row[:4])
        stream=fs.streams[key]
        stream.route.waypoints=anchored_waypoints(stream,proposal)
        lines[key]=stream_polyline(stream)
        moved.append(stream.name)
    return moved
