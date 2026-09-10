"""A nearby unrelated body must not consume the router's nozzle escape node."""

import pytest

from pandid import Feed, Flowsheet, Product, Valve
from pandid.geometry import Frame, Route
from pandid.portgeom import port_anchor, unit_box
from pandid.routing import DefaultRouter
from pandid.routing.visibility import Rect, clear_escape_projection


@pytest.mark.parametrize("direction,projection,obstacle,expected", [
    ("E", (25, 0), Rect(20, 100, -10, 10), (10, 0)),
    ("W", (-25, 0), Rect(-100, -20, -10, 10), (-10, 0)),
    ("N", (0, -25), Rect(-10, 10, -100, -20), (0, -10)),
    ("S", (0, 25), Rect(-10, 10, 20, 100), (0, 10)),
])
def test_escape_uses_clear_gap_in_each_port_direction(direction, projection, obstacle, expected):
    actual = clear_escape_projection((0, 0), direction, projection, [obstacle])
    assert actual == expected
    assert not obstacle.intersects_segment(0, 0, *actual)


def test_roomy_escape_and_own_symbol_are_unchanged():
    own = Rect(-24, 0, -10, 10)
    distant = Rect(40, 100, -10, 10)
    assert clear_escape_projection((0, 0), "E", (25, 0), [own, distant]) == (25, 0)


@pytest.mark.parametrize("manual", [False, True])
def test_valve_discharge_routes_before_a_wide_unrelated_flag(manual):
    fs = Flowsheet("Compact continuation")
    valve = fs.add(Valve("HV-01"))
    flag = fs.add(Feed("Reverse cleaning"))
    target = fs.add(Product("Permeate"))
    valve.frame = Frame(x=0, y=0, w=24, h=15)
    flag.frame = Frame(x=184, y=-20, w=190, h=55)
    target.frame = Frame(x=260, y=-120, w=50, h=20)
    stream = fs.connect(valve.outlet, target.inlet)
    start = port_anchor(valve, valve.frame, "outlet")[:2]
    end = port_anchor(target, target.frame, "inlet")[:2]
    authored = [start, (34, start[1]), (34, end[1]), end]
    if manual:
        stream.route = Route(waypoints=authored, manual=True)
    DefaultRouter().route(fs)
    assert stream.route.waypoints[0] == start
    assert stream.route.waypoints[-1] == end
    x0, y0, x1, y1 = unit_box(flag, flag.frame)
    body = Rect(x0, x1, y0, y1)
    for a, b in zip(stream.route.waypoints, stream.route.waypoints[1:]):
        assert not body.intersects_segment(*a, *b), stream.route.waypoints
    if manual:
        assert stream.route.waypoints == authored
