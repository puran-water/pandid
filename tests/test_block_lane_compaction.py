"""Port-driven uniform height must not waste both sheet dimensions."""
from pandid.layout.block_lanes import _plan, plan


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
