"""A legal text corridor can fall between full-height candidate bands."""
import pytest
from pandid.render.svg import _label_anchors, _covering


@pytest.mark.parametrize('vertical', [False, True])
def test_bare_label_finds_clear_corridor_between_legacy_bands(vertical):
    # Forty-unit text fits in this 48-unit corridor. Full-height candidate
    # centres at 24 and 64 each hit a wall; the intermediate centre fits.
    obstacles = [(-1000, -1000, 1000, 20), (-1000, 68, 1000, 1000)]
    if vertical:
        obstacles = [(y0, x0, y1, x1) for x0, y0, x1, y1 in obstacles]
    candidates = list(_label_anchors(0, 0, 200, 132, 40, vertical, False, 132, 3))
    bw, bh = (40, 132) if vertical else (132, 40)
    clear = [(x, y) for x, y, _ in candidates if _covering(
        (x-bw/2, y-bh/2, x+bw/2, y+bh/2), [], obstacles) == (0, 0)]
    assert clear
    # The improvement changes neither text size nor the search's reach.
    assert max(off for _, _, off in candidates) == 104


def test_enclosed_label_stays_on_its_run():
    candidates = list(_label_anchors(0, 0, 200, 132, 40, False, True, 132, 3))
    assert candidates and all(y == off == 0 for _, y, off in candidates)


def test_bfd_caption_uses_clear_paper_when_its_nearby_search_is_full():
    from pandid.profiles.circle_h2o import block_diagram
    from pandid.render.drawio import _tag_pass
    from pandid.render.svg import stream_numbers, _meets
    from pandid.render.symbols import default_registry
    from pandid.portgeom import unit_box

    blocks = [{'key': k, 'id': k, 'label': k, 'lane': 'process',
               'order': order, 'attributes': {}} for order, k in enumerate(('source', 'target'))]
    fs = block_diagram('Short caption corridor', blocks, [
        {'key': 'transfer-01', 'id': 'transfer', 'source': 'source',
         'target': 'target', 'attributes': {}}], title_block=None,
        page_id='page', graph_attributes={}, lanes=[{'id': 'process', 'title': 'Process'}])
    fs.stream_labels.font_size = 30.8
    fs.layout_options.stream_label_bands = 1
    fs.to_drawio(diagram='bfd', jump_direction='auto')
    number, = stream_numbers(fs, list(_tag_pass(fs, default_registry, None, 'auto').plates), None, 'auto')
    assert number.leader is not None
    assert not number.crossed
    assert not any(_meets(number.box, unit_box(u, u.frame)) for u in fs.units)
