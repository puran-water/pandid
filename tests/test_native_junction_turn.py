from pandid import Flowsheet, Junction, Product
from pandid.geometry import Frame, Route
from pandid.render.drawio import DrawioRenderer


def test_native_header_keeps_a_square_lead_when_route_turns_at_box():
    fs = Flowsheet("Header terminal turn")
    header = fs.add(Junction("header", inputs=1, outputs=2, header=True))
    target = fs.add(Product("target"))
    header.frame = Frame(x=100, y=100, w=4, h=60)
    target.frame = Frame(x=300, y=240, w=50, h=20)
    stream = fs.connect(header.outlets[1], target.inlet)
    stream.route = Route(waypoints=[(104, 145), (104, 180), (250, 180), (250, 250), (300, 250)])
    points = DrawioRenderer()._native_stream_polyline(stream)
    assert points[:3] == [(102, 145), (104, 145), (104, 180)]
    assert points[-1] == (300, 250)
    assert all(a[0] == b[0] or a[1] == b[1] for a, b in zip(points, points[1:]))
