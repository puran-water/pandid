from pandid import Feed, Flowsheet, Instrument, Product
from pandid.geometry import Frame, Route
from pandid.routing.body_clearance import repair


def fixture(manual=False):
    fs = Flowsheet("Separated track and balloon")
    source = fs.add(Feed("air"))
    target = fs.add(Product("tank"))
    balloon = fs.add(Instrument("PI-01"))
    source.frame = Frame(x=-50, y=-10, w=50, h=20)
    target.frame = Frame(x=200, y=90, w=50, h=20)
    balloon.frame = Frame(x=95, y=40, w=20, h=20)
    stream = fs.connect(source.outlet, target.inlet)
    stream.route = Route(waypoints=[(0, 0), (100, 0), (100, 100), (200, 100)], manual=manual)
    fs.layout_options.stream_spacing = 14
    return fs, stream


def test_final_track_clears_balloon_without_moving_ports_or_creating_doglegs():
    fs, stream = fixture()
    repair(fs)
    assert stream.route.waypoints == [(0, 0), (81, 0), (81, 100), (200, 100)]
    before = list(stream.route.waypoints)
    repair(fs)
    assert stream.route.waypoints == before


def test_authored_route_is_preserved_even_when_the_author_must_resolve_a_collision():
    fs, stream = fixture(manual=True)
    before = list(stream.route.waypoints)
    repair(fs)
    assert stream.route.waypoints == before


def test_instrument_clearance_prevents_a_pipe_touching_a_signal_terminal():
    fs, stream = fixture()
    # Outside the mathematical box but within the printed stroke: draw.io
    # cut a gap at this terminal, although no pipe crossed the signal there.
    fs.units[2].frame.x = 100.02
    before = list(stream.route.waypoints)
    repair(fs)
    assert stream.route.waypoints == before
    fs.layout_options.instrument_clearance = 4
    repair(fs)
    assert stream.route.waypoints[0] == before[0]
    assert stream.route.waypoints[-1] == before[-1]
    assert stream.route.waypoints[1][0] < fs.units[2].frame.x - 4
    from pandid.containment import route_obstacles
    box = route_obstacles(fs, stream)[2]
    assert box.x_min == fs.units[2].frame.x - 4
    assert not any(box.intersects_segment(*a,*b) for a,b in zip(stream.route.waypoints,stream.route.waypoints[1:]))


def test_narrow_clear_corridor_is_used_when_full_spacing_would_overlap_another_line():
    fs, stream = fixture()
    stream.dest.owner.frame.x = 120
    stream.route.waypoints[-1] = (120, 100)
    source = fs.add(Feed("other-air"))
    target = fs.add(Product("other-tank"))
    source.frame = Frame(x=-50, y=-40, w=50, h=20)
    target.frame = Frame(x=200, y=120, w=50, h=20)
    peer = fs.connect(source.outlet, target.inlet)
    peer.route = Route(waypoints=[(0, -30), (81, -30), (81, 130), (200, 130)], manual=True)
    repair(fs)
    assert stream.route.waypoints == [(0, 0), (88, 0), (88, 100), (120, 100)]
    assert peer.route.waypoints == [(0, -30), (81, -30), (81, 130), (200, 130)]


def test_wide_boundary_flag_keeps_a_corridor_beyond_the_previous_column():
    from pandid import Valve
    from pandid.layout import _seed_slots
    from pandid.layout.coordinates import assign_coordinates
    from pandid.portgeom import unit_box

    fs = Flowsheet("Wide continuation flag")
    valve = fs.add(Valve("HV-01")).pin(col=0, row=0)
    feed = fs.add(Feed("Reverse-cleaning supply")).pin(col=1, row=0)
    fs.layout_options.column_gap = 40
    _seed_slots(fs)
    feed._slot.w = 190
    assign_coordinates(fs)
    assert unit_box(feed, feed.frame)[0] - unit_box(valve, valve.frame)[2] >= 40


def test_repair_can_correct_a_separated_track_that_overshot_its_destination():
    fs, stream = fixture()
    fs.units[2].frame.x = 123
    stream.dest.owner.frame.x = 120
    stream.route.waypoints = [(0, 0), (129, 0), (129, 100), (120, 100)]
    repair(fs)
    assert stream.route.waypoints == [(0, 0), (109, 0), (109, 100), (120, 100)]


def test_inverted_departure_and_independent_body_collision_can_both_be_repaired():
    from pandid.routing.visibility import Rect
    fs, stream = fixture()
    stream.route.waypoints = [(0, 0), (-8, 0), (-8, -40),
                              (100, -40), (100, 100), (200, 100)]
    endpoints = stream.route.waypoints[0], stream.route.waypoints[-1]
    repair(fs)
    points = stream.route.waypoints
    assert (points[0], points[-1]) == endpoints
    assert points[1][0] > points[0][0]
    assert points[-2][0] < points[-1][0]
    for box in (Rect(-50, 0, -10, 10), Rect(95, 115, 40, 60)):
        assert not any(box.intersects_segment(*a, *b) for a, b in zip(points, points[1:]))
    repair(fs)
    assert stream.route.waypoints == points


def test_authored_inverted_departure_remains_an_author_hold():
    fs, stream = fixture(manual=True)
    points = [(0, 0), (-8, 0), (-8, -40), (100, -40), (100, 100), (200, 100)]
    stream.route.waypoints = points[:]
    repair(fs)
    assert stream.route.waypoints == points


def test_collinear_terminal_projection_keeps_square_nozzle_approach():
    from pandid.routing.visibility import Rect
    fs, stream = fixture()
    fs.units[2].frame = Frame(x=250, y=85, w=20, h=30)
    stream.route.waypoints = [(0, 0), (300, 0), (300, 100), (175, 100), (200, 100)]
    before = stream.route.waypoints[:]
    repair(fs)
    points = stream.route.waypoints
    assert points != before
    assert points[0] == before[0] and points[-1] == before[-1]
    assert points[-2] == before[-2]
    assert all(a[0] == b[0] or a[1] == b[1] for a, b in zip(points, points[1:]))
    box = Rect(250, 270, 85, 115)
    assert not any(box.intersects_segment(*a, *b) for a, b in zip(points, points[1:]))


def test_target_body_is_not_a_corridor_before_the_final_nozzle_approach():
    from pandid.routing.visibility import Rect
    fs = Flowsheet("Approach an outlet without cutting through its box")
    source = fs.add(Feed("source"))
    target = fs.add(Product("destination"))
    source.frame = Frame(x=-50, y=-10, w=50, h=20)
    target.frame = Frame(x=100, y=80, w=160, h=80)
    stream = fs.connect(source.outlet, target.inlet)
    stream.route = Route(waypoints=[(0, 0), (170, 0), (170, 112), (75, 112), (75, 120), (100, 120)])
    endpoints = stream.route.waypoints[0], stream.route.waypoints[-1]
    fs.layout_options.stream_spacing = 14
    repair(fs)
    points = stream.route.waypoints
    assert (points[0], points[-1]) == endpoints
    box = Rect(100, 260, 80, 160)
    assert not any(box.intersects_segment(*a, *b) for a, b in zip(points[:-1], points[1:-1]))
