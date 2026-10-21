"""A number named in ``fs.stream_labels.own_line_unled`` goes bare only where its own line is the nearest.

The first pass writes a bare number on its run or in the first band beside it wherever the halo is
readable, and never asked whether another stream's line written along it stands nearer than its own;
the leadered search does (:class:`~pandid.render.svg._OwnLine`, owner ruling 2026-09-25). A block
diagram whose renderer measures that on its sheet names the numbers it found off their line, and
for those the first pass applies the same verdict: the number tries the rest of its run, then a
leader, and is reported unresolved where neither is clear. Nothing named, nothing moves.
"""

import pytest

from pandid import Block, Flowsheet
from pandid.document import StreamLabelOptions
from pandid.render import svg as svg_module
from pandid.render.svg import (_HALO_CHAR, _HALO_DEEP, _HALO_PAD, _LABEL_GAP, _OwnLine, _Ink,
                               _bare_stream_number, _ink_pad, stream_numbers)
from pandid.render.weights import LineWeight
from pandid.spec import from_dict, to_dict

OWN, RIVAL = "230-01", "250-03"
PAD = _ink_pad(LineWeight.MAIN_FLOW)
SCALE = 2.2
WIDTH, DEPTH = len(OWN) * _HALO_CHAR * SCALE + _HALO_PAD * SCALE, _HALO_DEEP * SCALE


def _line(name, a, b):
    (ax, ay), (bx, by) = a, b
    axis, at = ("v", (ax + bx) / 2) if abs(ax - bx) < abs(ay - by) else ("h", (ay + by) / 2)
    return _Ink(min(ax, bx) - PAD, min(ay, by) - PAD, max(ax, bx) + PAD, max(ay, by) + PAD, axis, at,
                "pipe", name)


#: Its own run, 80 units: too short for the number on the pipe, long enough to be beside it.
SEGMENT = ((0.0, 0.0), (80.0, 0.0))
#: The rival runs along above it, its centre line 2.4 units off the first band's plate there: nearer
#: than the 4-unit gap the plate keeps to its own (ZLR 230-01: 2.47 against 4.00).
RIVAL_Y = -(_LABEL_GAP + DEPTH + 2.4)


def _place(held, placed=(), rival_below=False):
    ink = [_line(OWN, *SEGMENT), _line(RIVAL, (-200.0, RIVAL_Y), (300.0, RIVAL_Y))]
    if rival_below:
        ink.append(_line(RIVAL, (-200.0, -RIVAL_Y), (300.0, -RIVAL_Y)))
    return _bare_stream_number([(SEGMENT, 0.0)], OWN, "black", OWN, 10.0 * SCALE, WIDTH, DEPTH, 7, [],
                               list(placed), ink, None, 8.0, (), held), _OwnLine(OWN, ink)


def test_the_first_pass_writes_the_number_beside_a_nearer_parallel_unless_it_is_named():
    pinned, own_line = _place(False)
    assert pinned.leader is None and pinned.placement_limit is None
    assert pinned.box[3] < 0, "the first band above the run, the side ISO 15519-1 7.2.5 asks for"
    assert own_line.verdict(tuple(pinned.box), False) == "strict"

    named, own_line = _place(True)
    assert named.leader is None and named.placement_limit is None
    assert named.box[1] > 0, "the far side of its own run, where its line is the nearest"
    assert own_line.verdict(tuple(named.box), False) is None


def test_a_named_number_with_no_clear_side_is_led_or_unresolved_never_written_beside_the_rival():
    """With the rival along both sides, no bare spot has its own line nearest: the leadered search
    answers, and whatever it answers is not a bare number beside the rival."""
    pinned, own_line = _place(False, rival_below=True)
    assert pinned.leader is None and own_line.verdict(tuple(pinned.box), False) == "strict"

    named, own_line = _place(True, rival_below=True)
    assert named.leader is not None or named.placement_limit is not None
    if named.leader is not None:
        assert own_line.verdict(tuple(named.box), False) != "strict"


def _two_links():
    fs = Flowsheet("Two links")
    first = fs.add(Block("First", inputs=0, outputs=["E"], width=180, height=150)).pin(x=100, y=100)
    second = fs.add(Block("Second", inputs=["W"], outputs=["E"], width=180, height=150)).pin(x=500, y=100)
    third = fs.add(Block("Third", inputs=["W"], outputs=0, width=180, height=150)).pin(x=900, y=100)
    for source, dest, name in ((first.out_1, second.in_1, OWN), (second.out_1, third.in_1, RIVAL)):
        fs.connect(source, dest, name=name).display_label = name
    fs.layout()
    fs.route()
    return fs


@pytest.mark.parametrize("value, held", [(frozenset(), set()), (frozenset({RIVAL}), {RIVAL}),
                                         ([OWN, RIVAL], {OWN, RIVAL}), (True, {OWN, RIVAL})])
def test_only_the_named_numbers_are_held(monkeypatch, value, held):
    seen = {}
    original = svg_module._bare_stream_number

    def spy(runs, name, *args):
        seen[name] = args[-1]
        return original(runs, name, *args)

    monkeypatch.setattr(svg_module, "_bare_stream_number", spy)
    fs = _two_links()
    fs.stream_labels.own_line_unled = value
    stream_numbers(fs, [], None, "vertical", None)
    assert {name for name, flag in seen.items() if flag} == held and set(seen) == {OWN, RIVAL}


@pytest.mark.parametrize("value", ["230-01", [1], 3.0, None])
def test_anything_but_true_false_or_stream_names_is_refused(value):
    with pytest.raises(ValueError, match="own_line_unled"):
        StreamLabelOptions(own_line_unled=value)


def test_the_option_round_trips_through_a_spec():
    fs = Flowsheet("held")
    assert "stream_labels" not in to_dict(fs), "the default writes nothing"
    fs.stream_labels.own_line_unled = frozenset({RIVAL, OWN})
    spec = to_dict(fs)
    assert spec["stream_labels"]["own_line_unled"] == [OWN, RIVAL]
    assert from_dict(spec).stream_labels.own_line_unled == frozenset({OWN, RIVAL})
    fs.stream_labels.own_line_unled = True
    assert from_dict(to_dict(fs)).stream_labels.own_line_unled is True
