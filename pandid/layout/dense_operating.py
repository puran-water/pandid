"""Use paper below boundary rails while retaining one common nameplate row.

All equipment data stay below the process field. The fallback packs measured
operating assemblies into the remaining shape; no card becomes a second row.
"""
from dataclasses import replace
from copy import deepcopy
from pandid.layout.shape_pack import pack


def place(fs, assemblies, pads, cards, width, height):
    from pandid.profiles.process import boundary_approach, ESCAPE_LANE
    from pandid.render.nameplates import _aligned_positions
    approach = boundary_approach(fs)
    width -= ESCAPE_LANE
    height -= ESCAPE_LANE
    gap = max((r.get('gap', 20) for r in fs.equipment_data.values()), default=0)
    clearance = max((r.get('clearance', 65) for r in fs.equipment_data.values()), default=0)
    if sum(c.w for c in cards) + gap * max(0, len(cards)-1) > width:
        return None
    card_height = max((c.h for c in cards), default=0)
    budget = height-card_height-clearance
    if budget <= 0:
        return None
    rails, obstacles = {}, []
    for kind in ('feed', 'product'):
        rail = [u for u in fs.units if u.kind == kind]
        if not rail:
            continue
        flag_width = max(u.frame.w for u in rail)
        total = sum(u.frame.h for u in rail)+fs.layout_options.boundary_flag_gap*(len(rail)-1)
        if total > budget:
            return None
        left = 0 if kind == 'feed' else width-flag_width
        obstacles.append((0 if kind == 'feed' else left-approach, 0,
                          flag_width+approach, total))
        y = 0
        for unit in rail:
            rails[unit.name] = (left+unit.frame.w-50 if kind == 'feed' else left, y+50)
            y += unit.frame.h+fs.layout_options.boundary_flag_gap
    from pandid.layout.operating_banks import footprint
    shapes = [(a.name, a.width, a.height, footprint(fs, a, pads)) for a in assemblies]
    spacing = max(2*fs.layout_options.instrument_clearance, gap)
    owners = {u: a for a in assemblies for u in a.members}
    links=[(owners[s.source.owner].name,owners[s.dest.owner].name) for s in fs.streams
           if s.kind=='material' and s.source.owner in owners and s.dest.owner in owners
           and owners[s.source.owner] is not owners[s.dest.owner]]
    packed = pack(shapes, width, budget, obstacles=obstacles, gap=spacing,links=links)
    if packed is None:
        from pandid.layout.constraint_pack import pack as solve
        packed = solve(shapes, width, budget, obstacles=obstacles, gap=spacing)
        if packed is None:
            return None
    # Match each flag rail to the vertical order of the real process
    # connections after packing. Declaration order can put chemical feeds
    # above a later-composed break-tank inlet, forcing all four pipes to
    # cross before they reach the equipment. Flag identities do not change.
    for kind in ('feed','product'):
        rail=[u for u in fs.units if u.kind==kind]
        def destination_y(unit):
            peers=[s.dest.owner if kind=='feed' else s.source.owner for s in fs.streams
                   if (s.source.owner if kind=='feed' else s.dest.owner) is unit]
            ordinates=[packed[owners[p].name][1]+owners[p].frames[p][1]+owners[p].frames[p][3]/2
                       for p in peers if p in owners]
            return sum(ordinates)/len(ordinates) if ordinates else float('inf')
        y=50.
        for unit in sorted(rail,key=destination_y):
            rails[unit.name]=(rails[unit.name][0],y)
            y += unit.frame.h+fs.layout_options.boundary_flag_gap
    ordered = sorted(cards, key=lambda c: (packed[owners[fs.units[c.unit_index]].name][0]
                    + owners[fs.units[c.unit_index]].frames[fs.units[c.unit_index]][0], c.unit_index))
    desired = [packed[owners[fs.units[c.unit_index]].name][0]
               + owners[fs.units[c.unit_index]].frames[fs.units[c.unit_index]][0] for c in ordered]
    xs = _aligned_positions(desired, [c.w for c in ordered], 0, gap=gap, right=width)
    fs._dense_boundaries = rails
    fs._dense_nameplates = {fs.units[c.unit_index].name: replace(c, x=x, y=height-card_height+50)
                           for c, x in zip(ordered, xs)}
    fs._dense_nameplate_source = deepcopy(fs.equipment_data)
    return {a: (packed[a.name][0]-50, packed[a.name][1]) for a in assemblies}
