import xml.etree.ElementTree as ET

import pytest

from pandid import Feed, Flowsheet, Product, Valve
from pandid.render.svg import SvgRenderer, _unit_label_box


def test_multiline_halo_protects_both_lines_without_charging_newline_as_width():
    first = (100, 200, 'middle', 'baseline', 'top', '106-HV-03')
    one = _unit_label_box(first)
    two = _unit_label_box((*first[:-1], '106-HV-03\nDN50 / SPEC'))
    assert two[3] == one[3]
    assert two[3] - two[1] == pytest.approx(29.4)
    assert two[2] - two[0] == pytest.approx(len('DN50 / SPEC') * 6.6 + 8)
    rendered = ET.fromstring('<svg>' + ''.join(SvgRenderer()._draw_unit_labels(
        [(*first[:-1], '106-HV-03\nDN50 / SPEC')])) + '</svg>')
    labels = rendered.findall('.//text')
    assert [t.text for t in labels] == ['106-HV-03', 'DN50 / SPEC']
    assert float(labels[1].get('y')) - float(labels[0].get('y')) == pytest.approx(14.4)


def test_native_label_width_uses_longest_printed_line():
    fs = Flowsheet('Valve labels')
    source, target = fs.add(Feed('air')), fs.add(Product('basin'))
    valve = fs.add(Valve('106-HV-03\nDN50 / SPEC', variant='butterfly'))
    fs.connect(source.outlet, valve.inlet)
    fs.connect(valve.outlet, target.inlet)
    xml = ET.fromstring(fs.to_drawio())
    labelled = [e for e in xml.iter('mxCell') if '106-HV-03' in e.get('value', '')]
    assert len(labelled) == 1
    assert '<br>' in labelled[0].get('value')
    assert 'labelWidth=' in labelled[0].get('style')
