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
