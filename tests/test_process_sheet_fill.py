"""Spare A1 paper belongs between trains, while stations retain their spacing."""
import json
from pathlib import Path
import xml.etree.ElementTree as ET

import pytest

from pandid import Flowsheet, Instrument, Tank, Valve
from pandid.layout.attach import _anchor, place_attached, shared_tap_stacks
from pandid.layout.halo import balloon_pads
from pandid.portgeom import unit_box
from pandid.profiles.templates import from_template
from pandid.render.drawio import fitted_band
from pandid.spec import _read_title_block


def permeation(fill=True):
    # The saved 2026-09-10 house library's actual three-pump permeation sheet:
    # 25 appearances, 23 connections, full labels, nameplates and title strip.
    data = json.loads((Path(__file__).parent / 'fixtures/house_permeation.json').read_text())
    fs = from_template(data['name'], data['nodes'], data['edges'],
                       metadata=data['metadata'], pins=data['pins'])
    fs.title_block = _read_title_block(data['title_block'], 'title_block')
    fs.equipment_data = data['equipment_data']
    fs.layout_options.fill_columns = fill
    return fs


def core_span(fs):
    boxes = [unit_box(u, u.frame) for u in fs.units
             if u.kind not in {'feed', 'product', 'instrument'}]
    return max(b[2] for b in boxes) - min(b[0] for b in boxes)


def test_permeation_fills_between_the_fixed_boundary_approaches():
    before, after = permeation(False), permeation()
    before.layout()
    after.layout()
    assert len(after.units) == 25 and len(after.streams) == 23
    band = fitted_band(after, 'A1')[0]
    assert core_span(before) / band < .45
    assert core_span(after) / band > .73
    # Two 190-unit reference flags and two 110-unit rail approaches are the
    # boundary contract. Only the paper inside them can be spent on the core.
    usable = band - 2 * (190 + 110)
    mm = after.drawing_scale * after.print_scale * 25.4 / 96
    assert (usable - core_span(after)) / 2 * mm < 25
    old = {u.name: u for u in before.units}
    new = {u.name: u for u in after.units}
    for pump, inlet, outlet in [('duty-pump-1', 'iso-031', 'iso-033'),
                                ('duty-pump-2', 'iso-037', 'iso-039'),
                                ('standby-pump', 'iso-043', 'iso-045')]:
        for valve in (inlet, outlet):
            assert new[valve].frame.x - new[pump].frame.x == pytest.approx(
                old[valve].frame.x - old[pump].frame.x)
    for name in old:
        assert (new[name].frame.w, new[name].frame.h) == (old[name].frame.w, old[name].frame.h)
    xml = after.to_drawio(diagram='p&id', page_size='A1', border='zone')
    assert ET.fromstring(xml).find('diagram') is not None
    assert after.route_converged
    assert (after.drawing_scale, after.print_scale) == (.44, 2.7)
    frames = [u.frame for u in after.units]
    after.layout()
    after.route()
    assert [u.frame for u in after.units] == frames


def test_absolute_equipment_pin_keeps_the_authored_arrangement():
    fs = permeation()
    fs.units[1].pin(x=300)
    fs.layout()
    frames = [u.frame for u in fs.units]
    fs.layout_options.fill_columns = False
    fs.layout()
    assert [u.frame for u in fs.units] == frames


def test_an_overfull_sheet_reports_capacity_at_the_same_printed_size():
    fs = permeation()
    fs.units[1].width = 5000
    with pytest.raises(ValueError, match='FIXED_SCALE_CAPACITY'):
        fs.to_drawio(diagram='p&id', page_size='A1', border='zone')
    assert (fs.drawing_scale, fs.print_scale) == (.44, 2.7)


@pytest.mark.parametrize('count', [2, 3, 4])
def test_declared_channels_reserve_and_draw_the_entire_horizontal_row(count):
    fs = Flowsheet('Multi-channel element')
    fs.layout_options.control_passes = 16
    host = fs.add(Tank('T-1'))
    balloons = [fs.add(Instrument(f'LT-{i}')).attach(host, at='N', offset=60)
                for i in range(count)]
    host.declare_multi_channel(*balloons)
    fs.route()
    tap, _ = _anchor(balloons[0])
    for index, inst in enumerate(balloons):
        assert inst.frame.cx == pytest.approx(tap[0] + (index - (count - 1) / 2) * 50)
        assert tap[1] - inst.frame.cy == pytest.approx(60)
    pad = balloon_pads(fs)[host]
    assert pad.north >= 60 + 22 + 80
    assert pad.east >= (count - 1) * 25 + 22 + 80
    assert pad.west == pad.east
    from pandid.render.svg import tap_lines
    lines = tap_lines(fs)
    assert len([line for line in lines if line[1] == tap]) == 1
    assert all(a[0] == pytest.approx(b[0]) or a[1] == pytest.approx(b[1])
               for _, a, b in lines)
    assert fs.route_converged
    assert not place_attached(fs)
    before = [u.frame for u in fs.units]
    fs.layout()
    fs.route()
    assert [u.frame for u in fs.units] == before


def test_actuator_leaders_and_distinct_taps_keep_their_declared_connections():
    fs = Flowsheet('Different connections')
    valve = fs.add(Valve('XV-1'))
    a = fs.add(Instrument('XI-1')).attach(valve, at='N', offset=60, angle=30, relation='acting_on')
    b = fs.add(Instrument('XI-2')).attach(valve, at='N', offset=60, angle=30, relation='acting_on')
    tank = fs.add(Tank('T-1'))
    c = fs.add(Instrument('LT-1')).attach(tank, at='N', offset=60)
    d = fs.add(Instrument('LT-2')).attach(tank, at='S', offset=60)
    assert shared_tap_stacks(fs) == {}
    fs.layout()
    assert a.angle == b.angle == 30
    assert c.at != d.at
    tap, _ = _anchor(a)
    assert abs(a.frame.cx - tap[0]) > 1


@pytest.mark.parametrize('variable', [None, 'pH', 'DO', 'ORP'])
def test_template_analyser_descriptor_is_above_and_right_in_native_drawio(variable):
    row = dict(key='ai', id='ai', symbol='instrument.field', label='250-AIT-01',
               instrument_function='AIT', instrument_loop='01', attributes={})
    if variable is not None:
        row['measured_variable'] = variable
    fs = from_template('Analyser', [row], [], metadata={})
    xml = ET.fromstring(fs.to_drawio(diagram='p&id', page_size='A1', border='zone'))
    inst = fs.units[0]
    if variable is None:
        assert not inst.quadrants
        return
    assert inst.quadrants == {'c': (variable,)}
    from pandid.render.svg import quadrant_labels
    x, y, *_ = next(item for item in quadrant_labels(fs, 'horizontal') if item[-1] == variable)
    assert x > inst.frame.cx and y < inst.frame.cy
    # Native detail text is the object's label; its mxCell owns the geometry.
    label = next(o for o in xml.iter('object') if o.get('label') == variable)
    detail = label.find('mxCell/mxGeometry')
    balloon = xml.find(".//mxCell[@id='ai']/mxGeometry")
    assert float(detail.get('x')) > float(balloon.get('x')) + float(balloon.get('width')) / 2
    assert float(detail.get('y')) + float(detail.get('height')) / 2 < float(balloon.get('y')) + float(balloon.get('height')) / 2


def test_each_folded_band_solves_its_own_gap():
    from collections import defaultdict
    from pandid.profiles.process import apply
    fs = apply(Flowsheet('Unequal bands'))
    fs.layout_options.band_width = 500
    fs.layout_options.column_gap = 20
    from pandid import Block
    tanks = [fs.add(Block(f'B-{i}')) for i in range(8)]
    for a, b in zip(tanks, tanks[1:]):
        fs.connect(a.out_1, b.in_1)
    fs.layout()
    bands = defaultdict(list)
    for tank in tanks:
        bands[tank.frame.y].append(tank)
    assert len(bands) > 1
    assert len({len(group) for group in bands.values()}) > 1
    for group in bands.values():
        if len(group) > 1:
            span = max(u.frame.x_max for u in group) - min(u.frame.x for u in group)
            assert span == pytest.approx(fitted_band(fs, 'A1')[0] - 50)


def test_a_shared_process_tap_on_a_valve_is_distinct_from_its_actuator():
    fs = Flowsheet('Valve pressure tap')
    valve = fs.add(Valve('FV-1'))
    a = fs.add(Instrument('PT-1')).attach(valve, at='N', offset=60, relation='sensing')
    b = fs.add(Instrument('PT-2')).attach(valve, at='N', offset=60, relation='sensing')
    actuator = fs.add(Instrument('XI-1')).attach(valve, at='N', offset=60,
                                              angle=30, relation='acting_on')
    valve.declare_multi_channel(a, b)
    assert set(shared_tap_stacks(fs)) == {a, b}
    fs.layout()
    assert a.frame.cy == pytest.approx(b.frame.cy)
    assert b.frame.cx - a.frame.cx == pytest.approx(50)
    assert actuator.angle == 30
