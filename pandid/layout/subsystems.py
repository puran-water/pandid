"""Pack declared operating subsystems at fixed scale with rigid pump/filter banks.

Only metadata-requested sheets use this planner. Every port, valve, instrument
and caption remains subject to the ordinary native and physical gates.
"""
from collections import Counter, defaultdict
from pandid.geometry import Frame
from pandid.layout.halo import Pad, balloon_pads, is_core
from pandid.layout.stages import slot


def declared(fs):
    return any(v.get('attributes', {}).get('layout-subsystem')
               for v in fs.drawio_metadata.get('units', {}).values())


def _membership(fs):
    metadata = fs.drawio_metadata.get('units', {})
    by_id = {v.get('id'): name for name, v in metadata.items()}
    result = {}
    for unit in fs.units:
        attrs = metadata.get(unit.name, {}).get('attributes', {})
        group = attrs.get('layout-subsystem')
        if not group and attrs.get('projection-for'):
            original = by_id.get(attrs['projection-for'])
            group = metadata.get(original, {}).get('attributes', {}).get('layout-subsystem')
        if group and is_core(unit):
            result[unit] = group
    missing = {u for u in fs.units if is_core(u)} - set(result)
    for _ in range(len(missing)+1):
        previous = len(missing)
        for unit in list(missing):
            peers = [v for s in fs.streams if s.kind in {'material','energy'}
                     for v in (s.source.owner,s.dest.owner)
                     if unit in (s.source.owner,s.dest.owner) and v in result]
            if peers:
                result[unit] = result[peers[0]]
                missing.remove(unit)
        if len(missing) == previous:
            break
    if missing:
        raise ValueError('OPERATING_SUBSYSTEM_REQUIRED: '+', '.join(u.name for u in missing))
    return result


def place(fs):
    from pandid.render.drawio import fitted_band
    from pandid.profiles.process import boundary_approach, ESCAPE_LANE
    from pandid.render.furniture import text_width
    from pandid.layout.operating_banks import Assembly, banks

    fs._dense_boundaries,fs._dense_nameplates={},{}
    fs._resolved_tag_boxes=None
    membership, pads = _membership(fs), balloon_pads(fs)
    width, height = fitted_band(fs, fs.layout_options.boundary_page or 'A1')
    flag_width = max((slot(u).w for u in fs.units if u.kind in {'feed','product'}), default=0)
    core_width = width - 2*(flag_width+boundary_approach(fs)) - ESCAPE_LANE
    from pandid.layout.grouped_stations import stations
    assemblies = stations(fs, membership, pads)
    grouped = {u for a in assemblies for u in a.members}
    assemblies += banks(fs, {u: group for u, group in membership.items() if u not in grouped}, pads)
    from pandid.layout.operating_paths import paths
    claimed = {u for a in assemblies for u in a.members}
    assemblies += paths(fs,membership,pads,claimed,core_width)
    owner = {u: a for a in assemblies for u in a.members}
    for unit in membership:
        if unit in owner:
            continue
        s, p = slot(unit), pads.get(unit, Pad())
        a = Assembly(unit.name, (unit,), {unit:(p.west,p.north,s.w,s.h)},
                     s.w+p.west+p.east, s.h+p.north+p.south)
        assemblies.append(a)
        owner[unit] = a
    from pandid.layout.operating_terminals import attach
    attach(fs,assemblies,pads,core_width)
    from pandid.layout.operating_banks import reserve_caption_bays
    reserve_caption_bays(fs,assemblies,pads)
    owner = {u:a for a in assemblies for u in a.members}
    groups = {}
    # Authored subsystem order is stable even when a bank has collapsed many
    # appearances into a single placement envelope.
    for unit in membership:
        group, assembly = membership[unit], owner[unit]
        if assembly not in groups.setdefault(group, []):
            groups[group].append(assembly)
    counts = Counter(s.label_group or s.name for s in fs.streams if s.kind=='material' and s.label)
    boxes = []
    for name, members in groups.items():
        edges = [(owner[s.source.owner],owner[s.dest.owner],s) for s in fs.streams
                 if s.kind in {'material','energy'} and not s.is_recycle
                 and s.source.owner in owner and s.dest.owner in owner
                 and owner[s.source.owner] is not owner[s.dest.owner]
                 and owner[s.source.owner] in members and owner[s.dest.owner] in members]
        incoming = {a: {left for left,right,_ in edges if right is a} for a in members}
        rank, pending = {}, list(members)
        while pending:
            ready = [a for a in pending if incoming[a] <= rank.keys()]
            if not ready:
                # Collapsing a parallel bank can move the layout cycle's
                # previously chosen back edge inside that bank. Tear only a
                # placement dependency, preferring secondary return lines;
                # preserve every physical stream and its real endpoints.
                chosen = min(pending, key=lambda a: (
                    sum(s.flow_class == 'main' for left, right, s in edges
                        if right is a and left not in rank),
                    len(incoming[a] - rank.keys()), members.index(a)))
                incoming[chosen] &= rank.keys()
                ready = [chosen]
            for a in ready:
                rank[a] = max((rank[p]+1 for p in incoming[a]),default=0)
                pending.remove(a)
        columns = defaultdict(list)
        for a in members:
            columns[rank[a]].append(a)
        local, x, top, bottom = {}, 0., 0., 0.
        for _, column in sorted(columns.items()):
            span = max(a.width for a in column)
            if x and x+span > core_width:
                top = bottom+70
                x = 0.
            cursor = top
            for a in column:
                parents = [local[p][1]+p.height/2 for p in incoming[a] if p in local]
                desired = sum(parents)/len(parents)-a.height/2 if parents else cursor
                py = max(cursor,desired)
                local[a] = (x,py)
                clearance=fs.layout_options.parallel_train_clearance
                cursor = py+a.height+(100. if clearance is None else clearance)
                bottom = max(bottom,cursor)
            from pandid.render.line_groups import caption_span
            captions = [caption_span(s.label,fs.stream_labels.font_size,fs.layout_options.stream_label_gap)
                        for left,_,s in edges if left in column and s.label and counts[s.label_group or s.name]==1]
            x += span+max(fs.layout_options.column_gap,max(captions,default=0))
        w = max(px+a.width for a,(px,py) in local.items())
        h = max(py+a.height for a,(px,py) in local.items())
        if len(groups)==1 and top==0 and max(rank.values(),default=0):
            spare, last = max(0.,core_width-w), max(rank.values())
            local = {a:(px+spare*rank[a]/last,py) for a,(px,py) in local.items()}
            w = core_width
        boxes.append((local,w,h))
    x = y = shelf = 0.
    placements = {}
    for local,w,h in boxes:
        if x and x+w > core_width:
            x = 0.
            y += shelf+70
            shelf = 0.
        placements.update({a:(px+x,py+y) for a,(px,py) in local.items()})
        x += w+70
        shelf = max(shelf,h)
    for u in fs.units:
        s=slot(u)
        u.frame=Frame(x=0,y=50,w=s.w,h=s.h,col=s.col,row=s.row,
                      orientation=s.orientation,mirrored=s.mirrored,mirror_y=s.mirror_y)
    def apply_positions():
        for a,(ax,ay) in placements.items():
            for u,(px,py,w,h) in a.frames.items():
                if u.pin_ is not None:
                    raise ValueError('OPERATING_SUBSYSTEM_PIN_CONFLICT: '+u.name)
                s=slot(u)
                u.frame=Frame(x=ax+px+50,y=ay+py+50,w=w,h=h,col=s.col,row=s.row,
                              orientation=s.orientation,mirrored=s.mirrored,mirror_y=s.mirror_y)
    apply_positions()
    from pandid.render.nameplates import plan
    from pandid.layout.rectangle_pack import pack
    cards, data_bounds = plan(fs,(0,0,width-50,0))
    # A bottom-facing nozzle still needs its two approaches and separated
    # tracks before the common data row. Measuring only equipment envelopes
    # made a nominally fitting field overflow after its return pipes routed.
    route_reserve=max(50.,2*25.+2*fs.layout_options.stream_spacing
                      +fs.stream_labels.font_size*1.2)
    budget = height-data_bounds[3]-route_reserve
    if max((y+a.height for a,(x,y) in placements.items()),default=0)>budget and budget>0:
        rectangles=[(a.name,a.width+20,a.height+20) for a in assemblies]
        links=[(owner[s.source.owner].name,owner[s.dest.owner].name) for s in fs.streams
               if s.kind=='material' and s.source.owner in owner and s.dest.owner in owner]
        packed=pack(rectangles,core_width,budget,links)
        if packed:
            placements={a:packed[a.name][:2] for a in assemblies}
            apply_positions()
        else:
            from pandid.layout.shape_pack import pack as pack_shapes
            from pandid.layout.operating_banks import footprint
            shapes=[]
            for a in assemblies:
                shapes.append((a.name,a.width,a.height,footprint(fs,a,pads)))
            packed=pack_shapes(shapes,core_width,budget,links=links)
            if packed is None:
                from pandid.layout.constraint_pack import pack as solve_shapes
                try:
                    packed=solve_shapes(shapes,core_width,budget,gap=20)
                except ValueError as exc:
                    if not str(exc).startswith('FIXED_SCALE_SEARCH_LIMIT:'):
                        raise
            if packed:
                placements={a:packed[a.name] for a in assemblies}
                apply_positions()
            else:
                from pandid.layout.dense_operating import place as place_dense
                together=place_dense(fs,assemblies,pads,cards,width,height)
                if together:
                    placements=together
                    apply_positions()
                else:
                    raise ValueError('FIXED_SCALE_CAPACITY: measured operating assemblies do not fit '
                                     f'the current A1 composition ({core_width:.1f} x {budget:.1f}); '
                                     'lettering and reservations are retained')
