"""Units a host's nozzle places: a vent standing on a top nozzle.

An open vent to atmosphere piped from a nozzle that can only leave upward
-- a tower's overhead, a vessel's vent nozzle -- is built as a short stack
straight up off that nozzle, and a reader expects it drawn so. As a free
process unit it took a grid column of its own, as far off as the fit put
it, and the router ran the vapour line across the sheet to it: a degasser
drawn with its off-gas piped to somewhere that is not there.

So such a vent takes no part in stage 1 (:func:`pandid.layout.stages.
process_units` leaves it out, and the run into it is not a stream stage 1
positions against) and its frame is set from its host instead, after the
host has its own: the vent's inlet on the nozzle's axis, :data:`VENT_STUB`
above it. Keyed on the **Vent unit** and on its source nozzle's only face
being north, never on what the host is; a vent off a side nozzle, a vent
the author pinned, and a vent with no host keep the grid.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pandid.flowsheet import Flowsheet
    from pandid.units import Port, Unit

#: How far above the nozzle the vent's own inlet stands: one short stub of
#: pipe, drawn, long enough to read as a line and to carry a line number.
VENT_STUB = 30.0


def dock_source(unit: "Unit | None") -> "Port | None":
    """The nozzle *unit* stands on, or ``None`` when it is laid out freely."""
    if unit is None or unit.kind != "vent" or unit.pin_ is not None:
        return None
    inlet = unit.ports.get("inlet")
    stream = getattr(inlet, "stream", None)
    if stream is None or stream.representation == "internal":
        return None
    source = stream.source
    host = source.owner
    if host is None or host is unit or host.kind in ("instrument", "vent"):
        return None
    from pandid.portgeom import port_faces

    return source if port_faces(host, source.name) == ["N"] else None


def is_docked(unit: "Unit | None") -> bool:
    """True when a host's top nozzle places this vent, not the grid."""
    return dock_source(unit) is not None


def dock(fs: "Flowsheet") -> None:
    """Stand every docked vent on its nozzle, against its host's frame.

    Run after the hosts have frames, and again whenever a later pass may
    have moved one; it reads only the host, so running it twice is the
    same as running it once.
    """
    from pandid.geometry import Frame
    from pandid.portgeom import port_point, resolve_size

    for unit in fs.units:
        source = dock_source(unit)
        if source is None or source.owner.frame is None:
            continue
        host = source.owner
        nx, ny = port_point(host, host.frame, source.name)
        w, h = resolve_size(unit)
        probe = Frame(0.0, 0.0, w, h)
        ix, iy = port_point(unit, probe, "inlet")
        unit.frame = Frame(nx - ix, ny - VENT_STUB - iy, w, h,
                           label_pos=unit.frame.label_pos if unit.frame else None)
