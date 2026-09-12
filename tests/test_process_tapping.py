"""One process connection per independent device, declared sharing per element."""

import math
import xml.etree.ElementTree as ET

import pytest

from pandid import Flowsheet, Tank, Valve
from pandid.layout.attach import _anchor, place_attached, shared_tap_stacks
from pandid.portgeom import face_point, unit_box
from pandid.render.svg import tap_lines


def pair(*, along=(.2, .8), face='N', width=240):
    fs = Flowsheet('Instrument connections')
    tank = fs.add(Tank('T-1', width=width, height=240))
    a = fs.add_instrument('LIT', '101-07', sensing=tank, at=face, along=along[0], offset=60)
    b = fs.add_instrument('AE', '101-08', sensing=tank, at=face, along=along[1], offset=60)
    return fs, tank, a, b


@pytest.mark.parametrize('face', ['N', 'S', 'E', 'W'])
def test_independent_taps_keep_perpendicular_parallel_stems(face):
    fs, tank, a, b = pair(face=face)
    assert shared_tap_stacks(fs) == {}
    fs.route()
    assert a.tap != b.tap
    for inst in (a, b):
        tap, tangent = _anchor(inst)
        delta = (inst.frame.cx - tap[0], inst.frame.cy - tap[1])
        assert delta[0] * tangent[0] + delta[1] * tangent[1] == pytest.approx(0, abs=1e-8)
        assert math.hypot(*delta) == pytest.approx(60)
    assert fs.route_converged
    assert not place_attached(fs)
    assert not [issue for issue in fs.validate() if issue.severity == 'error']


def test_each_field_device_has_its_own_panel_function_above_it():
    fs, tank, a, b = pair()
    panels = [fs.add_instrument(code, field.number, sensing=field, at='N', offset=70,
                               display='central')
              for field, code in ((a, 'LIC'), (b, 'AIT'))]
    fs.to_svg()
    for field, panel in zip((a, b), panels):
        assert panel.frame.cx == pytest.approx(field.frame.cx)
        assert panel.frame.cy < field.frame.cy < field.tap[1]
    assert len(tap_lines(fs)) == 4
    xml = ET.fromstring(fs.to_drawio())
    taps = [cell for cell in xml.iter('mxCell') if cell.get('id', '').startswith('t')
            and cell.get('edge') == '1']
    assert len(taps) == 4
    assert all('edgeStyle=none;' in cell.get('style') for cell in taps)
    assert len({cell.get('target') for cell in taps}) == 4


@pytest.mark.parametrize('orientation', [0, 90, 180, 270])
@pytest.mark.parametrize('face', ['N', 'S', 'E', 'W'])
def test_along_uses_the_drawn_face_after_host_transforms(face, orientation):
    fs, tank, a, b = pair(face=face)
    tank.pin(x=300, y=300, orientation=orientation, mirrored=True)
    fs.route()
    x0, y0, x1, y1 = unit_box(tank, tank.frame)
    for inst, fraction in ((a, .2), (b, .8)):
        expected = {'N': (x0 + fraction * (x1-x0), y0),
                    'S': (x0 + fraction * (x1-x0), y1),
                    'E': (x1, y0 + fraction * (y1-y0)),
                    'W': (x0, y0 + fraction * (y1-y0))}[face]
        assert inst.tap == pytest.approx(expected)
    assert face_point(tank, tank.frame, face) == face_point(tank, tank.frame, face, .5)


@pytest.mark.parametrize('along', [0, .5, 1])
def test_along_endpoints_and_explicit_centre_round_trip(along):
    fs = Flowsheet('Face fraction')
    tank = fs.add(Tank('T'))
    a = fs.add_instrument('LT', 1, sensing=tank, at='N', along=along)
    fs.route()
    rebuilt = Flowsheet.from_dict(fs.to_dict())
    rebuilt.route()
    assert rebuilt.units[1].tap == a.tap
    assert rebuilt.units[1].along == along
    assert ('along' in fs.to_dict()['instruments'][0]) == (along != .5)


@pytest.mark.parametrize('along', [-.1, 1.1, float('nan'), float('inf'), True, '.2'])
def test_bad_along_is_refused_before_an_attachment_or_sheet_changes(along):
    fs, tank, a, b = pair()
    before = fs.to_dict()
    with pytest.raises(ValueError, match='along='):
        a.attach(tank, at='S', along=along)
    assert fs.to_dict() == before
    with pytest.raises(ValueError, match='along='):
        fs.add_instrument('TT', 3, sensing=tank, along=along)
    assert fs.to_dict() == before


def test_a_stream_or_unattached_balloon_cannot_silently_ignore_along():
    fs = Flowsheet('Stream fraction')
    a, b = [fs.add(Tank(name)) for name in ('A', 'B')]
    line = fs.connect(a.outlet, b.inlet)
    with pytest.raises(ValueError, match='along='):
        fs.add_instrument('FT', 1, sensing=line, along=.5)
    with pytest.raises(ValueError, match='along='):
        fs.add_instrument('FT', 1, along=.5)


@pytest.mark.parametrize('render', ['to_svg', 'to_drawio'])
@pytest.mark.parametrize('changes', [{}, {'offset': 90}, {'angle': 45}])
def test_undeclared_coincidence_fails_closed_even_with_different_standoffs(render, changes):
    fs, tank, a, b = pair(along=(.5, .5))
    b.attach(tank, at='N', offset=changes.get('offset', 60), angle=changes.get('angle', 90))
    assert shared_tap_stacks(fs) == {}
    with pytest.raises(ValueError, match='instrument-tap-undeclared'):
        getattr(fs, render)()
    issue = next(issue for issue in fs.validate() if issue.code == 'instrument-tap-undeclared')
    assert issue.severity == 'error'
    assert a.name in issue.message and b.name in issue.message and 'along' in issue.message


def test_different_faces_that_meet_at_one_corner_are_also_an_error():
    fs, tank, a, b = pair(along=(0, 0))
    b.attach(tank, at='W', along=0, offset=60)
    with pytest.raises(ValueError, match='instrument-tap-undeclared'):
        fs.to_svg()


@pytest.mark.parametrize('on_stream', [False, True])
def test_declared_multichannel_pair_draws_one_stem_and_horizontal_channels(on_stream):
    fs, tank, a, b = pair(along=(.5, .5))
    host = tank
    if on_stream:
        other = fs.add(Tank('T-2'))
        host = fs.connect(tank.outlet, other.inlet)
        for inst in (a, b):
            inst.attach(host, at=.5, offset=60)
    host.declare_multi_channel(a, b)
    fs.to_svg()
    assert a.tap == b.tap
    assert a.frame.cy == pytest.approx(b.frame.cy)
    assert b.frame.x - a.frame.x_max == pytest.approx(6)
    segments = tap_lines(fs)
    stems = [(inst, start, end) for inst, start, end in segments if start == a.tap]
    assert len(stems) == 1
    junction = stems[0][2]
    assert a.frame.cx < junction[0] < b.frame.cx
    assert all(start[1] == pytest.approx(end[1]) for _, start, end in segments[1:])
    xml = ET.fromstring(fs.to_drawio())
    cells = [cell for cell in xml.iter('mxCell') if cell.get('id', '').startswith('t')
             and cell.get('edge') == '1']
    assert len(cells) == 3
    assert cells[0].get('target') is None
    assert cells[0].find('mxGeometry/mxPoint[@as="targetPoint"]') is not None
    assert all(cell.get('target') for cell in cells[1:])
    assert all(cell.find('mxGeometry/mxPoint[@as="sourcePoint"]') is not None
               for cell in cells[1:])
    before = fs.to_dict()
    rebuilt = Flowsheet.from_dict(before)
    assert rebuilt.to_dict() == before
    assert rebuilt.to_svg() == fs.to_svg()
    assert fs.route_converged and not place_attached(fs)


def test_a_declaration_cannot_swallow_an_undeclared_third_device():
    fs, tank, a, b = pair(along=(.5, .5))
    tank.declare_multi_channel(a, b)
    fs.add_instrument('PT', 3, sensing=tank, at='N', offset=60)
    with pytest.raises(ValueError, match='instrument-tap-undeclared'):
        fs.to_svg()


@pytest.mark.parametrize('change', ['along', 'relation', 'pin', 'removed'])
def test_declarations_are_rechecked_after_member_edits(change):
    fs, tank, a, b = pair(along=(.5, .5))
    tank.declare_multi_channel(a, b)
    if change == 'along':
        b.attach(tank, at='N', along=.8, offset=60)
    elif change == 'relation':
        b.attach(tank, at='N', relation='acting_on', offset=60)
    elif change == 'pin':
        b.pin(x=200)
    else:
        fs.units.remove(b)
    with pytest.raises(ValueError, match='multi-channel-invalid'):
        fs.to_svg()


def test_declaring_an_element_checks_members_before_writing():
    fs, tank, a, b = pair()
    for members in [(a,), (a, a), (a, b), (a, tank)]:
        with pytest.raises(ValueError):
            tank.declare_multi_channel(*members)
        assert tank.multi_channel_elements == ()


def test_an_angled_actuator_leader_keeps_its_authored_angle():
    fs = Flowsheet('Actuator leader')
    valve = fs.add(Valve('XV-1'))
    balloon = fs.add_instrument('XI', 1, acting_on=valve, at='N', offset=90, angle=30)
    fs.to_svg()
    tap, tangent = _anchor(balloon)
    dx, dy = balloon.frame.cx - tap[0], balloon.frame.cy - tap[1]
    assert math.degrees(math.atan2(-dy, dx)) == pytest.approx(30)
    assert math.hypot(dx, dy) == pytest.approx(90)
    assert shared_tap_stacks(fs) == {}


def test_distinct_but_too_close_taps_still_report_the_real_search_constraint():
    fs, tank, a, b = pair(along=(.48, .52))
    fs.route()
    assert a.tap != b.tap
    # Distinct taps do not promise enough paper for two 44-unit bubbles.
    # The existing search may rotate at its first ring to clear that overlap.
    assert abs(b.frame.cx - b.tap[0]) > 1
    assert not [issue for issue in fs.validate() if issue.code == 'instrument-tap-undeclared']


def test_declared_channels_keep_unique_stable_drawio_appearances():
    fs, tank, a, b = pair(along=(.5, .5))
    tank.declare_multi_channel(a, b)
    fs.drawio_metadata = {'units': {a.name: {'id': 'channel-a'}, b.name: {'id': 'channel-b'}}}
    xml = ET.fromstring(fs.to_drawio())
    ids = [element.get('id') for element in xml.iter() if element.get('id') is not None]
    assert len(ids) == len(set(ids))
    assert {'channel-a', 'channel-b', 'channel-a-tap-stem', 'channel-a-tap',
            'channel-b-tap'} <= set(ids)
    assert xml.find('.//object[@id="channel-a-tap-stem"]').get('for-cell') == 'channel-a'


def test_templates_pass_face_positions_and_explicit_host_membership():
    from pandid.profiles.templates import from_template
    nodes = [dict(key='tank', id='tank-id', symbol='tank.vertical', label='T', attributes={})]
    for key in ['a', 'b']:
        nodes.append(dict(key=key, id=key+'-id', symbol='instrument.field', label='',
                          instrument_function='AE' if key == 'a' else 'TE', instrument_loop='1',
                          attributes={}, attachment=dict(kind='unit', target='tank', at='N',
                                                         along=.2 if key == 'a' else .8)))
    fs = from_template('Independent positions', nodes, [], metadata={})
    assert [u.along for u in fs.units[1:]] == [.2, .8]
    assert shared_tap_stacks(fs) == {}
    nodes[2]['attachment']['along'] = .2
    nodes[0]['multi_channel_elements'] = [['a', 'b']]
    fs = from_template('One element', nodes, [], metadata={})
    assert fs.units[0].multi_channel_elements == (tuple(fs.units[1:]),)
    assert len(shared_tap_stacks(fs)) == 2
    assert ET.fromstring(fs.to_drawio()).find('diagram') is not None


def test_a_primary_balloon_keeps_along_and_refuses_a_bad_fraction_atomically():
    fs = Flowsheet('Primary element')
    element = fs.add(Valve('FE-1'))
    before = fs.to_dict()
    with pytest.raises(ValueError, match='along='):
        fs.add_balloon(element, at='N', along=2)
    assert fs.to_dict() == before and element.balloon is None
    balloon = fs.add_balloon(element, at='N', along=.2)
    rebuilt = Flowsheet.from_dict(fs.to_dict())
    assert rebuilt.units[1].along == balloon.along == .2


def test_a_control_loop_passes_along_to_its_field_device():
    fs = Flowsheet('Level control')
    tank = fs.add(Tank('T'))
    valve = fs.add(Valve('LV-1', variant='control'))
    loop = fs.add_control_loop('L', 1, measuring=tank, acting_on=valve,
                               at='N', along=.2)
    assert loop.transmitter.along == .2
    assert loop.controller.host is loop.transmitter
    fs.to_svg()


@pytest.mark.parametrize('entry', [
    {'type': 'LT', 'number': 1, 'along': .2},
    {'type': 'LT', 'number': 1, 'sensing': 'T', 'along': True},
    {'type': 'LT', 'number': 1, 'sensing': 'T', 'along': 1.1},
])
def test_specs_refuse_an_invalid_or_unanchored_face_fraction(entry):
    from pandid.spec import SpecError
    with pytest.raises(SpecError, match='along'):
        Flowsheet.from_dict({'name': 'Invalid position', 'units': [{'kind': 'Tank', 'name': 'T'}],
                             'instruments': [entry]})


def test_a_shared_row_reserves_its_panel_children_and_moves_as_one_box():
    fs, tank, a, b = pair(along=(.5, .5))
    tank.declare_multi_channel(a, b)
    panels = [fs.add_instrument(code, inst.number, sensing=inst, at='N',
                               offset=70, display='central')
              for inst, code in [(a, 'LIC'), (b, 'AIT')]]
    fs.to_svg()
    for inst, panel in zip((a, b), panels):
        assert panel.frame.cx == pytest.approx(inst.frame.cx)
        assert panel.frame.cy < inst.frame.cy
    assert a.frame.cy == pytest.approx(b.frame.cy)
    assert fs.route_converged and not place_attached(fs)
    xml = fs.to_drawio()
    fs.layout()
    assert fs.to_drawio() == xml


def test_a_vertical_process_line_reserves_the_horizontal_channels_full_reach():
    from pandid.layout.halo import balloon_pads

    fs = Flowsheet('Vertical process line')
    upper = fs.add(Tank('Upper')).pin(col=0, row=0)
    lower = fs.add(Tank('Lower')).pin(col=0, row=1)
    line = fs.connect(upper.outlet, lower.inlet)
    channels = [fs.add_instrument(code, 1, sensing=line, offset=60)
                for code in ('AE', 'TE')]
    line.declare_multi_channel(*channels)
    fs.layout()
    for host in (upper, lower):
        # Both endpoints pay for a stream tap before the route exists. Its
        # channel row reaches beyond the common stem, including on this axis.
        assert balloon_pads(fs)[host].east >= 60 + 47 + 22 + 80
