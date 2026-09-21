"""A header bank spends paper on actual station envelopes, not a blanket pitch."""

import pytest

from pandid import Feed, Flowsheet, Junction, Product, Pump, Valve
from pandid.layout.parallel_trains import align
from pandid.portgeom import port_point, unit_box
from pandid.profiles.process import apply


def bank(clearance):
    fs = apply(Flowsheet('Synthetic six-station bank'))
    fs.layout_options.parallel_trains = True
    fs.layout_options.parallel_train_clearance = clearance
    source = fs.add(Feed('supply'))
    suction = fs.add(Junction('suction', outputs=6, header=True))
    delivery = fs.add(Junction('delivery', inputs=6, header=True))
    target = fs.add(Product('delivery-boundary'))
    fs.connect(source.outlet, suction.inlets[0])
    for i in range(6):
        valve = fs.add(Valve(f'801-HV-{i+1:02}'))
        pump = fs.add(Pump(f'801-P-{i+1:02}', variant='peristaltic'))
        fs.connect(suction.outlets[i], valve.inlet)
        fs.connect(valve.outlet, pump.suction)
        fs.connect(pump.discharge, delivery.inlets[i])
    fs.connect(delivery.outlets[0], target.inlet)
    for stream in fs.streams:
        stream.display_label = ''
    fs.layout()
    return fs, suction, delivery


def test_measured_bank_recovers_height_without_scaling_or_changing_connectivity():
    old, old_suction, _ = bank(None)
    fs, suction, delivery = bank(32)
    assert suction.frame.h < old_suction.frame.h - 250
    assert len(fs.units) == len(old.units) and len(fs.streams) == len(old.streams)
    assert (fs.print_scale, fs.drawing_scale) == (old.print_scale, old.drawing_scale)
    for before, after in zip(old.units, fs.units):
        if after.kind != 'junction':
            assert (after.frame.w, after.frame.h) == (before.frame.w, before.frame.h)
    pumps = [u for u in fs.units if u.kind == 'pump']
    for a, b in zip(pumps, pumps[1:]):
        assert unit_box(b, b.frame)[1] - unit_box(a, a.frame)[3] >= 32
    axes = [port_point(u, u.frame, 'suction')[1] for u in pumps]
    assert len({round(b-a, 5) for a, b in zip(axes, axes[1:])}) == 1
    fs.to_drawio(diagram='p&id', page_size='A1')
    assert fs.route_converged


def test_authored_train_pin_is_not_repacked():
    fs, _, _ = bank(32)
    pump = next(u for u in fs.units if u.kind == 'pump')
    pump.pin(y=pump.frame.y)
    frames = [u.frame for u in fs.units]
    align(fs)
    assert [u.frame for u in fs.units] == frames


@pytest.mark.parametrize('bad', [0, -1, True, float('nan')])
def test_clearance_policy_is_positive_and_finite(bad):
    fs = Flowsheet('Invalid clearance')
    fs.layout_options.parallel_train_clearance = bad
    with pytest.raises(ValueError, match='parallel_train_clearance'):
        fs.layout_options.validate()


def test_caller_lettering_is_measured_and_never_capped_to_a_balloon():
    import xml.etree.ElementTree as ET
    from pandid import Instrument
    from pandid.profiles.process import lettering
    from pandid.render.svg import SvgRenderer, _unit_label_box
    fs, _, _ = bank(32)
    pump = next(u for u in fs.units if u.kind == 'pump')
    instrument = fs.add(Instrument('801-LIT-01'))
    instrument.attach(pump, at='N')
    fs.equipment_data = {pump.name: {'tags': pump.name, 'rows': ['DUTY: synthetic']}}
    lettering(fs, body=17, heading=24)
    first = [(u.width, u.height) for u in fs.units]
    lettering(fs, body=17, heading=24)
    assert [(u.width, u.height) for u in fs.units] == first
    assert fs.stream_labels.font_size == 17
    assert fs.equipment_data[pump.name]['font_size'] == 17
    xml = ET.fromstring(fs.to_drawio(diagram='p&id', page_size='A1'))
    cell = xml.find(f".//mxCell[@id='u{fs.units.index(instrument)}']")
    size = dict(p.split('=', 1) for p in cell.get('style').split(';') if '=' in p)['fontSize']
    assert float(size) == pytest.approx(17 * fs.print_scale * fs.drawing_scale * 100 / 96, abs=.01)
    renderer = SvgRenderer()
    frame = pump.frame
    small = renderer._unit_label_item(pump, frame, frame.x, frame.y, frame.w, frame.h, '801-P-01')
    pump.font_size = 24
    large = renderer._unit_label_item(pump, frame, frame.x, frame.y, frame.w, frame.h, '801-P-01')
    a, b = _unit_label_box(small), _unit_label_box(large)
    assert b[2]-b[0] > a[2]-a[0] and b[3]-b[1] > a[3]-a[1]
