"""The house packed degasser symbol and its reach from a template row."""
from pandid.portgeom import port_faces
from pandid.profiles.templates import from_template, symbol_type
from pandid.render.house_artwork import ARTWORK
from pandid import units

DEGASSER = "house.degasser.packed_tower"


def node(key, symbol, **extra):
    return dict(key=key, id="c-" + key, symbol=symbol, label=key, attributes={}, **extra)


def edge(key, s, t, sp="outlet", tp="inlet"):
    return dict(key=key, id="e-" + key, source=s, target=t, source_port=sp, target_port=tp,
                kind="material", attributes={}, label="")


def test_house_degasser_artwork_anchors():
    art = ARTWORK[DEGASSER]
    anchors = {name: (x, y) for name, x, y in art.anchors}
    assert set(anchors) == {"liquid_in", "air_in", "offgas", "outlet"}
    assert anchors["liquid_in"][0] == 0 and anchors["air_in"][0] == 1
    assert anchors["offgas"] == (0.5, 0) and anchors["outlet"] == (0.5, 1)
    assert anchors["liquid_in"][1] < art.bed[0] / art.height
    assert anchors["air_in"][1] > art.bed[1] / art.height
    assert "review" in art.qualification


def test_house_degasser_is_reachable_from_a_template_row():
    assert symbol_type(DEGASSER) == ("degasser", "default")
    nodes = [node("water", "boundary"), node("air", "boundary"),
             node("tower", DEGASSER), node("offgas", "boundary"), node("treated", "boundary")]
    edges = [edge("liquid", "water", "tower", tp="liquid_in"),
             edge("air-in", "air", "tower", tp="air_in"),
             edge("vent", "tower", "offgas", sp="offgas"),
             edge("out", "tower", "treated", sp="outlet")]
    fs = from_template("House degasser", nodes, edges, metadata={})
    tower = next(u for u in fs.units if u.name == "tower")
    assert type(tower) is units.Degasser
    ends = {s.name: (s.source.name, s.dest.name) for s in fs.streams}
    assert ends == {"liquid": ("outlet", "liquid_in"), "air-in": ("outlet", "air_in"),
                    "vent": ("offgas", "inlet"), "out": ("outlet", "inlet")}
    xml = fs.to_drawio(diagram="pfd")
    assert "shape=stencil(" in xml
    fs.layout()
    assert port_faces(tower, "liquid_in") == ["W"] and port_faces(tower, "air_in") == ["E"]
    assert port_faces(tower, "offgas") == ["N"] and port_faces(tower, "outlet") == ["S"]


def test_house_degasser_draws_its_blower_east_and_the_lines_do_not_cross():
    nodes = [node("water", "boundary"), node("air", "boundary"),
             node("blower", "stencil.pid.pumps.gas_blower"), node("tower", DEGASSER),
             node("offgas", "boundary"), node("treated", "boundary")]
    edges = [edge("liquid", "water", "tower", tp="liquid_in"), edge("suction", "air", "blower"),
             edge("air-in", "blower", "tower", tp="air_in"),
             edge("vent", "tower", "offgas", sp="offgas"), edge("out", "tower", "treated", sp="outlet")]
    fs = from_template("House degasser", nodes, edges, metadata={})
    fs.to_drawio(diagram="pfd")
    by = {u.name: u for u in fs.units}
    assert by["blower"].frame.x > by["tower"].frame.x
    route = {s.name: s.route.waypoints for s in fs.streams}

    def orient(p, q, r):
        v = (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])
        return (v > 1e-9) - (v < -1e-9)

    def cross(a, b):
        (p1, p2), (q1, q2) = a, b
        return (orient(p1, p2, q1) * orient(p1, p2, q2) < 0
                and orient(q1, q2, p1) * orient(q1, q2, p2) < 0)

    seg = lambda pts: list(zip(pts, pts[1:]))
    assert not any(cross(a, b) for a in seg(route["liquid"]) for b in seg(route["air-in"]))
