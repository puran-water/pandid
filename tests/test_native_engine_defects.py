"""Nozzle geometry must survive repair and the native stencil's own scaling."""

import base64
import importlib.util
from pathlib import Path
import xml.etree.ElementTree as ET
import zlib

import pytest

from pandid import Flowsheet, units
from pandid.geometry import Frame, Route
from pandid.portgeom import port_anchor, port_point
from pandid.profiles.process import apply
from pandid.render.svg import stream_polyline
from pandid.render.symbols import Symbol, default_registry
from pandid.routing.terminal_clearance import protect, square_micro_jogs


def _style(cell):
    return dict(item.split("=", 1) for item in cell.get("style", "").split(";") if "=" in item)


@pytest.mark.parametrize("size", [(180, 120), (90, 240)])
@pytest.mark.parametrize("turn", [0, 90, 180, 270])
@pytest.mark.parametrize("mirror", [False, "x", "y", "xy"])
@pytest.mark.parametrize("diagram", ["pfd", "p&id"])
def test_fixed_stencil_connection_and_routed_nozzle_agree_on_a1(size, turn, mirror, diagram):
    fs = apply(Flowsheet("Fixed stencil nozzle"))
    source = fs.add(units.Block("AIR", width=60, height=40)).pin(x=100, y=300)
    lift = fs.add(units.Airlift("250-AL-01", width=size[0], height=size[1]))
    lift.pin(x=400, y=300, orientation=turn, mirrored=mirror)
    line = fs.connect(source.outlets[0], lift.air_in)
    line.display_label = ""
    root = ET.fromstring(fs.to_drawio(diagram=diagram, page_size="A1", border="zone"))
    cell = root.find(".//mxCell[@id='u1']")
    geometry, style = cell.find("mxGeometry"), _style(cell)
    edge = _style(root.find(".//mxCell[@id='s0']"))
    encoded = style["shape"][len("stencil("):-1]
    stencil = ET.fromstring(zlib.decompress(base64.b64decode(encoded), -15))
    assert stencil.get("aspect") == "fixed"
    assert stencil.findall(".//quad"), "this is the artwork the SVG scaler could not read"

    # Native connection fractions use mxCellState.getPerimeterBounds: the
    # fixed stencil's centred rectangle, after a quarter turn exchanges axes.
    # Measure that independently of the engine's port and ink-box helpers.
    sw, sh = float(stencil.get("w")), float(stencil.get("h"))
    if style.get("direction") in {"north", "south"}:
        sw, sh = sh, sw
    x, y, w, h = (float(geometry.get(k)) for k in ("x", "y", "width", "height"))
    scale = min(w / sw, h / sh)
    iw, ih = sw * scale, sh * scale
    fx, fy = float(edge["entryX"]), float(edge["entryY"])
    flip_h, flip_v = style.get("flipH") == "1", style.get("flipV") == "1"
    if style.get("direction") in {"north", "south"}:
        flip_h, flip_v = flip_v, flip_h
    if flip_h:
        fx = 1 - fx
    if flip_v:
        fy = 1 - fy
    native = (x + (w - iw) / 2 + fx * iw, y + (h - ih) / 2 + fy * ih)
    px, py = port_point(lift, lift.frame, "air_in")
    expected = (x + (px - lift.frame.x) * w / lift.frame.w,
                y + (py - lift.frame.y) * h / lift.frame.h)
    assert native == pytest.approx(expected, abs=1e-4)
    assert line.route.waypoints[-1] == port_anchor(lift, lift.frame, "air_in")[:2]
    points = stream_polyline(line)
    assert all(a[0] == b[0] or a[1] == b[1] for a, b in zip(points, points[1:]))


class _InsetNozzle(units.Unit):
    kind = "inset_nozzle_test_unit"
    PORTS = [("inlet", "inlet", "process")]

    def symbol(self):
        return Symbol(svg='<g><rect x="10" y="0" width="90" height="40"/></g>',
                      width=100, height=40, ports={"inlet": (10, 20)})


@pytest.mark.parametrize("manual", [False, True])
def test_terminal_repair_keeps_inset_nozzles_and_routing_anchors_distinct(manual, monkeypatch):
    fs = Flowsheet("Inset nozzle")
    fs._drawn_as = "pfd"
    source = fs.add(units.Feed("F"))
    source.frame = Frame(x=0, y=0, w=50, h=40)
    target = fs.add(_InsetNozzle("V"))
    monkeypatch.setitem(default_registry._symbols, (target.kind, "default"), target.symbol())
    target.frame = Frame(x=300, y=100, w=100, h=40)
    stream = fs.connect(source.outlet, target.inlet)
    original = [(50, 20), (290, 20), (290, 120), (300, 120)]
    stream.route = Route(waypoints=list(original), manual=manual)
    square_micro_jogs(fs)
    assert stream.route.waypoints == original
    protect(fs)
    if manual:
        assert stream.route.waypoints == original
    else:
        assert stream.route.waypoints[1:-1] != original[1:-1]
        assert stream.route.waypoints[-1] == (300, 120)
        assert stream_polyline(stream)[-1] == (310, 120)
        assert stream_polyline(stream)[-2][0] <= 286


def test_house_generator_preserves_each_stencils_aspect(monkeypatch):
    root = Path(__file__).resolve().parents[1]
    monkeypatch.syspath_prepend(str(root / "scripts"))
    spec = importlib.util.spec_from_file_location("_house_generator", root / "scripts/house_symbols.py")
    generator = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(generator)
    assert generator.render() == (root / "pandid/render/_house_symbols.py").read_text()
    for key, (kind, variant, _) in generator.KINDS.items():
        assert default_registry.get(kind, variant).stretchable == (
            generator.ARTWORK[key].aspect == "variable")


@pytest.mark.parametrize("tag,area", [("250-FIT-01", "250"), ("250-FIT-01", ""), ("FIT-01", "")])
def test_balloon_area_corroborates_the_element_in_both_entrypoints(tag, area):
    fs = Flowsheet("Element identity")
    element = fs.add(units.Fitting(tag, variant="magnetic"))
    with pytest.raises(ValueError, match="area"):
        fs.add_balloon(element, area="999")
    assert element.balloon is None
    balloon = fs.add_balloon(element, area=area)
    assert balloon.tag == element.name == tag
    assert element.tag == ""
    spec = fs.to_dict()
    spec["instruments"][0]["area"] = "999"
    with pytest.raises(ValueError, match="area"):
        Flowsheet.from_dict(spec)
    spec["instruments"][0]["area"] = area
    assert Flowsheet.from_dict(spec).units[-1].tag == tag
