"""A route's first turn stands off its own end block: short_terminal_stubs / hold_terminal_stubs."""
import copy

import pytest

from pandid import Flowsheet, units
from pandid.geometry import Frame, Route
from pandid.render.svg import stream_polyline
from pandid.routing.terminal_clearance import hold_terminal_stubs, short_terminal_stubs

#: A sump 200 wide whose top face is y=100; its outlet leaves the top, turns 0.9 above the face and runs along it,
#: as a crossing move left ZLR's 840-01 over sump-1, then rises into a block 400 to the east.
ALONG_OWN_BLOCK = [(100, 100), (100, 99.1), (500, 99.1), (500, 0)]


def _block(fs, name, frame, out_face=None, in_face=None):
    block = fs.add(units.Block(name))
    if out_face:
        block.nozzle("out_1", out_face)
    if in_face:
        block.nozzle("in_1", in_face)
    block.frame = frame
    return block


def _sheet(route, *, manual=False, neighbour=None):
    fs = Flowsheet("terminal stub")
    fs.layout_options.stream_spacing = 14
    sump = _block(fs, "Sump", Frame(x=0, y=100, w=200, h=100), out_face="N")
    target = _block(fs, "Target", Frame(x=400, y=-100, w=200, h=100), in_face="S")
    stream = fs.connect(sump.out_1, target.in_1)
    stream.route = Route(waypoints=copy.deepcopy(route), manual=manual)
    if neighbour is not None:
        a = _block(fs, "A", Frame(x=-200, y=0, w=100, h=100), out_face="E")
        b = _block(fs, "B", Frame(x=700, y=0, w=100, h=100), in_face="W")
        other = fs.connect(a.out_1, b.in_1)
        other.route = Route(waypoints=copy.deepcopy(neighbour))
    return fs, stream


def test_a_turn_back_along_its_own_block_nearer_than_the_minimum_is_short_and_one_off_its_corner_is_not():
    fs, stream = _sheet(ALONG_OWN_BLOCK)
    assert short_terminal_stubs(fs, stream, ALONG_OWN_BLOCK, 6) == [0]
    assert short_terminal_stubs(fs, stream, [(100, 100), (100, 94), (500, 94), (500, 0)], 6) == []
    # Out of the block's corner and away from it: the turned leg passes over nothing.
    corner = [(200, 100), (200, 99.1), (500, 99.1), (500, 0)]
    assert short_terminal_stubs(fs, stream, corner, 6) == []
    # The destination end: the target's bottom face is y=0; a turn 0.9 under it running back below it is short.
    assert short_terminal_stubs(fs, stream, [(100, 100), (100, 50), (450, 50), (450, 0.9), (500, 0.9), (500, 0)],
                                6) == [-1]


def test_the_track_moves_out_to_the_preferred_stand_off_with_exact_ends_and_is_idempotent():
    fs, stream = _sheet(ALONG_OWN_BLOCK)
    assert hold_terminal_stubs(fs, minimum=6, preferred=14) == [stream.name]
    after = stream_polyline(stream)
    assert after == [(100, 100), (100, 86), (500, 86), (500, 0)]
    assert short_terminal_stubs(fs, stream, after, 6) == []
    assert hold_terminal_stubs(fs, minimum=6, preferred=14) == []
    assert stream_polyline(stream) == after


def test_an_authored_route_is_never_moved():
    fs, stream = _sheet(ALONG_OWN_BLOCK, manual=True)
    assert hold_terminal_stubs(fs, minimum=6, preferred=14) == []
    assert stream.route.waypoints == ALONG_OWN_BLOCK


def test_a_parallel_run_crowding_the_new_track_steps_on_by_the_spacing():
    # An interior run 20 above the face: the stub at 14 would sit 6 from it, so it steps on to a spacing beyond.
    neighbour = [(-100, 50), (-40, 50), (-40, 80), (300, 80), (300, 50), (700, 50)]
    fs, stream = _sheet(ALONG_OWN_BLOCK, neighbour=neighbour)
    moved = hold_terminal_stubs(fs, minimum=6, preferred=14)
    other = fs.streams[1]
    assert sorted(moved) == sorted([stream.name, other.name])
    assert stream_polyline(stream) == [(100, 100), (100, 86), (500, 86), (500, 0)]
    assert stream_polyline(other) == [(-100, 50), (-40, 50), (-40, 72), (300, 72), (300, 50), (700, 50)]


@pytest.mark.parametrize("worse", [True, False])
def test_a_move_that_leaves_more_stream_numbers_unplaced_is_not_taken(worse):
    fs, stream = _sheet(ALONG_OWN_BLOCK)
    original = list(stream.route.waypoints)
    # A stand-in for the sheet's label search: one more number unplaced once the route has moved.
    count = (lambda sheet: int(sheet.streams[0].route.waypoints != original)) if worse else (lambda sheet: 0)
    moved = hold_terminal_stubs(fs, minimum=6, preferred=14, unplaced=count)
    if worse:
        assert moved == [] and stream_polyline(stream) == ALONG_OWN_BLOCK
    else:
        assert moved == [stream.name] and stream_polyline(stream)[1] == (100, 86)
