import copy

from pandid import Feed, Flowsheet, Product, Block
from pandid.geometry import Frame, Route
from pandid.render.svg import stream_polyline
from pandid.routing.terminal_clearance import square_interior_micro_jogs


def fixture(manual=False):
    fs = Flowsheet("Native internal jog")
    source, target = fs.add(Feed("source")), fs.add(Product("target"))
    source.frame = Frame(x=-50, y=-10, w=50, h=20)
    target.frame = Frame(x=400, y=140, w=50, h=20)
    stream = fs.connect(source.outlet, target.inlet)
    stream.route = Route(waypoints=[(0, 0), (100, 0), (100, 100),
                                  (200, 100), (200, 101), (300, 101),
                                  (300, 150), (400, 150)], manual=manual)
    return fs, stream


def test_tiny_internal_step_is_squared_with_exact_endpoints_and_is_idempotent():
    fs, stream = fixture()
    before = copy.deepcopy(stream.route.waypoints)
    square_interior_micro_jogs(fs)
    after = stream_polyline(stream)
    assert len(after) < len(before)
    assert after[0] == before[0] and after[-1] == before[-1]
    assert all(a[0] == b[0] or a[1] == b[1] for a, b in zip(after, after[1:]))
    square_interior_micro_jogs(fs)
    assert stream_polyline(stream) == after


def test_authored_tiny_step_is_preserved():
    fs, stream = fixture(manual=True)
    before = copy.deepcopy(stream.route.waypoints)
    square_interior_micro_jogs(fs)
    assert stream.route.waypoints == before


def test_no_flattening_into_equipment_even_for_a_one_unit_move():
    fs, stream = fixture()
    low, high = fs.add(Block("low")), fs.add(Block("high"))
    low.frame = Frame(x=110, y=100.4, w=40, h=20)
    high.frame = Frame(x=240, y=80, w=40, h=20.6)
    before = copy.deepcopy(stream.route.waypoints)
    square_interior_micro_jogs(fs)
    assert stream.route.waypoints == before
