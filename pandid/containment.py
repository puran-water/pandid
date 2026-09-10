"""Declared equipment inside open basins, preserving every unit and connection.

Containment affects layout and obstacle geometry; it never invents a process
connection. Internal bulk transfer or mixing duty must be explicitly classified.
An unrelated pipe still sees the entire basin as an obstacle. A pipe serving an
internal item sees the basin walls and may enter through the open top.
"""
from copy import copy
from dataclasses import replace


def read(fs, value):
    if not isinstance(value, dict) or any(not isinstance(k, str) or not isinstance(v, str) for k,v in value.items()):
        raise ValueError("containments must map equipment names to basin names")
    previous = fs.containments
    fs.containments = dict(value)
    try:
        validate(fs)
    except BaseException:
        fs.containments = previous
        raise
    fs._invalidate_layout()


def validate(fs):
    units = {u.name: u for u in fs.units}
    for child, parent in fs.containments.items():
        if child not in units or parent not in units or child == parent or parent in fs.containments:
            raise ValueError("CONTAINMENT_INVALID: known distinct equipment and one top-level basin are required")
        if units[parent].kind != "concrete_basin" or units[child].kind not in {
            "membrane_cage", "air_diffuser", "basin_agitator", "submersible_mixer"}:
            raise ValueError("CONTAINMENT_UNSUPPORTED: declare a supported basin internal and an open concrete basin")
    for s in fs.streams:
        if s.representation not in {"pipe", "internal"}:
            raise ValueError("Unknown stream representation: " + str(s.representation))
        if s.representation == "internal":
            a,b=s.source.owner.name,s.dest.owner.name
            if a == b or fs.containments.get(a,a) != fs.containments.get(b,b) or s.kind not in {"material", "energy"}:
                raise ValueError("INTERNAL_CONNECTION_OUTSIDE_BASIN: " + s.name)
            if s.route and s.route.manual:
                raise ValueError("An internal bulk connection has no pipe waypoints")


def related(fs, a, b):
    return fs.containments.get(a.name) == b.name or fs.containments.get(b.name) == a.name


def accessible(fs, stream):
    return frozenset(fs.containments[u.name] for u in (stream.source.owner, stream.dest.owner) if u.name in fs.containments)


def wall_boxes(unit):
    from pandid.routing.visibility import Rect
    f=unit.frame
    wall=6*f.w/400
    floor=6*f.h/300
    return [Rect(f.x,f.x+wall,f.y,f.y+f.h), Rect(f.x+f.w-wall,f.x+f.w,f.y,f.y+f.h),
            Rect(f.x,f.x+f.w,f.y+f.h-floor,f.y+f.h)]


def layout(fs, engine):
    """Solve the outer process graph, then place each named internal in its basin."""
    from pandid.geometry import Frame
    from pandid.layout import _seed_slots
    from pandid.layout.control import place_control
    from pandid.layout.coordinates import assign_labels
    from pandid.layout.faces import select_faces
    validate(fs)
    units={u.name:u for u in fs.units}
    children={parent:[units[k] for k,v in fs.containments.items() if v==parent] for parent in fs.containments.values()}
    for parent, members in children.items():
        basin=units[parent]
        cages=[u for u in members if u.kind == "membrane_cage"]
        basin.width=max(basin.width or 400, len(cages)*150+80)
        basin.height=max(basin.height or 300, 300)
    projection=copy(fs)
    projection.containments={}
    projection.layout_options=replace(fs.layout_options, parallel_trains=False)
    projection.units=[u for u in fs.units if u.name not in fs.containments and u.kind != 'instrument']
    projection.streams=[]
    for stream in fs.streams:
        if stream.representation == 'internal' or stream.kind != 'material':
            continue
        if stream.source.owner.kind == 'instrument' or stream.dest.owner.kind == 'instrument':
            continue
        line=copy(stream)
        for field in ('source','dest'):
            port=getattr(stream,field)
            if port.owner.name in fs.containments:
                parent=units[fs.containments[port.owner.name]]
                port=copy(parent.outlets[0] if field=='source' else parent.inlets[0])
            setattr(line,field,port)
        if line.source.owner is not line.dest.owner:
            projection.streams.append(line)
    engine.layout(projection)
    _seed_slots(fs)
    for parent,members in children.items():
        f=units[parent].frame
        cages=[u for u in members if u.kind=='membrane_cage']
        others=[u for u in members if u.kind!='membrane_cage']
        for i,u in enumerate(cages):
            w,h=100,134
            x=f.x+f.w*(i+1)/(len(cages)+1)-w/2
            u.width,u.height=w,h
            u.frame=Frame(x,f.y+65,w,h,label_pos='top')
        for i,u in enumerate(others):
            w,h={'air_diffuser':(128,64),'basin_agitator':(64,180),'submersible_mixer':(100,70)}[u.kind]
            x=f.x+f.w*(i+1)/(len(others)+1)-w/2
            y=f.y+f.h-h-20 if u.kind!='basin_agitator' else f.y+25
            u.width,u.height=w,h
            u.frame=Frame(x,y,w,h,label_pos='top')
        for u in members:
            pin=u.pin_
            if pin and any(getattr(pin,k) is not None for k in ('x','y','col','row')):
                raise ValueError('CONTAINED_EQUIPMENT_PIN_CONFLICT: '+u.name)
    select_faces(fs)
    for _ in range(fs.layout_options.control_passes):
        if not place_control(fs):
            break
        select_faces(fs)
    assign_labels(fs)


def route_obstacles(fs, stream):
    """The same host-wall exception for routing and every post-route repair."""
    from pandid.portgeom import unit_box
    from pandid.routing.visibility import Rect
    from pandid.drawing_regions import captions
    allowed=accessible(fs,stream)
    boxes=[]
    for unit in fs.units:
        if unit.frame is None:
            continue
        if unit.name in allowed:
            boxes.extend(wall_boxes(unit))
        else:
            x0,y0,x1,y1=unit_box(unit,unit.frame)
            boxes.append(Rect(x0,x1,y0,y1))
    return boxes+[Rect(c.x,c.x+c.w,c.y,c.y+c.h) for c in captions(fs)]
