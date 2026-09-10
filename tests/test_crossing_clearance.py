"""A crossing-order cycle from grouped parallel services must remain connected."""
import copy

from pandid import Feed, Product, Flowsheet
from pandid.geometry import Route
from pandid.render.crossings import crossing_order
from pandid.render.svg import stream_polyline
from pandid.routing.crossing_clearance import repair


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
