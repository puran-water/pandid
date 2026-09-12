"""The process connection a host explicitly declares for several channels.

Coincident coordinates describe where something is drawn, not what was
inserted into the process. Only the host's declaration can join readings into
one element; layout and validation read that same declaration.
"""

from __future__ import annotations


class TapHost:
    @property
    def multi_channel_elements(self) -> tuple:
        """Groups of instrument handles, in their left-to-right order."""
        return getattr(self, '_multi_channel_elements', ())

    def declare_multi_channel(self, *instruments):
        """Declare one insertion carrying these field channels on this host.

        Attach the members first. They must name the same tap and standoff;
        independent devices instead use distinct ``along`` positions on a
        unit face, or distinct ``at`` fractions on a stream. A panel function
        hangs off its field instrument and does not join this declaration.
        """
        check_element(self, instruments)
        existing = {id(inst) for group in self.multi_channel_elements for inst in group}
        if any(id(inst) in existing for inst in instruments):
            raise ValueError('a channel already belongs to a multi-channel element')
        self._multi_channel_elements = (*self.multi_channel_elements, tuple(instruments))
        instruments[0]._invalidate_layout()
        return self


def process_tapping(inst) -> bool:
    """A field reading with a process connection, rather than an actuator."""
    from pandid.streams import Stream
    from pandid.units import Instrument

    host = getattr(inst, 'host', None)
    return (isinstance(inst, Instrument) and host is not None
            and not isinstance(host, Instrument)
            and (not isinstance(host, Stream) or host.kind in {'material', 'energy'})
            and inst.relation == 'sensing' and inst.offset > 0
            and inst.symbol_type == 'default' and inst.display == 'field')


def check_element(host, members) -> None:
    """Check again after edits, so a stale declaration cannot author geometry."""
    if len(members) < 2 or len({id(inst) for inst in members}) != len(members):
        raise ValueError('a multi-channel element needs at least two distinct channels')
    first = members[0]
    for inst in members:
        if not process_tapping(inst) or inst.host is not host:
            raise ValueError('multi-channel members must sense the same process host in the field')
        if (inst.at, inst.along, inst.offset, inst.angle) != (
                first.at, first.along, first.offset, first.angle):
            raise ValueError('multi-channel members must declare the same tap and standoff')
        pin = inst.pin_
        if inst.angle != 90 or pin is not None and (pin.x is not None or pin.y is not None):
            raise ValueError('a multi-channel element needs a perpendicular, unpinned standoff')
        if inst.flowsheet is None or inst.flowsheet is not first.flowsheet:
            raise ValueError('multi-channel members must be on the same flowsheet')
    fs = first.flowsheet
    if not any(item is host for item in [*fs.units, *fs.streams]):
        raise ValueError('the multi-channel host must be on the channels\' flowsheet')


def declared_elements(fs):
    """Validated declarations, including hosts whose last channel was removed."""
    present = {id(inst) for inst in fs.units}
    for host in [*fs.units, *fs.streams]:
        for members in host.multi_channel_elements:
            check_element(host, members)
            if any(id(inst) not in present for inst in members):
                raise ValueError('a declared multi-channel member is missing from the flowsheet')
            yield members


def undeclared_taps(fs, *, resolved=False):
    """Coincident independent connections, ignoring standoff and pin choices."""
    groups = {}
    declarations = {id(inst): index for index, members in enumerate(declared_elements(fs))
                    for inst in members}
    for inst in fs.units:
        if not process_tapping(inst):
            continue
        if resolved:
            from pandid.layout.attach import _anchor
            anchor = _anchor(inst)
            if anchor is None:
                continue
            point = tuple(round(value, 6) for value in anchor[0])
        else:
            point = (inst.at, inst.along)
        groups.setdefault((id(inst.host), point), []).append(inst)
    for members in groups.values():
        elements = {('declared', declarations[id(inst)]) if id(inst) in declarations
                    else ('independent', id(inst)) for inst in members}
        if len(elements) > 1:
            yield members
