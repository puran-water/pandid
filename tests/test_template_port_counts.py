"""A template row declares a unit's variable port count, as a spec entry does.

The spec format has long read ``n_feeds`` on a Column or a Reactor (and so on
every subclass: Absorber, Stripper, DistillationColumn). The template adapter
built units from a symbol and its incoming/outgoing edge counts alone, so a
template could not ask for a second feed nozzle: a packed tower taking liquid
and air on two nozzles had both edges resolved to its one ``feed_1`` and was
refused as a duplicate physical port.
"""
import xml.etree.ElementTree as ET

import pytest

from pandid.portgeom import port_point
from pandid.profiles.templates import from_template
from pandid.units import Absorber, Column

PACKED = "stencil.pid.vessels.tower_with_packing"
SHELL = "stencil.pid.vessels.pressurized_vessel"


def node(key, symbol, **extra):
    return dict(key=key, id=key, symbol=symbol, label=key, attributes={}, **extra)


def edge(key, source, target, sp="outlet", tp="inlet", kind="material"):
    return dict(key=key, id=key, source=source, target=target, source_port=sp,
                target_port=tp, kind=kind, attributes={"semantic-path": key}, label="")


def tower_sheet(tower):
    """Liquid to ``feed_1``, air to ``feed_2``; offgas overhead, water from bottoms."""
    nodes = [node("liquid", "boundary"), node("air", "boundary"), tower,
             node("offgas", "boundary"), node("water", "boundary")]
    edges = [edge("liquid-in", "liquid", "tower", tp="feed_1"),
             edge("air-in", "air", "tower", tp="feed_2"),
             edge("offgas-out", "tower", "offgas", sp="overhead"),
             edge("water-out", "tower", "water", sp="bottoms")]
    return nodes, edges


def assert_two_feeds_connected(fs, cls):
    tower = next(u for u in fs.units if u.name == "tower")
    assert type(tower) is cls
    assert [p.name for p in tower.feeds] == ["feed_1", "feed_2"]
    dest = {s.name: s.dest for s in fs.streams}
    assert dest["liquid-in"] is tower.feed_1
    assert dest["air-in"] is tower.feed_2
    fs.layout()
    top = port_point(tower, tower.frame, "feed_1")[1]
    below = port_point(tower, tower.frame, "feed_2")[1]
    # Declaration order is top of the shell to bottom (Column's docstring).
    assert top < below
    xml = ET.fromstring(fs.to_drawio(diagram="pfd"))
    assert all(xml.find(f".//object[@id='{key}']") is not None
               for key in ("liquid-in", "air-in", "offgas-out", "water-out"))
    return tower


def test_template_column_declares_two_feeds_and_each_connects():
    nodes, edges = tower_sheet(node("tower", PACKED, n_feeds=2))
    fs = from_template("Packed tower", nodes, edges, metadata={})
    tower = assert_two_feeds_connected(fs, Column)
    assert tower.variant == "packed"


def test_template_absorber_declares_two_feeds_and_each_connects():
    nodes, edges = tower_sheet(node("tower", SHELL, engine_unit="Absorber", n_feeds=2))
    fs = from_template("Absorber", nodes, edges, metadata={})
    assert_two_feeds_connected(fs, Absorber)


def test_undeclared_count_keeps_the_single_feed_column():
    nodes = [node("liquid", "boundary"), node("tower", PACKED), node("water", "boundary")]
    edges = [edge("in", "liquid", "tower", tp="feed_1"), edge("out", "tower", "water", sp="bottoms")]
    fs = from_template("One feed", nodes, edges, metadata={})
    tower = next(u for u in fs.units if u.name == "tower")
    assert type(tower) is Column and [p.name for p in tower.feeds] == ["feed_1"]
    assert fs.streams[0].dest is tower.feed_1


def test_count_on_a_class_without_that_family_is_refused():
    nodes = [node("pump", "pump.centrifugal", n_feeds=2)]
    with pytest.raises(ValueError, match="PANDID_PORT_COUNT_UNSUPPORTED: pump/n_feeds"):
        from_template("Refused", nodes, [], metadata={})


def test_count_on_an_untyped_appearance_is_refused():
    nodes = [node("pkg", "process.package", n_feeds=2)]
    with pytest.raises(ValueError, match="PANDID_PORT_COUNT_UNSUPPORTED: pkg/n_feeds"):
        from_template("Refused", nodes, [], metadata={})


@pytest.mark.parametrize("value", [0, True, "2", 2.0])
def test_count_must_be_a_positive_integer(value):
    nodes = [node("tower", PACKED, n_feeds=value)]
    with pytest.raises(ValueError, match="n_feeds"):
        from_template("Refused", nodes, [], metadata={})


def test_engine_unit_must_refine_the_symbols_own_class():
    nodes = [node("tower", PACKED, engine_unit="Pump")]
    with pytest.raises(ValueError, match="PANDID_ENGINE_UNIT_MISMATCH: tower"):
        from_template("Refused", nodes, [], metadata={})
