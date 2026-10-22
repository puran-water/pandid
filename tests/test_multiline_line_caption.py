import html
import xml.etree.ElementTree as ET

import pytest

from pandid import Feed, Flowsheet, Product
from pandid.render.line_groups import caption_size


def test_multiline_plate_measures_longest_row_and_every_baseline():
    single = caption_size('DN80 / DS1', 12)
    multi = caption_size('LINE HOLD\nDN80 / DS1\nNaOH 50 wt%', 12)
    assert multi[0] == caption_size('NaOH 50 wt%', 12)[0]
    assert multi[1] == pytest.approx(single[1] + 2 * 12 * 1.2)


def test_both_native_formats_keep_the_three_line_caption():
    fs = Flowsheet('Review line')
    a, b = Feed('Feed'), Product('Product')
    fs.add(a); fs.add(b)
    a.pin(x=100, y=100); b.pin(x=750, y=100)
    stream = fs.connect(a.outlet, b.inlet)
    stream.display_label = 'LINE HOLD\nDN80 / DS1\nNaOH 50 wt%'
    svg = ET.fromstring(fs.to_svg())
    text = next(n for n in svg.iter() if n.tag.endswith('text') and len(n) == 3)
    assert [n.text for n in text] == stream.display_label.splitlines()
    native = ET.fromstring(fs.to_drawio())
    assert any(html.unescape(n.get('value', '')).replace('<br>', '\n') == stream.display_label for n in native.iter())
