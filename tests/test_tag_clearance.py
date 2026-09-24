"""An equipment or valve tag is never lettered over a line.

The LB TEX template review, revision 05 (item 4), found the pipe into the top of
each ion-exchange vessel running through the vessel's tag, and vertical runs
through valve tags beside it. The review filed it as caption placement, and that
is where it was: the tag search in :meth:`SvgRenderer._tag_item` never looked at
a face a nozzle leaves. An ion exchanger pipes all four -- feed in the side,
treated water out the other, regenerant in the crown, spent regenerant out the
bottom -- so layout had no free face to offer, the tag fell back to ``top``, and
the search was left with the one face and half the vessel's width to slide in.
A tag longer than the vessel is wide cannot clear a pipe dropping onto the
middle of the crown from anywhere in that half width, so it settled for the
least damaging spot on it, which is the pipe.

The router is not at fault. Every tag is placed after the routes are settled,
against the ink they draw (:func:`~pandid.render.svg._ink`), so a line never
arrives after the lettering; the search accepted a position over one.

**No connection of the tag's own is exempt.** A line number may be written in
the run it names (ISO 15519-1 §7.2.5), and its halo breaks that run on purpose.
An equipment tag names the *symbol* and is set beside it, and a halo across its
own nozzle line says the pipe stops short of the vessel it is drawn into. So
every line counts here, the vessel's own crown pipe included.

Where no face and no step along one is clear, the tag keeps the least damaging
spot and the sheet says so, as ``tag-over-line``, from both backends.
"""

import re
import xml.etree.ElementTree as ET

import pytest

from pandid import Flowsheet, units as U
from pandid.devices import IonExchanger
from pandid.render.drawio import _LABEL_SIDE
from pandid.render.svg import SvgRenderer, _ink, _unit_label_box

_TAG_PLATE = re.compile(
    r'<rect x="([-\d.]+)" y="([-\d.]+)" width="([\d.]+)" height="([\d.]+)" fill="white" />\s*'
    r'<text [^>]*>([^<]*)</text>'
)


def _crowned_vessel() -> Flowsheet:
    """The review's vessel, cut down to itself.

    An ion exchanger at the review sheet's size (50 x 100 drawing units, drawn
    61.9 x 123.8 in the master at its 1.2375 scale), piped on all four faces,
    with the regenerant dropping straight onto the middle of the crown.
    ``330-IX-01`` is 67.4 units of plate against a crown 50 wide, so no slide
    within half the crown clears the middle of it.
    """
    fs = Flowsheet("IX crown")
    ix = fs.add(IonExchanger("330-IX-01", width=50, height=100))
    regenerant = fs.add(U.Feed("REGENERANT"))
    feed = fs.add(U.Feed("FEED"))
    treated = fs.add(U.Product("TREATED"))
    spent = fs.add(U.Product("SPENT"))
    ix.pin(x=400, y=300)
    regenerant.pin(port="outlet", x=200, y=200)
    feed.pin(port="outlet", x=200, y=380)
    treated.pin(port="inlet", x=700, y=380)
    spent.pin(port="inlet", x=700, y=580)
    fs.connect(regenerant.outlet, ix.regenerant_in)
    fs.connect(feed.outlet, ix.inlet)
    fs.connect(ix.outlet, treated.inlet)
    fs.connect(ix.spent_regenerant, spent.inlet)
    return fs


def _drawn_tag(svg: str, tag: str) -> "tuple[float, float, float, float]":
    """The plate the sheet laid under *tag*, read off the drawn SVG."""
    body = svg.split('<g id="unit_labels">', 1)[1]
    found = [m for m in _TAG_PLATE.finditer(body) if m.group(5) == tag]
    assert len(found) == 1, f"{tag} drawn {len(found)} times"
    x, y, w, h = (float(found[0].group(i)) for i in range(1, 5))
    return x, y, x + w, y + h


def _lines_under(fs, box) -> "list[str]":
    """Every line whose stroke the plate at *box* covers, named."""
    return sorted(
        line.line or "an instrument connection"
        for line in _ink(fs, "vertical")
        if box[2] > line.x0 and box[0] < line.x1 and box[3] > line.y0 and box[1] < line.y1
    )


def _drawio_tag(fs, tag: str) -> "tuple[float, float, float, float]":
    """Where the editable master letters *tag*, as the same plate.

    The side is read back off the cell's style keys and the step along it off
    the label offset, then set by the sheet's own ``_label_place`` -- so this is
    the box the exporter *said*, in the sheet's terms. An unscaled sheet, so the
    master's units are the drawing's.
    """
    root = ET.fromstring(fs.to_drawio())
    cells = [c for c in root.iter("mxCell") if c.get("value") == tag]
    assert len(cells) == 1, f"{tag} lettered {len(cells)} times in the master"
    style = cells[0].get("style")
    sides = [side for side, keys in _LABEL_SIDE.items() if all(k + ";" in style for k in keys)]
    assert len(sides) == 1, (style, sides)
    geometry = cells[0].find("mxGeometry")
    offset = geometry.find("mxPoint[@as='offset']")
    dx, dy = ((float(offset.get("x", 0)), float(offset.get("y", 0)))
              if offset is not None else (0.0, 0.0))
    x, y, w, h = (float(geometry.get(k)) for k in ("x", "y", "width", "height"))
    lx, ly, anchor, baseline = SvgRenderer()._label_place(sides[0], x, y, w, h)
    return _unit_label_box((lx + dx, ly + dy, anchor, baseline, sides[0], tag))


def test_a_vessel_tag_is_not_lettered_over_the_pipe_into_its_crown():
    fs = _crowned_vessel()
    box = _drawn_tag(fs.to_svg(), "330-IX-01")
    assert _lines_under(fs, box) == [], f"330-IX-01's tag at {box} is over those lines"


def test_the_editable_master_letters_the_tag_where_the_sheet_does():
    fs = _crowned_vessel()
    drawn = _drawn_tag(fs.to_svg(), "330-IX-01")
    assert _drawio_tag(fs, "330-IX-01") == pytest.approx(drawn, abs=0.051)
    assert _lines_under(fs, drawn) == []


def _valve_between_runs(*also: float) -> Flowsheet:
    """330-HV-11 as the review found it: a valve on a horizontal run with a
    vertical run six units off each end, closer together than its tag is long.

    *also* adds further vertical runs at those x positions, which is how the
    last test below takes away every side the tag could step to.
    """
    fs = Flowsheet("valve between runs")
    feed, product = fs.add(U.Feed("IN")), fs.add(U.Product("OUT"))
    valve = fs.add(U.Valve("330-HV-11"))
    feed.pin(port="outlet", x=100, y=300)
    product.pin(port="inlet", x=700, y=300)
    valve.pin(x=390, y=292)
    fs.connect(feed.outlet, valve.inlet)
    fs.connect(valve.outlet, product.inlet)
    for i, x in enumerate((384, 420.5, *also)):
        top, bottom = 30 + 70 * i, 570 - 70 * i
        down = fs.add(U.Feed(f"T{i}"))
        out = fs.add(U.Product(f"B{i}"))
        down.pin(port="outlet", x=100, y=top)
        out.pin(port="inlet", x=700, y=bottom)
        fs.connect(down.outlet, out.inlet).via([(100, top), (x, top), (x, bottom), (700, bottom)])
    return fs


def test_a_valve_tag_steps_off_the_runs_either_side_of_it():
    """Neither face across the run is clear -- both vertical runs pass through
    a tag 67 units long over a valve 24.5 wide -- and the faces along it carry
    the valve's own run. Stepped to the valve's corner, clear of all three."""
    fs = _valve_between_runs()
    drawn = _drawn_tag(fs.to_svg(), "330-HV-11")
    assert _lines_under(fs, drawn) == [], f"330-HV-11's tag at {drawn} is over those lines"
    assert _drawio_tag(fs, "330-HV-11") == pytest.approx(drawn, abs=0.051)
    assert not [w for w in fs.warnings if w.code == "tag-over-line"]


def test_a_tag_with_no_clear_paper_says_so_from_both_backends():
    """Two more runs, through the paper beside each end of the valve, and there
    is nowhere left: the tag keeps the least damaging spot, and the sheet names
    the line under it rather than leaving the reader to find it."""
    fs = _valve_between_runs(340, 465)
    drawn = _drawn_tag(fs.to_svg(), "330-HV-11")
    under = _lines_under(fs, drawn)
    assert under
    svg = [w for w in fs.warnings if w.code == "tag-over-line"]
    assert len(svg) == 1 and svg[0].severity == "warning"
    assert svg[0].message.startswith("330-HV-11's tag is lettered over " + ", ".join(under) + ".")
    fs.to_drawio()
    drawio = [w for w in fs.warnings if w.code == "tag-over-line"]
    assert [w.message for w in drawio] == [svg[0].message]
