"""Explicit line-caption groups preserve every connection's identity."""
from collections import OrderedDict
from pandid.streams import PROCESS_KINDS


def caption_size(text, font_size):
    """The native label plate, shared by placement and caption reservations."""
    from pandid.render.svg import NUMBER_TYPE, _HALO_CHAR, _HALO_PAD, _HALO_DEEP
    scale = font_size / NUMBER_TYPE
    # Preserve the renderer's arithmetic order: a different last floating
    # point bit can change whether a plate exactly on a region edge fits.
    lines = text.splitlines() or ['']
    return (max(map(len, lines)) * (_HALO_CHAR * scale) + _HALO_PAD * scale,
            _HALO_DEEP * scale + (len(lines) - 1) * font_size * 1.2)


def caption_span(text, font_size, gap):
    """Straight pipe reserved for a plate and its visible pipe/arrow ends."""
    width = caption_size(text, font_size)[0]
    if len(text.splitlines()) >= 3:
        from pandid.render.svg import _LABEL_CLEAR
        from pandid.render.symbols import ARROWHEAD
        return width + max(2 * gap, 2 * _LABEL_CLEAR + ARROWHEAD)
    return width + 2 * gap


def caption_forms(text, font_size):
    """Alternative line breaks, with every identity/property word retained.

    Narrow horizontal plates and narrow vertical plates need different
    aspect ratios. Only the descriptive rows may reflow; neither lettering
    size nor the line identity and DN/class rows change.
    """
    rows=text.splitlines()
    if len(rows)<3:
        return []
    from pandid.render.nameplates import _wrapped
    description=' '.join(rows[2:])
    result=[]
    for width in (12*font_size,18*font_size,float('inf')):
        candidate='\n'.join([*rows[:2],*_wrapped(description,width,font_size)])
        if candidate!=text and candidate not in result:
            result.append(candidate)
    return result


def groups(fs):
    result = OrderedDict()
    # Before line identities are claimed, a continuous uniform header may
    # share its DN/class/fluid inscription through taps, tees and inline valves. Only an
    # explicit unminted declaration permits this; real line numbers, changed
    # properties, equipment and disconnected runs remain separate groups.
    parent = {}
    def root(key):
        parent.setdefault(key, key)
        while parent[key] != key:
            key = parent[key]
        return key
    candidates = []
    metadata = fs.drawio_metadata.get('streams', {})
    for stream in fs.streams:
        key = ('group', stream.label_group) if stream.label_group else ('stream', stream.name)
        root(key)
        if metadata.get(stream.name, {}).get('attributes', {}).get('line-identity-status') == 'candidate_unminted':
            candidates.append((stream, key))
    for index, (left, a) in enumerate(candidates):
        junctions = {p.owner for p in (left.source,left.dest) if p.owner.kind in {'junction','valve'}}
        for right, b in candidates[index+1:]:
            if ((left.label,left.kind,left.color) == (right.label,right.kind,right.color)
                    and junctions.intersection(p.owner for p in (right.source,right.dest))):
                parent[root(b)] = root(a)
    for stream in fs.streams:
        if stream.kind not in PROCESS_KINDS or not stream.label:
            continue
        key = ('group', stream.label_group) if stream.label_group else ('stream', stream.name)
        result.setdefault(root(key), []).append(stream)
    aliases = {}
    for members in result.values():
        if len({(s.label, s.kind, s.color) for s in members}) != 1:
            raise ValueError('LINE_LABEL_GROUP_CONFLICT: ' + str(members[0].label_group))
        aliases.update((s.name, members[0].name) for s in members)
    return list(result.values()), aliases


def caption_owners(fs, numbers):
    """Attach the native label to the member whose run supplied its position."""
    from pandid.render.svg import stream_polyline

    by_name = {number.name: number for number in numbers}
    result = {}
    for members in groups(fs)[0]:
        number = by_name.get(members[0].name)
        if number is None:
            continue
        owner = next((s for s in members if number.seg in list(zip(
            stream_polyline(s), stream_polyline(s)[1:]))), members[0])
        result[id(owner)] = number
    return result
