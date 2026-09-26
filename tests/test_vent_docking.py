"""A vent on a top nozzle stands on that nozzle (owner ruling 2026-09-26).

An open vent to atmosphere piped from a nozzle that can only leave upward is
drawn as it is built: a short stack straight up off the nozzle. The layout
placed it as a free unit in a grid column of its own -- in the degasser
specimen 1750 units east of the tower -- and the router ran the off-gas across
the sheet to it. Keyed on the Vent unit and on its source nozzle's only face
being north, never on what the host is.
"""
import pytest

from pandid import Feed, Flowsheet, Product
from pandid.portgeom import port_faces, port_point
from pandid.profiles.templates import from_template
from pandid import units


def _stood_on(vent, host, port):
    nx, ny = port_point(host, host.frame, port)
    vx, vy = port_point(vent, vent.frame, "inlet")
    return nx, ny, vx, vy


def assert_on_axis(fs, vent, host, port):
    nx, ny, vx, vy = _stood_on(vent, host, port)
    assert vx == pytest.approx(nx, abs=0.01)
    assert 0 < ny - vy <= 40, (ny, vy)
    stream = next(s for s in fs.streams if s.dest.owner is vent)
    xs = {round(x, 2) for x, _ in stream.route.waypoints}
    assert xs == {round(nx, 2)}, stream.route.waypoints


def node(key, symbol, **extra):
    return dict(key=key, id="c-" + key, symbol=symbol, label=key, attributes={}, **extra)


def edge(key, s, t, sp="outlet", tp="inlet"):
    return dict(key=key, id="e-" + key, source=s, target=t, source_port=sp, target_port=tp,
                kind="material", attributes={}, label="")


def test_template_degasser_overhead_vent_stands_on_the_nozzle():
    nodes = [node("water", "boundary"), node("air", "boundary"),
             node("blower", "stencil.pid.pumps.gas_blower"),
             node("tower", "stencil.pid.vessels.tower_with_packing", n_feeds=2),
             node("vent", "stencil.pid.fittings.vent"), node("treated", "boundary")]
    edges = [edge("liquid", "water", "tower", tp="feed_1"), edge("suction", "air", "blower"),
             edge("air-in", "blower", "tower", tp="feed_2"),
             edge("offgas", "tower", "vent", sp="overhead"),
             edge("out", "tower", "treated", sp="bottoms")]
    fs = from_template("Degasser", nodes, edges, metadata={})
    fs.to_drawio(diagram="pfd")
    by = {u.name: u for u in fs.units}
    assert_on_axis(fs, by["vent"], by["tower"], "overhead")


@pytest.mark.parametrize("variant", ["default", "breather", "exhaust_head"])
def test_every_vent_variant_stands_on_a_top_nozzle(variant):
    fs = Flowsheet("Stripper")
    tower = fs.add(units.Stripper("D-1", variant="packed"))
    vent = fs.add(units.Vent("VT-1", variant=variant))
    fs.connect(fs.add(Feed("in")).outlet, tower.feed)
    fs.connect(tower.overhead, vent.inlet)
    fs.connect(tower.bottoms, fs.add(Product("out")).inlet)
    assert port_faces(tower, "overhead") == ["N"]
    fs.layout()
    fs.route()
    assert_on_axis(fs, vent, tower, "overhead")
    first = vent.frame
    fs.layout()
    assert vent.frame == first  # laid out twice, drawn twice the same


def test_a_vent_off_a_side_nozzle_keeps_its_place_in_the_grid():
    fs = Flowsheet("Side")
    pump = fs.add(units.Pump("P-1"))
    vent = fs.add(units.Vent("VT-1"))
    fs.connect(fs.add(Feed("in")).outlet, pump.suction)
    fs.connect(pump.discharge, vent.inlet)
    assert port_faces(pump, "discharge") != ["N"]
    fs.layout()
    assert vent.frame.col is not None


def test_a_pinned_vent_is_where_the_author_put_it():
    fs = Flowsheet("Pinned")
    tower = fs.add(units.Stripper("D-1", variant="packed"))
    vent = fs.add(units.Vent("VT-1"))
    fs.connect(fs.add(Feed("in")).outlet, tower.feed)
    fs.connect(tower.overhead, vent.inlet)
    vent.pin(col=3, row=0)
    fs.layout()
    assert vent.frame.col == 3
