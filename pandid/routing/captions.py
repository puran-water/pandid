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
    for members in groups(fs)[0]:
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
    own=stream.label_group or stream.name
    return ([box for key,box in getattr(fs,'_planned_line_plates',{}).items() if key != own]
            + [box for key,boxes in getattr(fs,'_planned_label_leaders',{}).items()
               if key != own for box in boxes])


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
    from pandid.render.crossings import crossing_order
    from pandid.render.native_routes import stream_polyline
    if crossing_order({i:stream_polyline(s) for i,s in enumerate(fs.streams) if s.route},5)[1]:
        # Attached instruments may still move on the next fixed-point pass.
        # Captions cannot be settled against an unresolved hop order. Final
        # export retains the full crossing gate after all routing passes.
        return False
    from pandid.render.drawio import _tag_pass, fitted_region
    from pandid.render.symbols import default_registry
    from pandid.render.svg import stream_numbers
    from pandid.render.line_groups import groups
    from pandid.routing.visibility import Rect
    tags=_tag_pass(fs,default_registry,None,'auto')
    numbers=stream_numbers(fs,list(tags.plates),None,'auto',fitted_region(fs),False,default_registry)
    identities={members[0].name:members[0].label_group or members[0].name for members in groups(fs)[0]}
    plans={}
    previous=getattr(fs,'_planned_label_leaders',{})
    held=False
    for number in numbers:
        key=identities[number.name]
        held=held or bool(number.leader_crossed or number.crossed or number.placement_limit is not None)
        if not number.leader_crossed and key not in previous:
            continue
        x0,y0,x1,y1=number.box
        plans[key]=[Rect(x0,x1,y0,y1)]
        if number.leader:
            a,b=number.leader
            plans[key].append(Rect(min(a[0],b[0])-2,max(a[0],b[0])+2,
                                   min(a[1],b[1])-2,max(a[1],b[1])+2))
    fs._planned_label_leaders=plans
    return held and bool(plans)
