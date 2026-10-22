"""Router reservations measured by the same code that letters equipment tags."""


def equipment_tags(fs, *, settled=False, use_cached=True):
    from pandid.layout.subsystems import declared
    from pandid.portgeom import unit_box
    from pandid.render.svg import SvgRenderer, _unit_label_box, escaped, _ink_pad, _stream_rung
    from pandid.routing.visibility import Rect

    if not declared(fs):
        return {}
    if use_cached and not settled and getattr(fs,'_resolved_tag_boxes',None) is not None:
        return fs._resolved_tag_boxes
    renderer = SvgRenderer()
    placements = {}
    if settled:
        from pandid.render.drawio import _tag_pass
        # This is an intermediate route-repair pass. Hop ordering is not
        # settled yet, so asking its final export gate here prevents the
        # very crossing repair that follows. Final render repeats the full
        # tag and hop checks after the routes settle.
        placements = _tag_pass(fs,renderer.registry,None,'auto',pending_routes=True).at
    result = {}
    for unit in fs.units:
        if unit.frame is None or not unit.tag or unit.kind in {'feed', 'product', 'instrument'}:
            continue
        x0, y0, x1, y1 = unit_box(unit, unit.frame)
        frame=unit.frame
        dx=dy=0.
        if id(unit) in placements:
            from dataclasses import replace
            side,dx,dy=placements[id(unit)]
            frame=replace(frame,label_pos=side)
        item = renderer._unit_label_item(unit, frame, x0, y0, x1-x0, y1-y0, escaped(unit.tag))
        box = _unit_label_box(item)
        if box is not None:
            x0, y0, x1, y1 = box
            # The lettering gate measures stroked ink and its paper gap,
            # rather than bare pipe centre lines. Reserve the same envelope
            # here so a nominally clear route cannot graze the tag plate.
            pad = _ink_pad(_stream_rung(False))
            result[unit] = Rect(x0+dx-pad, x1+dx+pad, y0+dy-pad, y1+dy+pad)
    return result


def line_plates(fs, *, use_cached_tags=True):
    """Reserve lettering on straight process spans before other lines cross.

    Only a span with enough measured paper and no equipment or tag beneath
    it offers a reservation. A physical line owns at most one plate; its own
    pipe may pass through it, while unrelated process and signal lines may
    not. The ordinary render gate still decides final label placement.
    """
    from pandid.layout.subsystems import declared
    from pandid.portgeom import port_point, unit_box
    from pandid.render.line_groups import groups, caption_size
    from pandid.routing.visibility import Rect
    if not declared(fs):
        return {}
    bodies = [Rect(x0,x1,y0,y1) for u in fs.units if u.frame
              for x0,y0,x1,y1 in [unit_box(u,u.frame)]]
    bodies += list(equipment_tags(fs, use_cached=use_cached_tags).values())
    result = {}
    caption_groups = groups(fs)[0]
    fs._line_caption_keys = {s.name: members[0].label_group or members[0].name
                             for members in caption_groups for s in members}
    for members in caption_groups:
        offers = []
        for stream in members:
            a=port_point(stream.source.owner,stream.source.owner.frame,stream.source.name)
            b=port_point(stream.dest.owner,stream.dest.owner.frame,stream.dest.name)
            if a[0] != b[0] and a[1] != b[1]:
                continue
            w,h=caption_size(stream.label,fs.stream_labels.font_size)
            span=abs(a[0]-b[0])+abs(a[1]-b[1])
            if span+1e-7 < w+2*fs.layout_options.stream_label_gap:
                continue
            if a[0] == b[0]:w,h=h,w
            vertical=a[0]==b[0]
            text_half=(h if vertical else w)/2
            half=text_half+2
            start,end=sorted((a[1],b[1]) if vertical else (a[0],b[0]))
            lo,hi=start+text_half+fs.layout_options.stream_label_gap,end-text_half-fs.layout_options.stream_label_gap
            middle=(start+end)/2
            # A caption near the end of a neighbouring symbol can make the
            # midpoint unusable while a full clear span remains beside it.
            # Search that span before abandoning its reservation; otherwise
            # an unrelated route occupies the only remaining lettering bay.
            candidates={middle,lo,hi}
            for obstacle in bodies:
                low,high=(obstacle.y_min,obstacle.y_max) if vertical else (obstacle.x_min,obstacle.x_max)
                candidates.update((low-half-1,high+half+1))
            for at in sorted(candidates,key=lambda at:(abs(at-middle),at)):
                if not lo-1e-7 <= at <= hi+1e-7:
                    continue
                x,y=(a[0],at) if vertical else (at,a[1])
                box=Rect(x-w/2-2,x+w/2+2,y-h/2-2,y+h/2+2)
                if any(min(box.x_max,o.x_max)>max(box.x_min,o.x_min) and
                       min(box.y_max,o.y_max)>max(box.y_min,o.y_min) for o in bodies):
                    continue
                offers.append((span,box))
                break
        if offers:
            result[members[0].label_group or members[0].name] = max(offers,key=lambda x:x[0])[1]
    return result


def foreign_line_plates(fs, stream):
    own=getattr(fs, '_line_caption_keys', {}).get(stream.name, stream.label_group or stream.name)
    return ([box for key,box in getattr(fs,'_planned_line_plates',{}).items() if key != own]
            + [box for key,boxes in getattr(fs,'_planned_label_leaders',{}).items()
               if key != own for box in boxes])


def routed_plate(fs, members, protected, region):
    """Reserve a symbol-clear bay on an actual run for a held inscription.

    A dense router can leave parallel pipes occupying all the lettering
    space beside a short nozzle span. Reserve real paper on a longer routed
    segment, then reroute only foreign pipes around it. This proposes space;
    the ordinary renderer still has to place and verify the full caption.
    """
    from pandid.render.native_routes import stream_polyline
    from pandid.render.line_groups import caption_size, caption_span
    from pandid.routing.visibility import Rect
    from pandid.render.line_groups import caption_forms
    offers=[]
    for text in [members[0].label,*caption_forms(members[0].label,fs.stream_labels.font_size)]:
        w,h=caption_size(text,fs.stream_labels.font_size)
        minimum=caption_span(text,fs.stream_labels.font_size,fs.layout_options.stream_label_gap)
        for stream in members:
            points=stream_polyline(stream)
            for a,b in zip(points,points[1:]):
                vertical=a[0]==b[0]
                span=abs(a[0]-b[0])+abs(a[1]-b[1])
                if span+1e-7<minimum:
                    continue
                bw,bh=(h,w) if vertical else (w,h)
                start,end=sorted((a[1],b[1]) if vertical else (a[0],b[0]))
                half=minimum/2
                candidates={(start+end)/2,start+half,end-half}
                for obstacle in protected:
                    low,high=(obstacle.y_min,obstacle.y_max) if vertical else (obstacle.x_min,obstacle.x_max)
                    candidates.update((low-half-1,high+half+1))
                for at in sorted(candidates,key=lambda value:(abs(value-(start+end)/2),value)):
                    if at<start+half-1e-7 or at>end-half+1e-7:
                        continue
                    x,y=(a[0],at) if vertical else (at,a[1])
                    box=Rect(x-bw/2-2,x+bw/2+2,y-bh/2-2,y+bh/2+2)
                    if region and (box.x_min<region[0] or box.y_min<region[1] or box.x_max>region[2] or box.y_max>region[3]):
                        continue
                    if any(min(box.x_max,o.x_max)>max(box.x_min,o.x_min) and
                           min(box.y_max,o.y_max)>max(box.y_min,o.y_min) for o in protected):
                        continue
                    offers.append((span,-h,box))
    return max(offers,key=lambda row:row[:2])[2] if offers else None


def shift_caption_run(fs, members, protected, region):
    """Give a full inscription width to an automatic interior pipe track.

    A track can clear a header while its caption still overlaps that header.
    Move the whole straight run, retaining its terminal leads and topology;
    accept only clear paper and no additional body hits or parallel overlap.
    The normal crossing, lettering and fixed-scale gates remain authoritative.
    """
    from pandid.render.line_groups import caption_forms
    forms=[members[0].label,*caption_forms(members[0].label,fs.stream_labels.font_size)]
    for text in sorted(forms,key=lambda value:len(value.splitlines())):
        bay=_shift_caption_run(fs,members,protected,region,text)
        if bay is not None:
            return bay
    return None


def _shift_caption_run(fs,members,protected,region,text):
    from pandid.render.line_groups import caption_size, caption_span
    from pandid.routing.crossing_clearance import _overlaps
    from pandid.routing.visibility import Rect
    w,h=caption_size(text,fs.stream_labels.font_size)
    minimum=caption_span(text,fs.stream_labels.font_size,fs.layout_options.stream_label_gap)
    lines={i:list(s.route.waypoints) for i,s in enumerate(fs.streams) if s.route}
    overlap=_overlaps(lines)
    proposals=[]
    for stream in members:
        if not stream.route or stream.route.manual:
            continue
        key=fs.streams.index(stream)
        points=lines[key]
        old_hits={i for i,o in enumerate(protected) if any(o.intersects_segment(*a,*b) for a,b in zip(points,points[1:]))}
        for j in range(1,len(points)-2):
            a,b=points[j:j+2]
            axis=0 if a[0]==b[0] else 1
            if abs(a[1-axis]-b[1-axis])+1e-7<minimum:
                continue
            half=(h if axis==0 else w)/2+3
            tracks={a[axis]-half-4,a[axis]+half+4}
            for box in protected:
                lo,hi=(box.x_min,box.x_max) if axis==0 else (box.y_min,box.y_max)
                tracks.update((lo-half-2,hi+half+2))
            for track in sorted(tracks,key=lambda t:abs(t-a[axis])):
                if abs(track-a[axis])>2*max(w,h):
                    continue
                candidate=list(points)
                for k in (j,j+1):
                    point=list(points[k]);point[axis]=track;candidate[k]=tuple(point)
                if any(c[0]!=d[0] and c[1]!=d[1] for c,d in zip(candidate,candidate[1:])):
                    continue
                pairs=list(zip(zip(points,points[1:]),zip(candidate,candidate[1:])))
                if any(c==d for c,d in zip(candidate,candidate[1:])):
                    continue
                # Interior legs may turn the other way to reach an empty
                # caption lane. Nozzle leads retain their directions, and
                # a detour may neither fold over itself nor cross itself.
                if any(sum((d[n]-c[n])*(v[n]-u[n]) for n in (0,1))<=0
                       for (c,d),(u,v) in (pairs[0],pairs[-1])):
                    continue
                from pandid.render.crossings import _pair_constraints
                segments=list(zip(candidate,candidate[1:]))
                if any(_pair_constraints(tuple(left),tuple(right),1e9,1e9)
                       for i,left in enumerate(segments) for right in segments[i+2:]):
                    continue
                from pandid.routing.terminal_clearance import arrow_lead_preserved
                if not arrow_lead_preserved(fs,stream,points,candidate):
                    continue
                after={i for i,o in enumerate(protected) if any(o.intersects_segment(*c,*d) for c,d in zip(candidate,candidate[1:]))}
                if not after<=old_hits or _overlaps({**lines,key:candidate})>overlap+1e-6:
                    continue
                original=stream.route.waypoints
                stream.route.waypoints=candidate
                box=routed_plate(fs,[stream],protected,region)
                stream.route.waypoints=original
                if box is not None:
                    proposals.append((abs(track-a[axis]),key,j,track,candidate,box))
    if not proposals:
        return None
    _,key,_,_,points,box=min(proposals,key=lambda row:row[:4])
    fs.streams[key].route.waypoints=points
    return box


def leader_boxes(a,b,*,margin=2.,step=8.):
    """Reserve a leader's narrow ink corridor, not its whole diagonal box."""
    import math
    from pandid.routing.visibility import Rect
    if a[0]==b[0] or a[1]==b[1]:
        return [Rect(min(a[0],b[0])-margin,max(a[0],b[0])+margin,
                     min(a[1],b[1])-margin,max(a[1],b[1])+margin)]
    count=max(1,math.ceil(max(abs(b[k]-a[k]) for k in (0,1))/step))
    return [Rect(min(p[0],q[0])-margin,max(p[0],q[0])+margin,
                 min(p[1],q[1])-margin,max(p[1],q[1])+margin)
            for index in range(count)
            for p,q in [(tuple(a[k]+(b[k]-a[k])*index/count for k in (0,1)),
                          tuple(a[k]+(b[k]-a[k])*(index+1)/count for k in (0,1)))]]


def reserve_leaders(fs):
    """Offer the actual lettering pass clear paper before final validation.

    A held leader has already found a legible, symbol-clear position. Route
    the named foreign pipes away from that position and its short approach;
    the final renderer still repeats every placement and crossing check.
    """
    from pandid.layout.subsystems import declared
    from pandid.streams import PROCESS_KINDS
    if not declared(fs) or not any(s.label and s.kind in PROCESS_KINDS for s in fs.streams):
        return False
    from pandid.render.drawio import _tag_pass, fitted_region
    from pandid.render.symbols import default_registry
    from pandid.render.svg import stream_numbers
    from pandid.render.line_groups import groups
    from pandid.routing.visibility import Rect
    # Like the equipment-tag repair pass, this is intermediate geometry.
    # Requiring final hop order here skipped all caption repair on dense
    # sheets; native export still enforces its complete crossing gate.
    from pandid.render.crossings import crossing_order
    from pandid.render.native_routes import stream_polyline
    from pandid.render.svg import draws_arrowheads, HOP_R
    pending=bool(crossing_order({i:stream_polyline(s) for i,s in enumerate(fs.streams) if s.route},HOP_R)[1])
    # Once crossing order is legal, the hop ink must participate exactly as
    # it does in final export. Ignoring it left a clear intermediate caption
    # with a crossing leader on the actual native sheet.
    tags=_tag_pass(fs,default_registry,None,'auto',pending_routes=pending)
    numbers=stream_numbers(fs,list(tags.plates),None,'auto',fitted_region(fs),
                           draws_arrowheads(getattr(fs,'_drawn_as',None)),default_registry,pending_routes=pending)
    members_by_name={members[0].name:members for members in groups(fs)[0]}
    identities={name:members[0].label_group or name for name,members in members_by_name.items()}
    from pandid.render.svg import _ink, caption_symbols
    # A reservation must clear the same stroked symbols, descriptors and
    # flange marks as final lettering, not merely their unpadded bodies.
    hard=[Rect(x0,x1,y0,y1) for x0,y0,x1,y1 in
          [*caption_symbols(fs, pending_routes=pending), *tags.plates]]
    hard += [Rect(*[mark.box[i] for i in (0,2,1,3)]) for mark in _ink(fs,'auto',include_hops=False) if mark.kind=='tap']
    plans={}
    previous=getattr(fs,'_planned_label_leaders',{})
    held=False
    for number in numbers:
        key=identities[number.name]
        held=held or bool(number.leader_crossed or number.crossed or number.placement_limit is not None)
        if number.leader_crossed or (number.placement_limit is not None and number.leader is None):
            # Other line captions are movable results of this same routing
            # pass, not fixed equipment. Let their pipes give way to a held
            # caption's bay; all captions are laid out and gated again.
            occupied=list(hard)
            occupied += [box for boxes in plans.values() for box in boxes]
            # A caption already clear on its own pipe has earned that paper.
            # Reserving it again for a held line makes the next lettering
            # pass oscillate, even when both pipes themselves are clear.
            occupied += [Rect(n.box[0],n.box[2],n.box[1],n.box[3]) for n in numbers
                         if n.name != number.name and not n.leader_crossed
                         and not n.crossed and n.placement_limit is None]
            bay=routed_plate(fs,members_by_name[number.name],occupied,fitted_region(fs))
            if bay is None:
                bay=shift_caption_run(fs,members_by_name[number.name],occupied,fitted_region(fs))
            if bay is not None:
                plans[key]=[bay]
                continue
        if not number.leader_crossed and key not in previous:
            continue
        x0,y0,x1,y1=number.box
        plans[key]=[Rect(x0,x1,y0,y1)]
        if number.leader:
            a,b=number.leader
            plans[key].extend(leader_boxes(a,b))
    fs._planned_label_leaders=plans
    trace=getattr(fs,'_caption_repair_trace',[])
    trace.append({'held':held,'reservations':len(plans),
                  'reserved_boxes':{key:[(b.x_min,b.y_min,b.x_max,b.y_max) for b in boxes] for key,boxes in plans.items()},
                  'unresolved':[n.name for n in numbers if n.placement_limit is not None and n.leader is None]})
    fs._caption_repair_trace=trace
    return held and bool(plans)
