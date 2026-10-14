"""A bare line number goes without a leader only on its line or in the first band beside it.

Owner ruling 2026-10-14. :func:`~pandid.render.svg._along` asks whether a run
lies beside the words, not how far across the paper they stand, and the first
pass of :func:`~pandid.render.svg._bare_stream_number` used to take any along
anchor :func:`~pandid.render.svg._label_anchors` offered -- out to the seventh
band -- with no leader and without the own-line verdict a leader is held to
(owner ruling 2026-09-25). On the house block flow diagrams that wrote numbers
up to 44.6 mm from their own run, some of them beside another stream's line.

Every case here is one run and a strip of symbols laid over it, so the search
is posed directly: the same paper, and only the stand-off decides.
"""

import math

import pytest

from pandid.render.svg import _Ink, _OwnLine, _bare_stream_number, _first_band

NAME = "S1"
RUN = (((0.0, 0.0), (400.0, 0.0)), 0.0)
DEPTH, WIDTH = 20.0, 100.0
OWN = _Ink(-1.0, -1.0, 401.0, 1.0, "h", 0.0, "pipe", NAME)


def _place(symbols, ink=(OWN,)):
    return _bare_stream_number(
        [RUN], NAME, "black", NAME, 10.0, WIDTH, DEPTH, 7, list(symbols), [],
        list(ink), None, 8.0)


def test_a_number_in_the_first_band_beside_its_run_needs_no_leader():
    """The pipe itself is taken, the first band is clear: written there, bare."""
    number = _place([(-10.0, -3.0, 410.0, 3.0)])
    assert number.leader is None and number.placement_limit is None
    assert abs(number.y) == pytest.approx(_first_band(DEPTH))


def test_a_number_beyond_the_first_band_carries_a_leader_to_its_run():
    """The pipe and the first three bands are covered but for a 40-unit gap.

    The first clear paper along the run is the fourth band, 44 units out, which
    the first pass used to take bare. Its words have the run beside them and a
    whole empty band between: displaced, so tied back by a leader through the
    gap, landing on the run.
    """
    symbols = [(-10.0, -26.0, 180.0, 26.0), (220.0, -26.0, 410.0, 26.0)]
    number = _place(symbols)
    assert abs(number.y) > _first_band(DEPTH)
    assert number.placement_limit is None
    assert number.leader is not None, "written bare two bands or more from its run"
    (x0, y0), (x1, y1) = number.leader
    assert y1 == pytest.approx(0.0) and 180.0 < x1 < 220.0  # on its own run, in the gap
    assert abs(x1 - x0) > 0 and abs(y1 - y0) > 0  # oblique (ISO 15519-1 §12.1)
    assert math.hypot(x1 - x0, y1 - y0) >= 2 * 5.0


def test_a_far_band_beside_another_line_is_not_written_there_bare():
    """The same paper with another stream's line running along it, nearer the
    words than their own run: the number read as that line's. It now goes
    through the leadered search and its own-line verdict, which refuses the
    spot; with nothing else admissible here the placement is reported
    unresolved -- a finding a drawing can be refused on -- instead of being
    written beside the wrong line in silence."""
    other = _Ink(-101.0, -71.0, 501.0, -69.0, "h", -70.0, "pipe", "S2")
    symbols = [(-10.0, -26.0, 180.0, 26.0), (220.0, -26.0, 410.0, 26.0),
               (-200.0, 26.0, 600.0, 400.0)]
    number = _place(symbols, (OWN, other))
    assert _OwnLine(NAME, [OWN, other]).verdict(number.box, False) == "strict"
    assert number.leader is None
    assert number.placement_limit is not None, "written bare beside S2 with no finding"
