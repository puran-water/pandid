"""Port-driven uniform height must not waste both sheet dimensions."""
import pytest
from pandid.layout.block_lanes import _plan, plan, plan_details


def test_fewer_columns_reduce_port_driven_height_without_moving_explicit_slots():
    lanes = [{'id': 'process', 'title': 'Process'}, {'id': 'utilities', 'title': 'Utilities'}]
    blocks = [{'key': 'process', 'lane': 'process', 'label': 'Process',
               'order': 0, 'column': 7, 'row': 0}]
    blocks += [{'key': f'utility-{i}', 'lane': 'utilities', 'label': f'Utility {i}',
                'order': i} for i in range(14)]
    streams = [{'source': 'utility-0', 'target': f'utility-{i}'} for i in range(1, 14)]
    baseline = _plan(blocks, streams, lanes, 8)
    result = plan(blocks, streams, lanes, band_width=9999)
    assert result[5] == 180 < baseline[5]
    assert max(r.w for r in result[1]) <= max(r.w for r in baseline[1])
    assert max(r.y + r.h for r in result[1]) < max(r.y + r.h for r in baseline[1])
    assert result[0]['process']['x'] == 7 * (result[4] + 130)
    assert result[0]['process']['y'] == 0
    assert set(result[0]) == {b['key'] for b in blocks}
    assert result[3] == baseline[3]
    process_band = result[1][0]
    assert result[0]['process']['x'] + result[4] <= process_band.x + process_band.w


def test_compaction_never_adds_height_to_save_width():
    lanes = [{'id': 'process', 'title': 'Process'}]
    blocks = [{'key': str(i), 'lane': 'process', 'label': str(i), 'order': i} for i in range(8)]
    baseline = _plan(blocks, [], lanes, 8)
    assert plan(blocks, [], lanes, band_width=9999) == baseline


def test_band_width_folds_only_when_the_next_block_will_not_fit():
    lanes = [{'id': 'process', 'title': 'Process'}]
    blocks = [{'key': str(i), 'lane': 'process', 'label': str(i), 'order': i}
              for i in range(11)]
    # 11 280-unit blocks, ten existing 130-unit gaps and two 30-unit
    # band insets occupy exactly 4440 units.
    fitting = plan(blocks, [], lanes, band_width=4440)
    folded = plan(blocks, [], lanes, band_width=4439)
    assert {pin['y'] for pin in fitting[0].values()} == {0}
    assert len({pin['y'] for pin in folded[0].values()}) == 2


def test_profile_passes_sheet_derived_band_width_to_lane_plan():
    from pandid.profiles.circle_h2o import block_diagram

    lanes = [{'id': 'process', 'title': 'Process'}]
    blocks = [{'key': str(i), 'id': str(i), 'lane': 'process', 'label': str(i),
               'order': i, 'attributes': {}} for i in range(6)]
    streams = [{'key': f's-{i}', 'id': f's-{i}', 'source': str(i),
                'target': str(i + 1), 'attributes': {}} for i in range(5)]
    fs = block_diagram('Band width', blocks, streams, title_block=None,
                       page_id='page', graph_attributes={}, lanes=lanes,
                       band_width=1260)
    assert fs.layout_options.band_width == 1260
    fs.layout()
    assert len({u.frame.y for u in fs.units}) == 2


def test_profile_converts_paper_clearances_through_print_scale():
    from pandid.profiles.circle_h2o import block_diagram, plan_block_diagram

    lanes = [{'id': 'process', 'title': 'Process'}]
    blocks = [{'key': key, 'id': key, 'lane': 'process', 'label': key,
               'order': order, 'attributes': {}}
              for order, key in enumerate(('a', 'b'))]
    streams = [{'key': 's', 'id': 's', 'source': 'a', 'target': 'b',
                'attributes': {}}]
    scale = 1.25
    fs = block_diagram('Paper gaps', blocks, streams, title_block=None,
                       page_id='page', graph_attributes={}, lanes=lanes,
                       print_scale=scale, band_width=4000,
                       column_gap_mm=12, row_gap_mm=10, band_gap_mm=14)
    px_per_mm = 96 / 25.4
    assert fs.layout_options.column_gap == pytest.approx(12 * px_per_mm / scale)
    assert fs.layout_options.row_gap == pytest.approx(10 * px_per_mm / scale)
    assert fs.layout_options.band_gap == pytest.approx(14 * px_per_mm / scale)
    measured = plan_block_diagram(blocks, streams, lanes, print_scale=scale,
                                  band_width=4000)
    assert measured.width > 0 and measured.height > 0
    assert measured.sizes == {'a': (280, 150), 'b': (280, 150)}


@pytest.mark.parametrize('name,value', [
    ('column_gap_mm', 0), ('row_gap_mm', float('nan')), ('band_gap_mm', True)])
def test_profile_rejects_invalid_paper_clearances(name, value):
    from pandid.profiles.circle_h2o import plan_block_diagram

    kwargs = {name: value}
    with pytest.raises(ValueError, match=name):
        plan_block_diagram([], [], [], **kwargs)


def test_lane_vocabulary_can_compact_dosing_blocks_into_one_bottom_strip():
    lanes = [
        {'id': 'process', 'title': 'Process'},
        {'id': 'utilities', 'title': 'Dosing Utilities',
         'block_width_scale': .7, 'block_height_scale': .7},
    ]
    blocks = [
        {'key': 'process', 'lane': 'process', 'label': '200\nMain Process', 'order': 0},
        *[{'key': f'dose-{i}', 'lane': 'utilities',
           'label': f'8{i:02}\nReagent {i}', 'order': i} for i in range(11)],
    ]
    streams = [{'source': f'dose-{i}', 'target': 'process'} for i in range(11)]
    result = plan_details(blocks, streams, lanes, band_width=3300,
                          column_gap=12 * 96 / 25.4,
                          row_gap=10 * 96 / 25.4,
                          band_gap=14 * 96 / 25.4)
    utility_positions = [result.positions[f'dose-{i}'] for i in range(11)]
    assert len({pin['y'] for pin in utility_positions}) == 1
    assert result.sizes['process'] == (330, 150)
    assert result.sizes['dose-0'][0] < result.sizes['process'][0]
    assert result.sizes['dose-0'][1] == pytest.approx(105)
    utilities = next(region for region in result.regions
                     if region.key == 'lane-utilities')
    assert max(pin['x'] + result.sizes['dose-0'][0]
               for pin in utility_positions) <= utilities.x + utilities.w


def test_profile_builds_each_lane_at_its_planned_size():
    from pandid.profiles.circle_h2o import block_diagram

    lanes = [
        {'id': 'process', 'title': 'Process'},
        {'id': 'utilities', 'title': 'Utilities',
         'block_width_scale': .7, 'block_height_scale': .7},
    ]
    blocks = [
        {'key': 'process', 'id': 'process', 'lane': 'process',
         'label': '200\nProcess', 'attributes': {}},
        {'key': 'dose', 'id': 'dose', 'lane': 'utilities',
         'label': '810\nAcid', 'attributes': {}},
    ]
    streams = [{'key': 'dose-process', 'id': 'dose-process',
                'source': 'dose', 'target': 'process', 'attributes': {}}]
    fs = block_diagram('Lane sizes', blocks, streams, title_block=None,
                       page_id='page', graph_attributes={}, lanes=lanes,
                       print_scale=1, band_width=3300)
    by_name = {unit.name: unit for unit in fs.units}
    assert by_name['dose'].width < by_name['process'].width
    assert by_name['dose'].height == pytest.approx(.7 * by_name['process'].height)


@pytest.mark.parametrize('field,value', [
    ('block_width_scale', 0), ('block_height_scale', 1.01),
    ('block_width_scale', float('nan')), ('block_height_scale', True)])
def test_lane_block_scales_are_bounded_finite_options(field, value):
    lanes = [{'id': 'utilities', 'title': 'Utilities', field: value}]
    blocks = [{'key': 'dose', 'lane': 'utilities', 'label': '810\nAcid'}]
    with pytest.raises(ValueError, match=field):
        plan_details(blocks, [], lanes)


def test_lane_heading_leaves_a_full_north_nozzle_arrow_approach():
    from pandid.drawing_regions import captions
    from pandid.geometry import Route
    from pandid.profiles.circle_h2o import block_diagram
    from pandid.render.svg import stream_polyline
    from pandid.routing.terminal_clearance import protect
    from pandid.routing.visibility import Rect

    blocks = [{'key': k, 'id': k, 'label': k, 'lane': lane,
               'column': col, 'attributes': {}}
              for k, lane, col in [('upstream', 'first', 2), ('receiver', 'second', 0)]]
    streams = [{'key': 'transfer', 'id': 'transfer', 'source': 'upstream',
                'target': 'receiver', 'attributes': {}}]
    fs = block_diagram('Arrow approach', blocks, streams, title_block=None,
                       page_id='page', graph_attributes={}, lanes=[
                           {'id': 'first', 'title': 'Upstream Treatment'},
                           {'id': 'second', 'title': 'Receiving Treatment'}])
    fs.to_drawio(diagram='bfd')
    stream = fs.streams[0]
    start, end = stream_polyline(stream)[0], stream_polyline(stream)[-1]
    # Reproduce a short return-lane approach without changing the nozzles.
    stream.route = Route(waypoints=[start, (start[0], end[1]-4),
                                    (end[0], end[1]-4), end], manual=False)
    protect(fs)
    points = stream_polyline(stream)
    assert (points[0], points[-1]) == (start, end)
    assert points[-1][1] - points[-2][1] >= 24
    for caption in captions(fs):
        box = Rect(caption.x, caption.x+caption.w, caption.y, caption.y+caption.h)
        assert not any(box.intersects_segment(*a, *b) for a, b in zip(points, points[1:]))
    assert fs.regions[0].y + fs.regions[0].h < fs.regions[1].y
