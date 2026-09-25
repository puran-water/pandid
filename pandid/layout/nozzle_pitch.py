"""How far apart a block spreads the runs that carry tagged valves.

A block spreads the connections on one face at
:data:`~pandid.render.symbols.BLOCK_PITCH`, a pitch derived from the
arrowhead so that two arriving lines do not read as one. That is the
right floor for a line, and too tight for a line with a **valve** in it.
Layout lines each in-line unit up with the nozzle its run leaves from, so
a face of three connections, each run through a valve, lays the three
valves out as three rows exactly one block pitch apart -- and the tag
each valve letters above or below itself then has only the gap between
two runs to go in. At 30 units that gap is narrower than a tag at any
house lettering size, so every tag but the outermost was lettered over
the next run (LB TEX template review revision 05: the ten IX valve tags
still over lines after the tag search had tried every face).

So the pitch on such a face is raised to what the tags need, measured
from the tags themselves rather than chosen:

``pitch = reach + clearance``

``reach``
    how far the tag reaches past its own run's centre line on the nearer
    of the two faces the run does not pass through --
    :func:`pandid.render.svg.tag_reach`, the tag search's own geometry at
    the unit's own lettering size.
``clearance``
    what the tag has to stay off in the next row: that row's in-line
    body, half its depth across the run plus the plate clearance every
    label keeps off a symbol (:func:`pandid.render.svg._obstacle`), or,
    with no in-line unit on the face, the line's own ink pad
    (:func:`pandid.render.svg._ink_pad`).

The largest over the face's tagged units governs, and the result never
falls below the block pitch. A block whose author gave it a size keeps
that size: the pitch then grows only as far as the given box allows,
since an explicit width or height wins everywhere else a block is sized.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pandid.flowsheet import Flowsheet

#: The kinds that sit *in* a run rather than at the end of one, the same
#: set :func:`pandid.layout.coordinates._station_gaps` keeps together.
INLINE_KINDS = frozenset({"valve", "fitting", "reducer"})


def _across(unit) -> float:
    """The depth of an in-line unit across the run it sits in."""
    from pandid.render.symbols import default_registry

    if unit.height is not None:
        return unit.height
    return default_registry.for_unit(unit).height


def face_pitch(peers, horizontal: bool) -> "float | None":
    """The pitch one face needs for the tags of the units on its runs.

    *peers* is the unit at the far end of each connection on the face
    (``None`` where there is none), *horizontal* whether the runs leave
    the face across the sheet. ``None`` where nothing on the face letters
    a tag beside a run, which leaves the face at the block pitch.
    """
    from pandid.render.svg import _PLATE_CLEARANCE, _ink_pad, tag_reach
    from pandid.render.weights import LineWeight

    inline = [p for p in peers if p is not None and p.kind in INLINE_KINDS]
    reaches = [r for r in (tag_reach(p, horizontal) for p in inline) if r is not None]
    if not reaches:
        return None
    body = LineWeight.EQUIPMENT.width / 2 + _PLATE_CLEARANCE
    clearance = max([_ink_pad(LineWeight.MAIN_FLOW)]
                    + [_across(p) / 2 + body for p in inline])
    return max(reaches) + clearance


def widen_block_pitches(fs: "Flowsheet") -> None:
    """Set every block's :attr:`~pandid.units.Block.nozzle_pitches`.

    Derived afresh on every layout from the sheet as it stands, so a
    change of lettering size or of the valves on a run is picked up by
    the next layout rather than frozen by the first.
    """
    from pandid.render.symbols import BLOCK_PITCH
    from pandid.units import Block

    far_end: dict[tuple[int, str], object] = {}
    for s in fs.streams:
        far_end[(id(s.source.owner), s.source.name)] = s.dest.owner
        far_end[(id(s.dest.owner), s.dest.name)] = s.source.owner
    for block in fs.units:
        if not isinstance(block, Block):
            continue
        pin = block.pin_
        turned = int(getattr(pin, "orientation", 0) or 0) in (90, 270)
        faces: dict[str, list] = {}
        for port_name, face in block._faces.items():
            faces.setdefault(face, []).append(far_end.get((id(block), port_name)))
        pitches = []
        for face, peers in faces.items():
            # One connection on a face has no neighbour to crowd.
            if len(peers) < 2:
                continue
            upright = face in ("W", "E")
            pitch = face_pitch(peers, upright != turned)
            if pitch is None:
                continue
            # The box axis the face is drawn along, as Block._check_box
            # reads it: an explicit size is the final box and a quarter
            # turn swaps which of the two a face runs along.
            given = block.width if upright == turned else block.height
            if given is not None:
                pitch = min(pitch, given / len(peers))
            if pitch > BLOCK_PITCH:
                pitches.append((face, pitch))
        block.nozzle_pitches = tuple(sorted(pitches))
