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


def groups(fs):
    result = OrderedDict()
    for stream in fs.streams:
        if stream.kind not in PROCESS_KINDS or not stream.label:
            continue
        key = ('group', stream.label_group) if stream.label_group else ('stream', stream.name)
        result.setdefault(key, []).append(stream)
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
