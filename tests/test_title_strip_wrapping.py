"""A supplied held-review paragraph remains complete on the native sheet."""
import copy
import xml.etree.ElementTree as ET

from pandid import Annotation, Feed, Flowsheet, Product, Revision, TitleBlock
from pandid.render.furniture import (
    _HDR_TYPE, _header_lines, measure_title_strip, title_strip_fit, title_strip_layout,
    fit_title_strip_to_sheet, measure_annotation, OUTER_MARGIN, ZONE_BAND, SEP,
)


def review_block():
    return TitleBlock(
        title="Block Flow Diagram", drawing_number="EXAMPLE-CH2O-PR-1000",
        company="Circle H2O", client="Example Client", project="Treatment Plant",
        date="2026-09-14", status="HOLD - NOT FOR CONSTRUCTION", scale="NTS",
        fit_fields=True,
        extra_fields={"CONTRACTOR": "Example Engineering Contractor", "APPROVAL": "R",
                      "HOLD": "Review material. The process unit classification has been revised from "
                              "closed_circuit_ro to ultra_high_pressure_ro under the governing record. "
                              "Not checked or approved; the project lead decides issue under the "
                              "awarded-project drawing gate."},
        revisions=[Revision("02", "2026-09-14", "Review: process classification revised",
                            "Circle H2O", "PENDING", "PENDING")],
    )


def test_fitted_hold_wraps_without_losing_words_or_reducing_reading_size():
    block = review_block()
    before = copy.deepcopy(block)
    assert measure_title_strip(block)[0] < 1117
    assert not title_strip_fit(block, "", block.date)
    headers = _header_lines(block)
    hold_start = next(i for i, (label, _) in enumerate(headers) if label == "HOLD")
    hold = headers[hold_start:]
    assert len(hold) > 1
    assert " ".join(value for _, value in hold) == block.extra_fields["HOLD"]
    strip = title_strip_layout(block, "", block.date, 1117, 770)
    for _, line in hold:
        assert any(p[0] == "text" and p[3] == line and p[4] == _HDR_TYPE for p in strip.parts)
    assert block == before


def test_both_native_backends_retain_wrapped_hold_on_a1():
    fs = Flowsheet("Review")
    fs.title_block = review_block()
    fs.print_scale = 2.7
    feed, product = fs.add(Feed("feed")), fs.add(Product("product"))
    fs.connect(feed.outlet, product.inlet)
    legend = Annotation(title="STREAM KEY", align="bottom-left", rows=[("", "chemical")])
    fs.add_annotation(legend)
    from pandid.render.svg import _page
    page = _page("A1", fs.print_scale)
    items = [(fs.title_block, "bottom-right", *measure_title_strip(fs.title_block)),
             (legend, "bottom-left", *measure_annotation(legend))]
    fitted = fit_title_strip_to_sheet(items, fs.title_block, fs.title_block, page)
    width, height = fitted[0][2:]
    assert height < items[0][3]
    assert width + measure_annotation(legend)[0] + SEP < page.width - 2 * (OUTER_MARGIN + ZONE_BAND)
    headers = _header_lines(fs.title_block, width)
    hold_start = next(i for i, (label, _) in enumerate(headers) if label == "HOLD")
    for content in (fs.to_drawio(diagram="bfd", page_size="A1", border="zone"),
                    fs.to_svg(diagram="bfd", page_size="A1", border="zone")):
        root = ET.fromstring(content)
        text = " ".join([str(v) for node in root.iter() for v in node.attrib.values()]
                        + [node.text or "" for node in root.iter()])
        assert all(line in text for _, line in headers[hold_start:])


def test_unbreakable_value_remains_overwide_instead_of_being_shortened():
    block = review_block()
    block.extra_fields["HOLD"] = "W" * 400
    assert measure_title_strip(block)[0] > 1117
    assert dict(_header_lines(block))["HOLD"] == "W" * 400
