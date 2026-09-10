"""A crossing-order cycle from grouped parallel services must remain connected."""
import copy
import pytest

from pandid import Feed, Product, Flowsheet
from pandid.geometry import Frame, Route
from pandid.render.crossings import crossing_order
from pandid.render.svg import stream_polyline
from pandid.routing.crossing_clearance import _overlaps, repair


LINES = [
    [(750.3,632),(1036.3,632),(1036.3,447),(1060.3,447)],
    [(500.3,491.5),(807.3,491.5),(807.3,237.5),(852.3,237.5)],
    [(750.3,536.5),(1038.319237886467,536.5),(1038.319237886467,297.5),
     (827.3,297.5),(827.3,267.5),(852.3,267.5)],
    [(750.3,566.5),(827.3,566.5),(827.3,489.5),(852.3,489.5)],
]


def flowsheet(manual=False):
    fs=Flowsheet('Grouped service crossing cycle')
    fs.layout_options.stream_spacing=14
    for i,points in enumerate(LINES):
        a=fs.add(Feed('a'+str(i)))
        b=fs.add(Product('b'+str(i)))
        a.pin(port='outlet',x=points[0][0],y=points[0][1])
        b.pin(port='inlet',x=points[-1][0],y=points[-1][1])
        fs.connect(a.outlet,b.inlet)
    fs.layout()
    for stream,points in zip(fs.streams,LINES):
        stream.route=Route(waypoints=copy.deepcopy(points),manual=manual)
    return fs


def test_automatic_crossing_repair_preserves_nozzles_and_is_idempotent():
    fs=flowsheet()
    assert crossing_order(dict(enumerate(LINES)),5)[1]
    repair(fs)
    lines={i:stream_polyline(s) for i,s in enumerate(fs.streams)}
    assert not crossing_order(lines,5)[1]
    for i,line in lines.items():
        assert line[0]==LINES[i][0] and line[-1]==LINES[i][-1]
        assert all(a[0]==b[0] or a[1]==b[1] for a,b in zip(line,line[1:]))
    repair(fs)
    assert lines=={i:stream_polyline(s) for i,s in enumerate(fs.streams)}


def test_authored_waypoints_remain_held_instead_of_moving_silently():
    fs=flowsheet(manual=True)
    repair(fs)
    assert [s.route.waypoints for s in fs.streams]==LINES
    assert crossing_order(dict(enumerate(LINES)),5)[1]


@pytest.mark.parametrize("manual", [False, True])
@pytest.mark.parametrize("second_track", [100, 100.8])
def test_residual_parallel_overlap_is_repaired_with_or_without_a_lost_crossing_gap(manual, second_track):
    fs = Flowsheet("Residual parallel overlap")
    fs.layout_options.stream_spacing = 14
    before = {}
    for i, y in enumerate((0, 40)):
        source = fs.add(Feed(f"source-{i}"))
        target = fs.add(Product(f"target-{i}"))
        source.frame = Frame(x=-50, y=y-10, w=50, h=20)
        target.frame = Frame(x=200, y=y+90, w=50, h=20)
        stream = fs.connect(source.outlet, target.inlet)
        track = second_track if i else 100
        before[i] = [(0, y), (track, y), (track, y+100), (200, y+100)]
        stream.route = Route(waypoints=copy.deepcopy(before[i]), manual=manual)
    assert _overlaps(before, 14) == 60
    if second_track == 100:
        assert not crossing_order(before, 5)[1]
    else:
        assert crossing_order(before, 5)[1]
    repair(fs)
    after = {i: stream_polyline(s) for i, s in enumerate(fs.streams)}
    if manual:
        assert after == before
    else:
        assert _overlaps(after, 14) == 0
        assert not crossing_order(after, 5)[1]
        for i, points in after.items():
            assert points[0] == before[i][0] and points[-1] == before[i][-1]
        repair(fs)
        assert after == {i: stream_polyline(s) for i, s in enumerate(fs.streams)}
