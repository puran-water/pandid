"""A packed tower's two feeds (owner rulings 2026-09-26).

A counter-current packed tower takes its liquid above the packing and its gas
below it, on opposite faces so the two lines do not cross. On the packed
artwork (``column/packed``) the even spread put both nozzles inside the beds,
on the west face. For exactly two feeds on that artwork, ``feed_1`` now sits on
the west face above the top bed and ``feed_2`` on the east face below the
bottom bed, both read off the artwork's own bed extents.
"""
import re

import pytest

from pandid import Flowsheet, Feed, Product
from pandid.portgeom import port_faces, port_point
from pandid.profiles.templates import from_template
from pandid.render.symbols import default_registry
from pandid import units

PACKED = "stencil.pid.vessels.tower_with_packing"


def artwork_rules():
    """The packed artwork's horizontal rules, read from its own SVG path."""
    sym = default_registry.get("column", "packed")
    scale = float(re.search(r"scale\([\d.]+, ([\d.]+)\)", sym.svg).group(1))
    ys = sorted({float(a) * scale for a, b in
                 re.findall(r"M 0\.0 ([\d.]+) L 14\.0 ([\d.]+)", sym.svg) if a == b})
    # Outermost rules are the two head seams; the rest pair up into beds.
    seams, inner = (ys[0], ys[-1]), ys[1:-1]
    beds = list(zip(inner[::2], inner[1::2]))
    return seams, beds


def placed(unit, name):
    fs = Flowsheet("probe")
    fs.add(unit)
    for i, port in enumerate(unit.feeds):
        fs.connect(fs.add(Feed(f"F{i}")).outlet, port)
    fs.layout()
    x, y = port_point(unit, unit.frame, name)
    return x - unit.frame.x, y - unit.frame.y, port_faces(unit, name)


@pytest.mark.parametrize("cls", [units.Column, units.Absorber])
def test_two_feeds_on_packed_artwork_straddle_the_beds_on_opposite_faces(cls):
    (top_seam, bottom_seam), beds = artwork_rules()
    assert len(beds) == 2
    tower = cls("T-1", n_feeds=2, variant="packed")
    x1, y1, faces1 = placed(tower, "feed_1")
    tower = cls("T-1", n_feeds=2, variant="packed")
    x2, y2, faces2 = placed(tower, "feed_2")
    assert faces1 == ["W"] and x1 == 0
    assert faces2 == ["E"] and x2 == pytest.approx(62.0)
    assert top_seam < y1 < beds[0][0]
    assert beds[-1][1] < y2 < bottom_seam


def test_the_packed_symbol_states_its_beds_from_its_own_artwork():
    seams, beds = artwork_rules()
    sym = default_registry.get("column", "packed")
    flat = [v for bed in sym.beds for v in bed]
    assert flat == pytest.approx([v for bed in beds for v in bed], abs=0.01)
    assert list(sym.shell) == pytest.approx(list(seams), abs=0.01)


@pytest.mark.parametrize("n", [1, 3])
def test_other_feed_counts_keep_the_even_spread_on_the_west_face(n):
    tower = units.Column("T-1", n_feeds=n, variant="packed")
    for p in tower.feeds:
        x, _y, faces = placed(units.Column("T-1", n_feeds=n, variant="packed"), p.name)
        assert faces == ["W"] and x == 0


def test_a_stripper_keeps_its_boilup_nozzle_and_the_even_spread():
    # A Stripper's vapour already enters on boilup_in, east and below the bed.
    tower = units.Stripper("T-1", n_feeds=2, variant="packed")
    _x, _y, faces = placed(tower, "feed_2")
    assert faces == ["W"]


def _segments(stream):
    pts = stream.route.waypoints
    return list(zip(pts, pts[1:]))


def _cross(a, b):
    (p1, p2), (q1, q2) = a, b
    def orient(p, q, r):
        v = (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])
        return (v > 1e-9) - (v < -1e-9)
    return (orient(p1, p2, q1) * orient(p1, p2, q2) < 0
            and orient(q1, q2, p1) * orient(q1, q2, p2) < 0)


def node(key, symbol, **extra):
    return dict(key=key, id="c-" + key, symbol=symbol, label=key, attributes={}, **extra)


def edge(key, s, t, sp="outlet", tp="inlet"):
    return dict(key=key, id="e-" + key, source=s, target=t, source_port=sp, target_port=tp,
                kind="material", attributes={}, label="")


def test_template_degasser_on_packed_artwork_puts_air_east_and_nothing_crosses():
    nodes = [node("water", "boundary"), node("air", "boundary"),
             node("blower", "stencil.pid.pumps.gas_blower"),
             node("tower", PACKED, n_feeds=2), node("offgas", "boundary"),
             node("treated", "boundary")]
    edges = [edge("liquid", "water", "tower", tp="feed_1"),
             edge("suction", "air", "blower"),
             edge("air-in", "blower", "tower", tp="feed_2"),
             edge("vent", "tower", "offgas", sp="overhead"),
             edge("out", "tower", "treated", sp="bottoms")]
    fs = from_template("Degasser", nodes, edges, metadata={})
    fs.to_drawio(diagram="pfd")
    by = {u.name: u for u in fs.units}
    assert by["blower"].frame.x > by["tower"].frame.x
    streams = {s.name: s for s in fs.streams}
    liquid, air = _segments(streams["liquid"]), _segments(streams["air-in"])
    assert not any(_cross(a, b) for a in liquid for b in air)
