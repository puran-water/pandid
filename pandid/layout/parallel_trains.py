"""Align equivalent inline trains between a pair of pipe headers."""
from dataclasses import replace


def align(fs):
    from pandid.portgeom import port_point, unit_box
    process = [s for s in fs.streams if s.kind == 'material']
    incoming = {u: [s for s in process if s.dest.owner is u] for u in fs.units}
    outgoing = {u: [s for s in process if s.source.owner is u] for u in fs.units}
    for source in fs.units:
        if source.kind != 'junction' or len(outgoing[source]) < 2:
            continue
        paths, ends = [], []
        for first in outgoing[source]:
            chain, edge, seen = [], first, {source}
            while edge.dest.owner not in seen:
                unit = edge.dest.owner
                seen.add(unit)
                if unit.kind == 'junction':
                    ends.append(unit)
                    paths.append(chain)
                    break
                if len(incoming[unit]) != 1 or len(outgoing[unit]) != 1:
                    break
                chain.append((unit, edge.dest.name))
                edge = outgoing[unit][0]
        if (len(paths) != len(outgoing[source]) or not all(paths)
                or len(set(ends)) != 1):
            continue
        signatures = {tuple((u.kind, u.variant) for u, _ in path) for path in paths}
        group = {source, ends[0]} | {u for path in paths for u, _ in path}
        if (len(signatures) != 1 or not any(u.kind == 'pump' for u in group)
                or any(u.pin_ is not None for u in group)):
            continue
        spacing = max(140., max(u.frame.h for path in paths for u, _ in path) + 100.)
        top = max(spacing / 2 + 30, min(u.frame.cy for path in paths for u, _ in path))
        for i, path in enumerate(paths):
            for unit, inlet in path:
                _, old_y = port_point(unit, unit.frame, inlet)
                unit.frame = replace(unit.frame, y=unit.frame.y + top + i*spacing - old_y)
        for header in (source, ends[0]):
            header.frame = replace(header.frame, y=top-spacing/2, h=spacing*len(paths))
        # A drain or other side branch can occupy the newly expanded train
        # rows. Move its connected component below, preserving its relative
        # geometry and every authored pin.
        def overlap(a, b):
            return min(a[2],b[2]) > max(a[0],b[0]) and min(a[3],b[3]) > max(a[1],b[1])
        outside = {u for u in fs.units if u not in group and u.kind != 'instrument'}
        moved = set()
        for candidate in fs.units:
            if candidate not in outside or candidate in moved:
                continue
            if not any(overlap(unit_box(candidate,candidate.frame), unit_box(u,u.frame)) for u in group):
                continue
            component, pending = set(), [candidate]
            while pending:
                u = pending.pop()
                if u in component:
                    continue
                component.add(u)
                pending.extend(v for e in incoming[u]+outgoing[u]
                               for v in (e.source.owner,e.dest.owner) if v in outside and v not in component)
            if any(u.pin_ is not None for u in component):
                continue
            bottom = max(u.frame.y_max for u in group | moved)
            shift = bottom + 70 - min(unit_box(u,u.frame)[1] for u in component)
            for u in component:
                u.frame = replace(u.frame,y=u.frame.y+shift)
            moved |= component
