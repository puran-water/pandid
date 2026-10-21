"""Construction-specific process candidates share native and SVG artwork."""
import xml.etree.ElementTree as ET

import pytest

from pandid.profiles.templates import from_template
from pandid.render.house_artwork import ARTWORK
from pandid.render.nameplates import _wrapped
from pandid.render.symbols import default_registry


@pytest.mark.parametrize("key", ["house.basin.concrete", "house.tank.atmospheric_vertical",
                                 "house.filter.cartridge", "house.heater.immersion",
                                 "house.valve.pressure_relief", "house.membrane.pressure_vessel"])
def test_physical_candidates_are_native_units_with_named_ports(key):
    fs = from_template("Construction specimen", [{"key": "sample", "id": "sample", "symbol": key,
                        "label": "100-TK-01", "attributes": {}}], [], metadata={})
    symbol = default_registry.for_unit(fs.units[0])
    assert symbol.ports and ("rect" in ARTWORK[key].drawing or "path" in ARTWORK[key].drawing)
    assert "shape=stencil(" in fs.to_drawio(diagram="p&id")
    assert not any(w.code == "drawio-approximated" for w in fs.warnings)
    ET.fromstring(fs.to_svg())


def test_side_entry_vessel_has_three_distinct_named_flow_connections():
    art = ARTWORK["house.membrane.pressure_vessel"]
    assert {name for name, _, _ in art.anchors} == {"W", "E", "S"}
    assert len({(x, y) for _, x, y in art.anchors}) == 3
    assert "ellipse" not in art.drawing and "roundrect" not in art.drawing
    assert art.qualification == "candidate_requires_template_review"
    assert art.reference_sha256 and art.reference_pages


@pytest.mark.parametrize("value", ["41.37 bar", "2288.87 m²", "17.32 m³/h", "11.52 kW", "4.50 m"])
def test_nameplate_wrap_keeps_value_and_unit_on_one_line(value):
    lines = _wrapped("RATED VALUE " + value + " nominal", 105, 14)
    assert any(value in line for line in lines)
    assert " ".join(lines) == "RATED VALUE " + value + " nominal"
