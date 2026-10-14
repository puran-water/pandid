"""A line number's leader lands on its run clear of the flow arrowhead.

Owner ruling 2026-10-14. A leader's head is kept off a run's ends by
``_LABEL_CLEAR``, or a third of the run where the run is too short to spare
that, and further off an end that is *marked* -- a drawn flange -- through
``keep_out``. A flow arrowhead is a mark on its end too, and was not counted:
on a short link between two blocks the third-of-the-run clamp put the head
inside the arrowhead's length, on its flank, where at print size the two heads
merge and the leader reads as a second line into the block. The head now lands
:data:`~pandid.render.svg._HEAD_KEEP_OUT` clear of every flow head as drawn --
in the free length behind it where a short link leaves only that -- and a run
with no free length at all is reported unresolved, never led onto the head.
"""

import math

import pytest

from pandid import Block, Flowsheet
from pandid.render import drawio as drawio_module
from pandid.render import svg as svg_module
from pandid.render.svg import (_HEAD_KEEP_OUT, _LEADER_HEAD, _arrowhead_keep_outs, _drawn_head,
                               _head_room, _leader_choices, label_findings, stream_numbers,
                               stream_polyline)
from pandid.render.symbols import ARROWHEAD, MIN_HEAD_CLEARANCE
from pandid.render.weights import LineWeight

NAME = "000-04"


def _link(gap: float) -> "tuple[Flowsheet, object]":
    """Two blocks side by side, joined face to face by a link *gap* long.

    The number is wider than the link, so it cannot be written on it and is
    led back to it -- the shape of the house block diagrams' 000-04.
    """
    fs = Flowsheet("Short link")
    source = fs.add(Block("Supply", inputs=0, outputs=["E"], width=180, height=150)).pin(x=100, y=100)
    dest = fs.add(Block("Dosing", inputs=["W"], outputs=0, width=180, height=150)).pin(
        x=100 + 180 + gap, y=100)
    link = fs.connect(source.out_1, dest.in_1, name=NAME)
    link.display_label = NAME
    fs.stream_labels.font_size = 22
    fs.layout_options.stream_label_bands = 7
    fs.layout_options.strict_label_clearance = True
    fs.layout()
    fs.route()
    return fs, link


def _clear_of_heads(point, boxes) -> float:
    return min(math.hypot(max(b[0] - point[0], point[0] - b[2], 0.0),
                          max(b[1] - point[1], point[1] - b[3], 0.0)) for b in boxes)


def test_the_keep_out_is_the_white_between_the_two_heads_as_drawn():
    """The flow head and the leader's head as the export draws them, and the white between two marks."""
    main, detail = LineWeight.MAIN_FLOW.width, LineWeight.DETAIL.width
    assert _drawn_head(ARROWHEAD, main) == pytest.approx(ARROWHEAD + main * (3 + math.sqrt(5)) / 2)
    assert _HEAD_KEEP_OUT == pytest.approx(MIN_HEAD_CLEARANCE + _drawn_head(_LEADER_HEAD, detail))
    # Measured on an exported block diagram: a 10.5 pt flow triangle at 0.75 pt a unit, (12 + 2) long,
    # set back half a pen over sin(atan(1/2)) and stroked: 17.24 units from the line's end.
    assert _drawn_head(12.0, 2.0) == pytest.approx(17.236, abs=1e-3)


#: Paper taken above and below the destination block, so the number is written over the source block
#: and led forward to the link -- the side 000-04 was written on.
_DESTINATION_SIDE_TAKEN = [(305.0, -400.0, 900.0, 99.0), (305.0, 251.0, 900.0, 800.0)]


@pytest.mark.parametrize("gap, placed", [(45.35, _DESTINATION_SIDE_TAKEN), (80.0, [])])
def test_a_leader_to_a_short_link_lands_clear_of_its_flow_arrowhead(gap, placed):
    """45.35 units is the house link between two adjacent blocks: the third-of-the-run clamp put a
    forward leader's head 15.12 units from the point, inside the 17.24 the flow head is drawn over;
    it now lands in the free length behind the head, as a leader led back from the far side always
    did. At 80 the ``_LABEL_CLEAR`` inset put it 20 from the point, its own head over the flow head's
    base."""
    fs, link = _link(gap)
    points = stream_polyline(link)
    heads = _arrowhead_keep_outs(fs, True)[NAME]
    assert len(heads) == 1

    number = stream_numbers(fs, list(placed), None, "vertical", None)[0]
    assert number.leader is not None and number.placement_limit is None
    end = number.leader[1]
    assert end[1] == pytest.approx(points[0][1]), "the head must land on its own run"
    assert points[0][0] <= end[0] <= points[-1][0]
    assert _clear_of_heads(end, heads) >= _HEAD_KEEP_OUT - 1e-9
    along = points[-1][0] - end[0]
    assert along >= (_drawn_head(ARROWHEAD, LineWeight.MAIN_FLOW.width) + MIN_HEAD_CLEARANCE
                     + _drawn_head(_LEADER_HEAD, LineWeight.DETAIL.width) - 1e-9)

    # A sheet that draws no head keeps nothing off: the same search lands where the old clamp put it,
    # inside the keep-out, which is what this test would see without the heads counted.
    bare = stream_numbers(fs, list(placed), None, "vertical", None, False)[0]
    assert _clear_of_heads(bare.leader[1], heads) < _HEAD_KEEP_OUT


def test_a_link_with_no_room_behind_its_head_is_unresolved_never_led_onto_it():
    """30 units: the third of the run at the source end and the keep-out at the head leave no free
    length. The number is reported unresolved -- a finding a sheet can be refused on -- rather than
    led onto the arrowhead, which is where the unheaded search puts it."""
    fs, link = _link(30.0)
    number = stream_numbers(fs, [], None, "vertical", None)[0]
    assert number.leader is None
    assert number.placement_limit is not None
    codes = [issue.code for issue in label_findings(fs, "none", [number], "vertical")]
    assert "leader-placement-unresolved" in codes

    unheaded = stream_numbers(fs, [], None, "vertical", None, False)[0]
    heads = _arrowhead_keep_outs(fs, True)[NAME]
    assert unheaded.leader is not None
    assert _clear_of_heads(unheaded.leader[1], heads) < _HEAD_KEEP_OUT


def test_the_room_on_a_piece_beside_a_short_last_piece_is_measured_to_the_head():
    """A head on a last piece shorter than itself reaches round the corner; the piece before it
    keeps the leader's end the keep-out from the head's box, not from the run's end alone."""
    # A run down x = 0 from y = 0 to y = 100, then east 10 units to x = 10: the head's box stands
    # over the corner, x -7.24 .. 10, y 100 -/+ 8.62.
    length = _drawn_head(ARROWHEAD, LineWeight.MAIN_FLOW.width)
    head = (10.0 - length, 100.0 - length / 2, 10.0, 100.0 + length / 2)
    room = _head_room(0.0, 100.0, 0.0, True, (head,))
    assert room == [(0.0, pytest.approx(100.0 - length / 2 - _HEAD_KEEP_OUT))]
    # And a box beside the piece but farther than the keep-out takes nothing.
    assert _head_room(0.0, 100.0, 0.0, True, ((_HEAD_KEEP_OUT + 1, 40, 60, 60),)) == [(0.0, 100.0)]
    # Every leader the sweep offers to that piece lands in the room.
    halo = (-120.0, 20.0, -20.0, 40.0)
    for lead, _keys in _leader_choices(halo, ((0.0, 0.0), (0.0, 100.0)), 0.0, (head,)):
        assert lead[1][1] <= room[0][1] + 1e-9


@pytest.mark.parametrize("diagram, heads", [("bfd", True), ("pfd", True), ("p&id", False)])
def test_both_backends_ask_with_the_heads_their_sheet_draws(monkeypatch, diagram, heads):
    """The search is told whether the sheet heads its lines, by both exporters: a P&ID draws none and
    keeps nothing off, a PFD or block diagram draws them and keeps its leaders clear."""
    fs, _link_ = _link(80.0)
    seen = []
    original = svg_module.stream_numbers

    def spy(*args, **kwargs):
        seen.append(args[5] if len(args) > 5 else kwargs.get("arrows", True))
        return original(*args, **kwargs)

    monkeypatch.setattr(svg_module, "stream_numbers", spy)
    monkeypatch.setattr(drawio_module, "stream_numbers", spy)
    fs.to_drawio(diagram=diagram)
    fs.to_svg(diagram=diagram)
    assert seen and set(seen) == {heads}
