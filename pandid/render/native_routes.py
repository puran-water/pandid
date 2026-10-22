"""Native edge geometry, shared by routing clearance and draw.io export."""


def stream_polyline(stream):
    from pandid.portgeom import unit_box
    from pandid.render.svg import stream_polyline as drawn_polyline

    points = drawn_polyline(stream)
    if not points:
        return points
    for reverse, unit in ((False, stream.source.owner), (True, stream.dest.owner)):
        if unit.kind not in {'tee', 'junction'}:
            continue
        if reverse:
            points.reverse()
        x0, y0, x1, y1 = unit_box(unit, unit.frame)
        point = ((x0+x1)/2, points[0][1] if unit.kind == 'junction' and unit.is_header else (y0+y1)/2)
        if point != points[0]:
            points.insert(0, point)
        if reverse:
            points.reverse()
    simplified = []
    for point in points:
        if simplified and point == simplified[-1]:
            continue
        while len(simplified) >= 2 and (
            simplified[-2][0] == simplified[-1][0] == point[0]
            or simplified[-2][1] == simplified[-1][1] == point[1]
        ):
            simplified.pop()
        simplified.append(point)
    return simplified
