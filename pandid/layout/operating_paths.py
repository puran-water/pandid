"""Keep serial process stations together when a dense sheet is packed."""
from pandid.geometry import Frame
from pandid.layout.halo import Pad
from pandid.layout.stages import slot
from pandid.layout.operating_banks import Assembly
from pandid.portgeom import port_point
from pandid.render.line_groups import caption_size


def paths(fs, membership, pads, claimed, width):
    available = set(membership) - claimed
    primary = {s.source.owner for s in fs.streams if s.kind == 'material' and s.flow_class == 'main'}
    primary_targets = {s.dest.owner for s in fs.streams if s.kind == 'material' and s.flow_class == 'main'}
    edges = [s for s in fs.streams if s.kind == 'material' and not s.is_recycle]
    incoming = {u:[s for s in edges if s.dest.owner is u and
                   (s.flow_class == 'main' or u not in primary_targets)] for u in available}
    outgoing = {u:[s for s in edges if s.source.owner is u and
                   (s.flow_class == 'main' or u not in primary)] for u in available}
    eligible = {u for u in available if len(incoming[u]) == 1 and (
        len(outgoing[u]) <= 1 or incoming[u][0].source.owner.kind == 'valve')}
    following = {u:outgoing[u][0].dest.owner for u in eligible
                 if len(outgoing[u]) == 1 and outgoing[u][0].dest.owner in eligible
                 and membership[u] == membership[outgoing[u][0].dest.owner]}
    previous = {v:k for k,v in following.items()}
    result, seen = [], set()
    for start in membership:
        if start not in eligible or start in seen or start in previous:
            continue
        chain, unit = [], start
        while unit in eligible and unit not in seen:
            chain.append(unit);seen.add(unit)
            unit = following.get(unit)
        frames, x, ordinate, labelled = {}, 0., 0., set()

        def finish():
            if len(frames) < 2:
                return
            left = min(px-pads.get(u,Pad()).west for u,(px,py,w,h) in frames.items())
            top = min(py-pads.get(u,Pad()).north for u,(px,py,w,h) in frames.items())
            right = max(px+w+pads.get(u,Pad()).east for u,(px,py,w,h) in frames.items())
            bottom = max(py+h+pads.get(u,Pad()).south for u,(px,py,w,h) in frames.items())
            placed = {u:(px-left,py-top,w,h) for u,(px,py,w,h) in frames.items()}
            result.append(Assembly('path:'+next(iter(frames)).name,tuple(frames),placed,right-left,bottom-top))

        for unit in chain:
            s,p = slot(unit),pads.get(unit,Pad())
            if frames and x+p.west+s.w+p.east > width:
                finish();frames={};x=ordinate=0.
            frame = Frame(x=0,y=0,w=s.w,h=s.h,orientation=s.orientation,
                          mirrored=s.mirrored,mirror_y=s.mirror_y)
            inlet = port_point(unit,frame,incoming[unit][0].dest.name)[1]
            outlet = port_point(unit,frame,outgoing[unit][0].source.name)[1] if len(outgoing[unit]) == 1 else inlet
            frames[unit]=(x+p.west,ordinate-inlet,s.w,s.h)
            ordinate += outlet-inlet
            stream=outgoing[unit][0] if outgoing[unit] else None
            # Repeated segments of one line share one measured caption span.
            gap=fs.layout_options.column_gap
            identity = (stream.label_group or stream.name) if stream else None
            if stream and stream.label and identity not in labelled:
                gap=max(gap,caption_size(stream.label,fs.stream_labels.font_size)[0]
                        +2*fs.layout_options.stream_label_gap)
                labelled.add(identity)
            x+=p.west+s.w+p.east+gap
        finish()
    return result
