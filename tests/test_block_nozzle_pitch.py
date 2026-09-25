"""A block spreads runs that carry tagged valves far enough apart for the tags.

The LB TEX template review, revision 05, left ten IX valve tags over lines once
the tag search had tried every face (see ``tests/test_tag_clearance.py``). Each
IX vessel sheet fans a shared selector out to three vessels through one valve
per vessel, and layout lines each valve up with the selector nozzle its run
leaves from. The nozzles were :data:`~pandid.render.symbols.BLOCK_PITCH` (30
units) apart, a pitch derived from the arrowhead, so the valves stood in rows 30
apart and every tag but the outermost had only the gap between two runs to go
in -- narrower than the tag. The owner ruled the fix is the row pitch (2026-09-25):
widen the rows, measured from the tag, not a gate and not an acceptance.
"""

import re

import pytest

from pandid import Flowsheet, units as U
from pandid.portgeom import port_point
from pandid.profiles.process import apply, lettering
from pandid.render.svg import _PLATE_CLEARANCE, _ink
from pandid.render.symbols import BLOCK_PITCH
from pandid.render.weights import LineWeight

_TAG_PLATE = re.compile(
    r'<rect x="([-\d.]+)" y="([-\d.]+)" width="([\d.]+)" height="([\d.]+)" fill="white" />\s*'
    r'<text [^>]*>([^<]*)</text>'
)


def _selector(body: float, *, valves: bool = True, height=None) -> Flowsheet:
    """A shared service selector fanned out to three vessels, as on the IX sheets."""
    fs = apply(Flowsheet("IX selector"))
    feed = fs.add(U.Feed("FEED"))
    selector = fs.add(U.Block("SERVICE SELECTOR", inputs=1, outputs=3,
                              label_pos="center", height=height))
    fs.connect(feed.outlet, selector.in_1)
    for i in range(3):
        vessel = fs.add(U.Product(f"VESSEL {i + 1}"))
        if valves:
            valve = fs.add(U.Valve(f"330-HV-0{i + 1}"))
            fs.connect(selector.outlets[i], valve.inlet)
            fs.connect(valve.outlet, vessel.inlet)
        else:
            fs.connect(selector.outlets[i], vessel.inlet)
    lettering(fs, body=body, heading=body)
    return fs


def _drawn_tags(svg: str) -> "dict[str, tuple[float, float, float, float]]":
    body = svg.split('<g id="unit_labels">', 1)[1]
    out = {}
    for m in _TAG_PLATE.finditer(body):
        x, y, w, h = (float(m.group(i)) for i in range(1, 5))
        out[m.group(5)] = (x, y, x + w, y + h)
    return out


def _rows(fs) -> "list[float]":
    return sorted(u.frame.y + u.frame.h / 2 for u in fs.units if u.kind == "valve")


@pytest.mark.parametrize("body", [12, 17, 24])
def test_no_valve_tag_on_a_selector_fan_is_lettered_over_a_line(body):
    fs = _selector(body)
    svg = fs.to_svg(check=False)
    over = [w.message for w in fs.warnings if w.code == "tag-over-line"]
    assert over == []
    tags = _drawn_tags(svg)
    ink = _ink(fs, "vertical")
    for name in ("330-HV-01", "330-HV-02", "330-HV-03"):
        box = tags[name]
        assert not [line.line for line in ink
                    if box[2] > line.x0 and box[0] < line.x1
                    and box[3] > line.y0 and box[1] < line.y1], name


@pytest.mark.parametrize("body", [12, 17, 24])
def test_the_valve_rows_are_pitched_from_the_tag_they_have_to_hold(body):
    """Row pitch = the tag's reach past its own run + the next valve's half
    depth + the plate clearance a label keeps off a symbol. Measured off the
    drawn sheet, so the pitch is shown to follow the lettering rather than to
    be some number that happens to clear it at one size."""
    fs = _selector(body)
    tags = _drawn_tags(fs.to_svg(check=False))
    rows = _rows(fs)
    pitches = [b - a for a, b in zip(rows, rows[1:])]
    assert pitches[0] == pytest.approx(pitches[1])
    assert pitches[0] > BLOCK_PITCH

    middle = next(u for u in fs.units if u.name == "330-HV-02")
    centre = middle.frame.y + middle.frame.h / 2
    box = tags["330-HV-02"]
    reach = max(centre - box[1], box[3] - centre)
    neighbour = middle.frame.h / 2 + LineWeight.EQUIPMENT.width / 2 + _PLATE_CLEARANCE
    # The sheet writes a plate to a tenth of a unit, so the read-back is good
    # to that and no better.
    assert pitches[0] == pytest.approx(reach + neighbour, abs=0.15)


def test_a_larger_lettering_size_widens_the_rows():
    def pitch(body):
        fs = _selector(body)
        fs.to_svg(check=False)
        rows = _rows(fs)
        return rows[1] - rows[0]

    assert pitch(12) < pitch(17) < pitch(24)


def test_a_fan_with_no_tagged_valve_keeps_the_block_pitch():
    fs = _selector(17, valves=False)
    fs.to_svg(check=False)
    selector = next(u for u in fs.units if u.kind == "block")
    assert selector.nozzle_pitches == ()
    ports = sorted(port_point(selector, selector.frame, port.name)[1]
                   for port in selector.outlets)
    assert [b - a for a, b in zip(ports, ports[1:])] == pytest.approx([BLOCK_PITCH] * 2)


def test_an_author_sized_block_keeps_its_size():
    """An explicit height wins, as it does everywhere else a block is sized:
    the pitch grows only as far as the given box allows, and nothing is
    refused."""
    fs = _selector(17, height=100)
    fs.to_svg(check=False)
    selector = next(u for u in fs.units if u.kind == "block")
    assert selector.frame.h == pytest.approx(100)
    assert dict(selector.nozzle_pitches)["E"] == pytest.approx(100 / 3)
