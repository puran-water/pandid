"""A table sheet that carries a stated selection of streams, and notes.

``fs.stream_table.columns`` is what lets a caller split a stream table
too wide for one sheet across several: each sheet draws exactly the
streams it is given, in the order given, and nothing else -- not even
the boundary streams the table otherwise always keeps.
``fs.stream_table.notes`` docks boxes on the table's own sheet, which is
where the basis of the numbers and the meaning of a dash belong: not in
a cell, because every column is ruled at the widest cell.
"""

import re
import xml.etree.ElementTree as ET

import pytest

from pandid import Flowsheet, units as U
from pandid.document import Annotation, Revision, TitleBlock
from pandid.render import furniture as F
from pandid.render.svg import _page, table_sheet_plan
from pandid.spec import from_dict as from_spec, to_dict as to_spec


def _sheet(streams: int = 6) -> Flowsheet:
    fs = Flowsheet("Selection A100")
    fs.title_block = TitleBlock(
        title="Selection A100", subtitle="Process Flow Diagram 1",
        drawing_number="PFD-1001", company="Pandid",
        revisions=[Revision("A", "2026-01-01", "Issued for review", "AA")],
    )
    for i in range(streams):
        feed = fs.add(U.Feed(f"F{i}")).pin(x=100, y=100 + 80 * i)
        product = fs.add(U.Product(f"P{i}")).pin(x=320, y=100 + 80 * i)
        stream = fs.connect(feed.outlet, product.inlet)
        stream.properties = {"Flow (m3/h)": f"{10 + i}"}
    return fs


def _headings(fs) -> list[str]:
    return [s.name for s in F._table_streams(fs)]


def test_a_selection_is_the_columns_in_the_order_stated():
    fs = _sheet()
    names = [s.name for s in fs.streams]
    fs.stream_table.columns = (names[4], names[1])
    assert _headings(fs) == [names[4], names[1]]


def test_a_selection_leaves_out_boundary_streams_it_does_not_name():
    """Every stream here crosses the sheet edge, which is what keeps a
    column unasked; a stated selection is the one thing that overrules it,
    or a feed would head a column on every sheet of the set."""
    fs = _sheet()
    for s in fs.streams:
        s.properties = {}
    names = [s.name for s in fs.streams]
    assert _headings(fs) == names  # kept for crossing the edge
    fs.stream_table.columns = (names[2],)
    assert _headings(fs) == [names[2]]


def test_a_named_stream_with_nothing_on_it_keeps_its_column():
    fs = _sheet(streams=3)
    fs.streams[0].properties = {}
    fs.stream_table.columns = tuple(s.name for s in fs.streams)
    plan = table_sheet_plan(fs, _page("A3"))
    heading = [c.text for c in plan.table.blocks[0].rows[0][1:]]
    assert heading == [s.name for s in fs.streams]


@pytest.mark.parametrize("columns,match", [
    (("S99",), "no stream on this flowsheet"),
    (("S1", "S1"), "more than once"),
    ((), "is empty"),
    ("S1", "sequence of stream names"),
])
def test_a_selection_that_cannot_be_drawn_exactly_raises(columns, match):
    fs = _sheet()
    fs.stream_table.columns = columns
    with pytest.raises(ValueError, match=match):
        fs.to_svg(show_stream_table="sheet", page_size="A3")


def test_notes_dock_on_the_table_sheet_in_both_backends():
    fs = _sheet()
    fs.stream_table.notes = [Annotation(
        title="NOT GOVERNING", rows=["Basis: walk 36, converged", "'-' = not computed"],
        align="bottom-left")]
    plan = table_sheet_plan(fs, _page("A3"))
    (note, x, y, w, h), = plan.notes
    sx, sy, sw, sh = plan.strip
    # Beside the strip, in the same band, and clear of it.
    assert x + w <= sx and y + h == pytest.approx(sy + sh)
    # Below the table.
    last = plan.table.h + plan.top
    assert y >= last
    svg = fs.to_svg(show_stream_table="sheet", page_size="A3")
    assert "NOT GOVERNING" in svg and "Basis: walk 36, converged" in svg
    model = ET.fromstring(fs.to_drawio(show_stream_table="sheet", page_size="A3"))
    labels = " ".join(c.get("value", "") for c in model.iter("mxCell"))
    assert "NOT GOVERNING" in labels and "Basis: walk 36, converged" in labels


def test_notes_are_not_drawn_on_the_diagram():
    fs = _sheet(streams=2)
    fs.stream_table.notes = [Annotation(title="TABLE ONLY", rows=["x"], align="bottom-left")]
    assert "TABLE ONLY" not in fs.to_svg(page_size="A3")


def test_a_pinned_note_is_refused_on_the_table_sheet():
    fs = _sheet(streams=2)
    fs.stream_table.notes = [Annotation(title="PINNED", rows=["x"], position=(10, 10))]
    with pytest.raises(ValueError, match="dock by their align"):
        table_sheet_plan(fs, _page("A3"))


def test_notes_too_deep_for_the_page_are_refused_not_overlapped():
    fs = _sheet(streams=2)
    fs.stream_table.notes = [Annotation(title="LONG", rows=["line"] * 200, align="bottom-left")]
    with pytest.raises(ValueError, match="does not fit page size A3"):
        table_sheet_plan(fs, _page("A3"))


def test_selection_and_notes_round_trip_through_the_spec():
    fs = _sheet(streams=3)
    names = tuple(s.name for s in fs.streams)
    fs.stream_table.columns = names[::-1]
    fs.stream_table.notes = [Annotation(title="NOTES", rows=["a", "b"], align="bottom-left")]
    spec = to_spec(fs)
    assert spec["stream_table"]["columns"] == list(names[::-1])
    again = from_spec(spec)
    assert again.stream_table.columns == names[::-1]
    (note,) = again.stream_table.notes
    assert (note.title, note.rows, note.align) == ("NOTES", ["a", "b"], "bottom-left")


def test_a_sheet_that_sets_neither_writes_the_spec_it_always_did():
    spec = to_spec(_sheet(streams=2))
    assert "columns" not in spec.get("stream_table", {})
    assert "notes" not in spec.get("stream_table", {})


def test_one_table_split_over_two_sheets_heads_each_stream_once():
    fs = _sheet(streams=6)
    names = [s.name for s in fs.streams]
    seen = []
    for part in (names[:3], names[3:]):
        fs.stream_table.columns = tuple(part)
        svg = fs.to_svg(show_stream_table="sheet", page_size="A3")
        blocks = re.findall(r'<g id="stream_table_\d+">.*?</g>', svg, re.S)
        for block in blocks:
            seen += [t for t in re.findall(r"<text[^>]*>([^<]*)</text>", block) if t in names]
    assert sorted(seen) == sorted(names)


def test_a_page_too_small_for_its_table_is_a_type_a_caller_can_catch():
    from pandid.render.svg import PageTooSmall
    fs = _sheet(streams=2)
    fs.stream_table.notes = [Annotation(title="LONG", rows=["line"] * 200, align="bottom-left")]
    with pytest.raises(PageTooSmall):
        fs.to_drawio(show_stream_table="sheet", page_size="A3")
    assert issubclass(PageTooSmall, ValueError)


def test_the_table_sheet_neither_lays_out_nor_routes_the_diagram(monkeypatch):
    """It draws no diagram, so a table sheet of a large flowsheet must not
    pay for routing one -- nor report the diagram's geometry as its own."""
    fs = _sheet(streams=3)

    def refuse():
        raise AssertionError("a table sheet resolved the diagram's geometry")

    monkeypatch.setattr(fs, "_resolve_geometry", refuse)
    fs.to_drawio(show_stream_table="sheet", page_size="A3")
    fs.to_svg(show_stream_table="sheet", page_size="A3")
    with pytest.raises(AssertionError, match="resolved the diagram"):
        fs.to_svg(page_size="A3")
