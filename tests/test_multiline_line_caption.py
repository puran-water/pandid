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


def test_fixed_lettering_wraps_full_fluid_without_changing_its_words():
    from pandid.profiles.process import lettering
    fs = Flowsheet('Full fluid')
    a, b = fs.add(Feed('Feed')), fs.add(Product('Product'))
    stream = fs.connect(a.outlet, b.inlet)
    text = 'LINE HOLD\nDN100 / CH1\nCIP or permeate flush [strength HOLD]'
    stream.display_label = text
    lettering(fs, body=14, heading=20)
    assert stream.label.splitlines()[:2] == text.splitlines()[:2]
    assert ' '.join(stream.label.split()) == ' '.join(text.split())
    assert caption_size(stream.label, 14)[0] < caption_size(text, 14)[0]
    once = stream.label
    lettering(fs, body=14, heading=20)
    assert stream.label == once


def test_only_connected_uniform_unminted_header_segments_share_the_caption():
    from pandid import Junction, Pump
    from pandid.render.line_groups import groups
    fs = Flowsheet('Unminted header')
    a, tap, pump, b = [fs.add(u) for u in (Feed('A'), Junction('Tap'), Pump('Pump'), Product('B'))]
    lines = [fs.connect(a.outlet,tap.inlets[0]),fs.connect(tap.outlets[0],pump.suction),fs.connect(pump.discharge,b.inlet)]
    for index,line in enumerate(lines):
        line.display_label='LINE HOLD\nDN80 / DS1\nWater'
        line.label_group=str(index)
    assert len(groups(fs)[0]) == 3
    fs.drawio_metadata={'streams':{line.name:{'attributes':{'line-identity-status':'candidate_unminted'}} for line in lines}}
    assert [len(group) for group in groups(fs)[0]] == [2,1]
    from pandid.routing.captions import foreign_line_plates
    from pandid.routing.visibility import Rect
    fs._line_caption_keys = {s.name: members[0].label_group or members[0].name
                            for members in groups(fs)[0] for s in members}
    plate = Rect(10, 20, 10, 20)
    fs._planned_line_plates = {'0': plate}
    assert foreign_line_plates(fs, lines[1]) == []
    assert foreign_line_plates(fs, lines[2]) == [plate]
    lines[1].display_label='LINE HOLD\nDN50 / DS1\nWater'
    assert len(groups(fs)[0]) == 3


def test_multiline_pipe_span_reserves_the_native_flow_head_and_visible_ends():
    from pandid.render.line_groups import caption_span
    from pandid.render.svg import _LABEL_CLEAR
    from pandid.render.symbols import ARROWHEAD
    text = 'LINE HOLD\nDN80 / DS1\nmembrane feed'
    assert caption_span(text, 14, 8) >= caption_size(text, 14)[0] + 2 * _LABEL_CLEAR + ARROWHEAD


def test_routed_caption_bay_uses_clear_paper_on_the_actual_pipe_and_refuses_symbols():
    from pandid.streams import Route
    from pandid.routing.captions import routed_plate
    from pandid.routing.visibility import Rect
    fs = Flowsheet('Routed caption')
    a,b=fs.add(Feed('a')),fs.add(Product('b'))
    from pandid.geometry import Frame
    a.frame=Frame(x=-40,y=80,w=40,h=40)
    b.frame=Frame(x=600,y=80,w=40,h=40)
    line=fs.connect(a.outlet,b.inlet)
    line.display_label='LINE HOLD\nDN80 / DS1\nfeed'
    line.route=Route(waypoints=[(0,100),(600,100)])
    obstruction=Rect(250,350,40,160)
    bay=routed_plate(fs,[line],[obstruction],(0,0,700,200))
    assert bay is not None and bay.y_min < 100 < bay.y_max
    assert bay.x_max <= obstruction.x_min or bay.x_min >= obstruction.x_max
    assert routed_plate(fs,[line],[Rect(0,700,0,200)],(0,0,700,200)) is None


def test_operating_caption_region_includes_reserved_paper_below_the_last_nozzle():
    from pandid.profiles.process import apply
    from pandid.render.svg import fitted_region
    from pandid.render.drawio import fitted_band
    fs=Flowsheet('Caption paper')
    apply(fs)
    a,b=fs.add(Feed('a')),fs.add(Product('b'))
    fs.connect(a.outlet,b.inlet)
    fs.layout()
    original=fitted_region(fs)
    fs.drawio_metadata['units']={a.name:{'attributes':{'layout-subsystem':'process'}}}
    region=fitted_region(fs)
    assert region[:3]==original[:3]
    assert region[3]-region[1] == fitted_band(fs,'A1')[1]
    assert region[3] > original[3]


def test_caption_repair_moves_a_clear_pipe_track_far_enough_from_a_header():
    from pandid.geometry import Frame
    from pandid.streams import Route
    from pandid.routing.captions import routed_plate, shift_caption_run
    from pandid.routing.visibility import Rect
    fs=Flowsheet('Header beside an inscription')
    a,b=fs.add(Feed('a')),fs.add(Product('b'))
    a.frame=Frame(x=-40,y=30,w=40,h=40)
    b.frame=Frame(x=200,y=430,w=40,h=40)
    line=fs.connect(a.outlet,b.inlet)
    line.display_label='LINE HOLD\nDN15 / AS1\nVitec 3000\n[strength HOLD]'
    points=[(0,50),(100,50),(100,450),(200,450)]
    line.route=Route(waypoints=points)
    header=Rect(110,114,80,420)
    region=(0,0,500,500)
    assert routed_plate(fs,[line],[header],region) is None
    assert shift_caption_run(fs,[line],[header],region) is not None
    assert line.route.waypoints[0]==points[0] and line.route.waypoints[-1]==points[-1]
    assert line.route.waypoints[1][0] < 100
    assert not line.route.manual
    line.route=Route(waypoints=points,manual=True)
    assert shift_caption_run(fs,[line],[header],region) is None


def test_router_caption_reservation_is_reused_only_while_the_paper_is_clear():
    from pandid.geometry import Frame
    from pandid.streams import Route
    from pandid.routing.visibility import Rect
    from pandid.render.svg import stream_numbers
    fs=Flowsheet('Stable caption paper')
    a,b=fs.add(Feed('a')),fs.add(Product('b'))
    a.frame=Frame(x=-40,y=80,w=40,h=40)
    b.frame=Frame(x=600,y=80,w=40,h=40)
    line=fs.connect(a.outlet,b.inlet)
    line.display_label='LINE HOLD\nDN80 / DS1\nfeed'
    line.route=Route(waypoints=[(0,100),(600,100)])
    fs._planned_line_plates={line.name:Rect(70,230,65,135)}
    number=stream_numbers(fs,[],None,'auto')[0]
    assert number.x==150 and number.y==100 and number.leader is None
    blocked=stream_numbers(fs,[(70,65,230,135)],None,'auto')[0]
    assert blocked.x != 150 or blocked.y != 100


def test_caption_budget_reserves_a_floating_equipment_data_row():
    from pandid.profiles.process import apply
    from pandid.render.svg import fitted_region
    from pandid.render.drawio import fitted_band, DrawioRenderer
    from pandid.render.nameplates import plan
    fs=Flowsheet('Data and pipe captions share fixed paper')
    apply(fs)
    a,b=fs.add(Feed('a')),fs.add(Product('b'))
    fs.connect(a.outlet,b.inlet)
    fs.equipment_data={a.name:{'tags':'100-TK-01','rows':['CAP: 10 m³'],'clearance':65}}
    fs.layout()
    fs.drawio_metadata['units']={a.name:{'attributes':{'layout-subsystem':'process'}}}
    cards,_=plan(fs,DrawioRenderer._drawing_box(fs,equipment_data=False))
    region=fitted_region(fs)
    assert region[3]-region[1]+max(c.h for c in cards)+65 == pytest.approx(fitted_band(fs,'A1')[1])


def test_uniform_candidate_pipe_keeps_one_caption_through_a_relief_valve():
    from pandid import Valve, Pump
    from pandid.render.line_groups import groups
    fs=Flowsheet('Relief spool captions')
    a,v,b=[fs.add(u) for u in (Feed('a'),Valve('relief'),Product('b'))]
    before=fs.connect(a.outlet,v.inlet,name='upstream-entity')
    after=fs.connect(v.outlet,b.inlet,name='downstream-entity')
    for index,line in enumerate((before,after)):
        line.display_label='LINE HOLD\nDN80 / UH1\nHP relief discharge'
        line.label_group=str(index)
    assert len(groups(fs)[0])==2

    fs.drawio_metadata={'streams':{s.name:{'attributes':{'line-identity-status':'candidate_unminted'}} for s in fs.streams}}
    assert groups(fs)[0]==[[before,after]]
    assert [s.name for s in fs.streams]==['upstream-entity','downstream-entity']
    after.display_label='LINE HOLD\nDN100 / UH1\nHP relief discharge'
    assert len(groups(fs)[0])==2


def test_vertical_corridor_reflows_description_without_smaller_type_or_missing_words():
    from pandid.geometry import Frame, Route
    from pandid.render.svg import stream_numbers
    fs=Flowsheet('Narrow vertical pipe corridor')
    a,b=fs.add(Feed('a')),fs.add(Product('b'))
    a.frame=Frame(x=60,y=0,w=50,h=20)
    b.frame=Frame(x=110,y=1080,w=50,h=20)
    stream=fs.connect(a.outlet,b.inlet)
    stream.route=Route(waypoints=[(110,50),(110,1050)])
    text='LINE HOLD\nDN100 / CH1\nneutralised spent\nclean\n[strength HOLD]'
    stream.display_label=text
    fs.stream_labels.font_size=17
    numbers=stream_numbers(fs,[],None,'vertical',(70,0,150,1100),False)
    assert len(numbers)==1
    number=numbers[0]
    assert number.placement_limit is None and not number.leader_crossed and not number.crossed
    assert number.vertical and len(number.text.splitlines())==3
    assert ' '.join(number.text.split())==' '.join(text.split())
    assert number.font_size==17


def test_diagonal_leader_reserves_only_its_stroked_corridor():
    from pandid.routing.captions import leader_boxes
    boxes=leader_boxes((0,0),(100,100))
    assert all(any(b.contains(t,t) for b in boxes) for t in range(101))
    assert not any(b.contains(90,10) for b in boxes)
    assert any(b.intersects_segment(40,50,60,50) for b in boxes)
