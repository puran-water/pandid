"""Placing the boundary rails against the band a fixed page leaves.

Hanging the rails off the core's own extent puts them wherever the content
happens to end, and a fixed page then centres the whole drawing in the band left
for it -- so the flags land mid-sheet however much paper is free. On the
2026-09-10 house library that was 34 to 279 mm of clearance and no sheet reached
the band.

The mechanism is exercised here but is not yet switched on in the process
profile: see the note in ``profiles.process.apply``.
"""

import xml.etree.ElementTree as ET

import pytest

from pandid import Flowsheet
from pandid.profiles import process as P
from pandid.profiles.process import ESCAPE_LANE
from pandid.render.drawio import fitted_band
from pandid.units import Feed, Product, Pump, Tank

INNER_EXPORTED = 26.0 * 2.8125   # furniture units are drawn at print_scale


def station():
    fs = Flowsheet("Band probe")
    src = fs.add(Feed("raw", reference="A"))
    tank = fs.add(Tank("T-01"))
    pump = fs.add(Pump("P-01"))
    out = fs.add(Product("permeate", reference="B"))
    fs.connect(src.outlet, tank.inlet, name="L-001")
    fs.connect(tank.outlet, pump.suction, name="L-002")
    fs.connect(pump.discharge, out.inlet, name="L-003")
    P.apply(fs)
    return fs


def flags_and_band(fs):
    xml = fs.to_drawio(diagram="p&id", page_size="A1", border="zone")
    page = ET.fromstring(xml).find("diagram")
    frame, flags = None, []
    for cell in page.iter("mxCell"):
        geo = cell.find("mxGeometry")
        if geo is None or geo.get("x") is None:
            continue
        box = (float(geo.get("x")), float(geo.get("width") or 0))
        if "offPageConnector" in (cell.get("style") or ""):
            flags.append(box)
        if box[1] > 3000:
            frame = box
    assert frame and flags
    return flags, (frame[0] + INNER_EXPORTED, frame[0] + frame[1] - INNER_EXPORTED)


def test_rails_hang_off_the_core_when_no_page_is_named():
    fs = station()
    fs.layout_options.boundary_page = None
    fs.layout()
    flags, (band_l, band_r) = flags_and_band(fs)
    assert min(b[0] for b in flags) - band_l > 500      # far inboard
    assert band_r - max(b[0] + b[1] for b in flags) > 500


def test_rails_meet_the_band_less_the_escape_lane_when_the_page_is_named():
    """The flags span the band less one escape lane, and the band is the one
    both writers leave -- which for a page carrying no furniture is five units
    inside the dock's own, so asserting against the frame would be asserting
    the wrong band.

    The lane is not slack. Rails hung on the last unit of the band leave no
    paper for ink that sits outside the equipment -- a route corner, a leader,
    the approach to a flag -- and on 2026-09-11 that made four of twenty-one
    LB TEX families refuse to export. ``_filled_gap`` already withheld exactly
    this much when spending a band's spare paper; the rails are now the second
    place it is withheld, which is what makes the two agree."""
    fs = station()
    fs.layout_options.boundary_page = "A1"
    fs.layout()
    flags, (band_l, band_r) = flags_and_band(fs)
    width, _height = fitted_band(fs, "A1")
    scale = fs.drawing_scale * fs.print_scale * 100 / 96
    exported = (width - ESCAPE_LANE) * scale

    span = max(b[0] + b[1] for b in flags) - min(b[0] for b in flags)
    assert span == pytest.approx(exported, abs=1.0)
    # Centred in the frame's band, so the inset is equal either side.
    assert (min(b[0] for b in flags) - band_l) == pytest.approx(
        band_r - max(b[0] + b[1] for b in flags), abs=1.0)
    # At least half a lane, because that is what the rails withheld, and not
    # much more than it: the remainder is the margin the plain writer keeps
    # over the dock's band (see the docstring), not the rails drifting back
    # toward the middle of the sheet the way they used to by 500-plus.
    inset = min(b[0] for b in flags) - band_l
    assert ESCAPE_LANE / 2 * scale <= inset < ESCAPE_LANE / 2 * scale + 20


def test_the_band_is_what_both_writers_leave():
    """A bare fixed page is placed by a plain margin in the SVG writer, which
    leaves ten units less across than the dock does. A drawing sized to the
    dock's band alone overflows that writer."""
    from pandid.render.svg import _PLAIN_SHEET_MARGIN, _page

    fs = station()
    sheet = _page("A1", fs.print_scale)
    width, _height = fitted_band(fs, "A1")
    assert width * fs.drawing_scale <= sheet.width - 2 * _PLAIN_SHEET_MARGIN + 1e-9


def test_a_core_already_filling_the_band_keeps_its_own_extent():
    """The rails may be pushed out, never pulled in through the equipment."""
    fs = station()
    fs.layout_options.boundary_page = "A1"
    fs.layout()
    boundaries = [u for u in fs.units if u.kind in {"feed", "product"}]
    core = [u for u in fs.units if u.kind not in {"feed", "product", "instrument"} and u.frame]
    assert boundaries and core
    assert min(u.frame.x for u in boundaries) <= min(u.frame.x for u in core)
    assert max(u.frame.x for u in boundaries) >= max(u.frame.x for u in core)
