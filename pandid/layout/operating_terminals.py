"""Keep a single held pipe interface beside the nozzle it actually serves."""
from pandid.geometry import Frame
from pandid.layout.halo import Pad
from pandid.portgeom import port_point
from pandid.render.line_groups import caption_size


def attach(fs, assemblies, pads, maximum_width):
    owner = {u:a for a in assemblies for u in a.members}
    for terminal in fs.units:
        if terminal.kind != 'held_pipe_end' or terminal not in owner:
            continue
        own = owner[terminal]
        if len(own.members) != 1:
            continue
        connected = [s for s in fs.streams if s.kind == 'material' and
                     terminal in (s.source.owner,s.dest.owner)]
        if len(connected) != 1:
            continue
        stream = connected[0]
        incoming = stream.source.owner is terminal
        endpoint = stream.dest if incoming else stream.source
        peer = endpoint.owner
        if peer not in owner or owner[peer] is own:
            continue
        parent = owner[peer]
        px,py,pw,ph = parent.frames[peer]
        pframe = Frame(x=px,y=py,w=pw,h=ph)
        anchor = port_point(peer,pframe,endpoint.name)
        tx,ty,tw,th = own.frames[terminal]
        local = port_point(terminal,Frame(x=0,y=0,w=tw,h=th),'pipe')
        # Reserve a complete number between the two nozzle approaches. A
        # caption-sized span alone leaves no room when a nearby tank inlet
        # contributes a vertical approach beside its end.
        gap = max(90,caption_size(stream.label,fs.stream_labels.font_size)[0]
                  +2*max(25.,fs.layout_options.stream_label_gap))
        x = anchor[0]+(-gap if incoming else gap)-local[0]
        y = anchor[1]-local[1]
        frames = {**parent.frames,terminal:(x,y,tw,th)}
        left=min(x-pads.get(u,Pad()).west for u,(x,y,w,h) in frames.items())
        right=max(x+w+pads.get(u,Pad()).east for u,(x,y,w,h) in frames.items())
        top=min(y-pads.get(u,Pad()).north for u,(x,y,w,h) in frames.items())
        bottom=max(y+h+pads.get(u,Pad()).south for u,(x,y,w,h) in frames.items())
        if right-left > maximum_width:
            continue
        if any(min(x+tw,a+w)>max(x,a) and min(y+th,b+h)>max(y,b)
               for a,b,w,h in parent.frames.values()):
            continue
        parent.frames={u:(x-left,y-top,w,h) for u,(x,y,w,h) in frames.items()}
        parent.members=tuple(parent.frames)
        parent.width,parent.height=right-left,bottom-top
        assemblies.remove(own)
        owner[terminal]=parent

