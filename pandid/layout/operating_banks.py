"""Measured, rigid parallel equipment banks for the operating-sheet planner."""
from dataclasses import dataclass
from pandid.geometry import Frame
from pandid.layout.halo import Pad
from pandid.layout.stages import slot
from pandid.portgeom import port_point


@dataclass(eq=False)
class Assembly:
    name: str
    members: tuple
    frames: dict
    width: float
    height: float


def footprint(fs, assembly, pads):
    """Reserve rigid members and the clear pipe spans joining those members.

    Empty corners are usable paper; an in-line spool between two members is
    not. Omitting it allowed another bank's header to bisect a relief outlet.
    """
    parts=[]
    for u,(x,y,w,h) in assembly.frames.items():
        p=pads.get(u,Pad())
        parts.append((x-p.west,y-p.north,w+p.west+p.east,h+p.north+p.south))
    margin=max(4.,fs.layout_options.stream_spacing)/2
    for stream in fs.streams:
        if stream.kind not in {'material','energy'} or any(
                port.owner not in assembly.frames for port in (stream.source,stream.dest)):
            continue
        points=[]
        for port in (stream.source,stream.dest):
            x,y,w,h=assembly.frames[port.owner]
            points.append(port_point(port.owner,Frame(x=x,y=y,w=w,h=h),port.name))
        a,b=points
        if a[0] == b[0] or a[1] == b[1]:
            x0,y0=max(0,min(a[0],b[0])-margin),max(0,min(a[1],b[1])-margin)
            x1,y1=min(assembly.width,max(a[0],b[0])+margin),min(assembly.height,max(a[1],b[1])+margin)
            parts.append((x0,y0,x1-x0,y1-y0))
    return parts


def banks(fs, membership, pads):
    from pandid.layout.parallel_trains import _groups
    result, claimed = [], set()
    for source, target, paths, members, _, outgoing in _groups(fs):
        if members & claimed or any(u not in membership for u in members):
            continue
        if len({membership[u] for u in members}) != 1:
            continue
        frames, axes, ends = {}, {}, []
        above = below = 0.
        for path in paths:
            rise = 0.
            for unit, inlet in path:
                s = slot(unit)
                frame = Frame(x=0, y=0, w=s.w, h=s.h, orientation=s.orientation,
                              mirrored=s.mirrored, mirror_y=s.mirror_y)
                axis = port_point(unit, frame, inlet)[1]
                # A centrifugal pump's discharge is above its suction.
                # Continue that real nozzle axis through its downstream
                # valves instead of introducing a dogleg at every symbol.
                axes[unit] = axis - rise
                pad = pads.get(unit, Pad())
                above = max(above, axes[unit] + pad.north)
                below = max(below, s.h - axes[unit] + pad.south)
                outlet = outgoing[unit][0].source.name
                rise += port_point(unit, frame, outlet)[1] - axis
            ends.append(rise)
        if max(ends) - min(ends) > 1e-6:
            continue
        clearance=fs.layout_options.parallel_train_clearance
        pitch = above+below+(100. if clearance is None else clearance)
        row0 = above
        # Headers end just beyond their first/last branch, rather than
        # carrying an unused half-row of pipe at each end of the bank.
        tail = 12.
        header_height = pitch*(len(paths)-1)+2*tail
        extra_pitch = max(60., 3*fs.stream_labels.font_size+fs.layout_options.stream_spacing)
        def header_ports(header, source_side):
            selected = {}
            for row, path in enumerate(paths):
                member = path[0][0] if source_side else path[-1][0]
                connections = [edge for edge in fs.streams if edge.kind == 'material'
                               and edge.source.owner is (header if source_side else member)
                               and edge.dest.owner is (member if source_side else header)]
                if len(connections) != 1:
                    raise ValueError('PARALLEL_BANK_PORT_AMBIGUOUS: '+header.name)
                port = connections[0].source if source_side else connections[0].dest
                selected[port.name] = tail+row*pitch
            family = header.outlets if source_side else header.inlets
            spare = [port for port in family if port.name not in selected]
            for index, port in enumerate(spare):
                selected[port.name] = header_height-tail+extra_pitch*(index+1)
            # The opposite single process connection stays at the centre of
            # the operating branches when an extra CIP nozzle extends a tail.
            opposite = header.inlets if source_side else header.outlets
            for index, port in enumerate(opposite):
                fraction = index/(len(opposite)-1) if len(opposite)>1 else .5
                selected[port.name] = tail+(header_height-2*tail)*fraction
            header._operating_port_y = selected
            header._operating_header_height = header_height+extra_pitch*len(spare)
            return header._operating_header_height
        source_pad = pads.get(source, Pad())
        x = source_pad.west
        source_size = slot(source)
        if source.kind == 'junction':
            frames[source] = (x, row0-tail, source_size.w, header_ports(source,True))
        else:
            # A common tank can feed parallel pumps directly. Its construction
            # symbol and size stay fixed; only a pipe header may be stretched.
            frames[source] = (x, row0+(len(paths)-1)*pitch/2-source_size.h/2,
                              source_size.w, source_size.h)
        x += slot(source).w + source_pad.east + fs.layout_options.column_gap
        columns = list(zip(*paths))
        for index, column in enumerate(columns):
            width = max(slot(u).w + pads.get(u, Pad()).west + pads.get(u, Pad()).east for u, _ in column)
            for row, (unit, _) in enumerate(column):
                s, pad = slot(unit), pads.get(unit, Pad())
                px = x + pad.west + (width-s.w-pad.west-pad.east)/2
                frames[unit] = (px, row0+row*pitch-axes[unit], s.w, s.h)
            gap = fs.layout_options.column_gap
            # A line survives its isolation valve and tap segments, but needs
            # one readable straight span beside the equipment it serves.
            # Reserve that measured lettering space at purchased equipment,
            # not at every tiny fitting in the same physical line.
            if any(u.kind in {'pump', 'filter'} for u, _ in column) or (
                    index+1 < len(columns) and any(u.kind in {'pump', 'filter'} for u, _ in columns[index+1])):
                peers = {u for u, _ in column}
                labels = [s.label for s in fs.streams if s.kind == 'material'
                          and s.source.owner in peers and s.label]
                reserved = min((pads.get(left, Pad()).east + pads.get(right, Pad()).west
                                for (left, _), (right, _) in zip(column, columns[index+1])), default=0) if index+1 < len(columns) else 0
                from pandid.render.line_groups import caption_size
                gap = max([gap] + [caption_size(label, fs.stream_labels.font_size)[0]
                                  + 2*fs.layout_options.stream_label_gap - reserved for label in labels])
            x += width + gap
        target_pad = pads.get(target, Pad())
        x += target_pad.west
        frames[target] = (x, row0+ends[0]-tail, slot(target).w, header_ports(target,False))
        # A boundary valve belongs to its actual header connection. Keeping
        # it on that nozzle's axis avoids packing a CIP supply beside an
        # unrelated return header and routing it back through the bank.
        for header in (source,target):
            for edge in fs.streams:
                if edge.kind != 'material' or header not in (edge.source.owner,edge.dest.owner):
                    continue
                valve = edge.source.owner if edge.dest.owner is header else edge.dest.owner
                if valve in membership and valve not in frames and valve.kind == 'valve':
                    adjacent = [s for s in fs.streams if s.kind == 'material'
                                and valve in (s.source.owner,s.dest.owner) and s is not edge]
                    if len(adjacent) != 1 or not any(u.kind in {'feed','product'}
                            for u in (adjacent[0].source.owner,adjacent[0].dest.owner)):
                        continue
                    hx,hy,hw,hh = frames[header]
                    hf = Frame(x=hx,y=hy,w=hw,h=hh)
                    hp = edge.dest if edge.dest.owner is header else edge.source
                    vp = edge.source if edge.source.owner is valve else edge.dest
                    vs, pad = slot(valve), pads.get(valve,Pad())
                    vf = Frame(x=0,y=0,w=vs.w,h=vs.h)
                    ax,ay = port_point(header,hf,hp.name)
                    vx,vy = port_point(valve,vf,vp.name)
                    sign = -1 if edge.dest.owner is header else 1
                    frames[valve] = (ax+sign*fs.layout_options.column_gap-vx,ay-vy,vs.w,vs.h)
        left = min(px-pads.get(u, Pad()).west for u, (px, py, w, h) in frames.items())
        top = min(py-pads.get(u, Pad()).north for u, (px, py, w, h) in frames.items())
        right = max(px+w+pads.get(u, Pad()).east for u, (px, py, w, h) in frames.items())
        bottom = max(py+h+pads.get(u, Pad()).south for u, (px, py, w, h) in frames.items())
        frames = {u: (px-left, py-top, w, h) for u, (px, py, w, h) in frames.items()}
        result.append(Assembly(source.name+'--'+target.name, tuple(frames), frames, right-left, bottom-top))
        claimed.update(frames)
    return result
