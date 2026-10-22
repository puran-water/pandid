"""Fixed-size composition regressions, independent of project identity."""
import pytest
from pandid import Flowsheet, Feed, Product, Valve
from pandid.render.line_groups import groups
from pandid.render.reference_flags import wrap_reference
from pandid.render.furniture import text_width


def test_a_physical_line_can_offer_both_valve_segments_for_one_caption():
    from pandid.render.svg import stream_numbers
    fs=Flowsheet('Two spools, one line')
    a=fs.add(Feed('a')).pin(x=100,y=50)
    v=fs.add(Valve('HV')).pin(x=170,y=50)
    b=fs.add(Product('b')).pin(x=700,y=50)
    first=fs.connect(a.outlet,v.inlet,name='first')
    second=fs.connect(v.outlet,b.inlet,name='second')
    for s in (first,second):
        s.display_label='100-L-001';s.label_group='physical-line'
    fs.layout();fs.route()
    numbers=stream_numbers(fs,[],None,'vertical')
    assert len(numbers)==1 and numbers[0].text=='100-L-001'
    assert numbers[0].placement_limit is None
    assert numbers[0].seg[1][0]>300
    assert [s.name for s in fs.streams]==['first','second']
    restored=Flowsheet.from_dict(fs.to_dict())
    assert [s.label_group for s in restored.streams]==['physical-line','physical-line']
    from xml.etree import ElementTree as ET
    document = ET.fromstring(fs.to_drawio())
    printed = [e.get('value') for e in document.iter('mxCell') if e.get('edge') == '1']
    assert printed.count('100-L-001') == 1
    assert not any(e.get('value') == '100-L-001' and 'fontSize=' not in e.get('style', '')
                   for e in document.iter('mxCell'))


def test_grouping_is_explicit_and_rejects_conflicting_text():
    fs=Flowsheet('Grouping')
    a=fs.add(Feed('a'));v=fs.add(Valve('v'));b=fs.add(Product('b'))
    x=fs.connect(a.outlet,v.inlet,name='x');y=fs.connect(v.outlet,b.inlet,name='y')
    x.display_label=y.display_label='same words'
    assert len(groups(fs)[0])==2
    x.label_group=y.label_group='line'
    y.display_label='different line'
    with pytest.raises(ValueError,match='LINE_LABEL_GROUP_CONFLICT'):groups(fs)


def test_reference_wrap_retains_complete_document_identifier():
    text='Cleaning supply\nTO EXAMPLE/1200KLD/CH2O/PR/1002 SH. 6\n100-P-01'
    lines=wrap_reference(text,233,17)
    assert all(text_width(s,17)<=233 for s in lines)
    assert ''.join(''.join(lines).split())==''.join(text.split())
    assert len(lines)<=5


def test_held_end_has_one_real_port_and_visible_hold():
    from pandid.units import HeldPipeEnd
    from pandid.profiles.templates import from_template
    end=HeldPipeEnd('end',direction='outlet');end.display_label='Destination HOLD'
    assert len(end.ports)==1 and end.pipe.direction=='outlet'
    assert end.tag=='Destination HOLD'
    assert end.symbol().port_faces['pipe']=={'E':(40,6)}
    fs=Flowsheet('Unengineered source direction');fs.add(end)
    restored=Flowsheet.from_dict(fs.to_dict()).units[0]
    assert restored.pipe.direction=='outlet' and restored.tag=='Destination HOLD'
    assert restored.symbol().port_faces==end.symbol().port_faces


def test_held_interface_reserves_its_caption_overhang_beside_the_line_text():
    from pandid.units import HeldPipeEnd
    from pandid.geometry import Frame
    from pandid.layout.halo import Pad
    from pandid.layout.operating_banks import Assembly
    from pandid.layout.operating_terminals import attach
    from pandid.portgeom import port_point
    from pandid.render.line_groups import caption_size
    fs=Flowsheet('Held interface caption')
    source=fs.add(HeldPipeEnd('source',direction='outlet'))
    valve=fs.add(Valve('valve'))
    line=fs.connect(source.pipe,valve.inlet)
    line.display_label='LINE HOLD\nDN20 / SD1\nAcid provision - no duty'
    own=Assembly('source',(source,),{source:(80,20,40,12)},200,32)
    peer=Assembly('valve',(valve,),{valve:(10,20,40,30)},60,50)
    assemblies=[own,peer]
    pads={source:Pad(west=80,east=80,north=20),valve:Pad(west=10,east=10,north=20)}
    attach(fs,assemblies,pads,2000)
    def endpoint(unit,port):
        x,y,w,h=peer.frames[unit]
        return port_point(unit,Frame(x=x,y=y,w=w,h=h),port)
    a,b=endpoint(source,'pipe'),endpoint(valve,'inlet')
    assert b[0]-a[0] >= caption_size(line.label,fs.stream_labels.font_size)[0]+50+90
    assert a[1]==b[1] and len(assemblies)==1
    from pandid.layout.operating_banks import reserve_caption_bays, footprint
    before=peer.height
    reserve_caption_bays(fs,assemblies,pads)
    assert peer.height>before
    assert peer.caption_bays and all(box in footprint(fs,peer,pads) for box in peer.caption_bays)
    assert all(y>=0 and y+h<=peer.height for x,y,w,h in peer.caption_bays)


def test_measured_rectangle_pack_preserves_all_sizes():
    from pandid.layout.rectangle_pack import pack
    rectangles=[('large',100,90),('wide',100,40),('small',30,30)]
    result=pack(rectangles,200,150)
    assert result and set(result)=={'large','wide','small'}
    for key,w,h in rectangles:assert result[key][2:]==(w,h)
    assert pack(rectangles,50,50) is None


def test_nozzle_escape_cannot_jump_across_a_thin_header():
    from pandid.routing.visibility import Rect, clear_escape_projection
    header = Rect(820, 824, 50, 537)
    anchor, proposed = (844, 465), (819, 465)
    assert not header.contains(*proposed)
    actual = clear_escape_projection(anchor, 'W', proposed, [header])
    assert actual == (834, 465)
    assert not header.intersects_segment(*anchor, *actual)


def test_operating_bank_follows_pump_discharge_nozzle_and_reserves_its_caption():
    from pandid import Junction, Pump
    from pandid.profiles.process import apply
    from pandid.portgeom import port_point
    from pandid.render.line_groups import caption_size
    fs = apply(Flowsheet('Two complete pump stations'))
    fs.layout_options.parallel_trains = True
    fs.layout_options.parallel_train_clearance = 32
    source = fs.add(Junction('suction', outputs=2, header=True))
    target = fs.add(Junction('discharge', inputs=2, header=True))
    stations = []
    for index in range(2):
        pump = fs.add(Pump('pump-'+str(index)))
        valve = fs.add(Valve('valve-'+str(index)))
        fs.connect(source.outlets[index], pump.suction)
        stream = fs.connect(pump.discharge, valve.inlet)
        stream.display_label = '100-L-001'
        fs.connect(valve.outlet, target.inlets[index])
        stations.append((pump, valve, stream))
    fs.drawio_metadata['units'] = {u.name:{'attributes':{'layout-subsystem':'pumping'}} for u in fs.units}
    fs.layout()
    for pump, valve, stream in stations:
        start, end = port_point(pump,pump.frame,'discharge'), port_point(valve,valve.frame,'inlet')
        assert start[1] == pytest.approx(end[1])
        assert end[0]-start[0] >= caption_size(stream.label,fs.stream_labels.font_size)[0]
    assert len(fs.units) == 6 and len(fs.streams) == 6


def test_free_controller_stays_in_the_available_operating_field():
    from pandid.layout.control import _nearest_free
    from pandid.geometry import Frame
    occupied = [Frame(x=50,y=50,w=100,h=100)]
    x,y = _nearest_free(40,30,40,40,occupied,True,True,bounds=(0,0,300,200))
    assert 0 <= x <= 260 and 0 <= y <= 160
    assert x >= 180 or y >= 180 or x+40+30 <= 50 or y+40+30 <= 50


def test_free_control_placement_does_not_chase_route_dependent_caption_offsets():
    from pandid import Instrument
    from pandid.geometry import Frame
    from pandid.layout.control import _place_free
    from pandid.routing.visibility import Rect
    fs=Flowsheet('Stable controller placement against frozen equipment')
    valve=fs.add(Valve('control valve',variant='control'))
    valve.frame=Frame(x=400,y=300,w=40,h=40)
    control=fs.add(Instrument('FCV',1))
    fs.connect(control.sig_out,valve.actuator,kind='electric')
    fs.layout_options.control_grid=25
    fs.drawio_metadata['units']={valve.name:{'attributes':{'layout-subsystem':'process'}}}
    _place_free(fs)
    before=(control.frame.x,control.frame.y)
    fs._resolved_tag_boxes={valve:Rect(before[0]-50,before[0]+100,before[1]-50,before[1]+100)}
    assert not _place_free(fs)
    assert (control.frame.x,control.frame.y)==before


def test_nameplate_plan_does_not_require_a_free_controller_position():
    from pandid import Pump, Instrument
    from pandid.geometry import Frame
    from pandid.render.nameplates import plan
    fs = Flowsheet('Measured equipment with an unplaced controller')
    pump = fs.add(Pump('pump')); pump.frame = Frame(x=50,y=100,w=60,h=60)
    fs.add(Instrument('PIC-1'))
    fs.equipment_data = {'pump': {'tags':'100-P-01','rows':['Capacity: source value']}}
    blocks, bounds = plan(fs,(0,0,600,200))
    assert len(blocks) == 1 and bounds[3] > 200


def test_router_avoids_another_lines_reserved_caption():
    from types import SimpleNamespace
    from pandid.routing.astar import find_path
    from pandid.routing.visibility import Rect
    start, goal, upper_left, upper_right = (0,0),(40,0),(0,30),(40,30)
    edges = {start:[goal,upper_left],goal:[start,upper_right],
             upper_left:[start,upper_right],upper_right:[upper_left,goal]}
    graph=SimpleNamespace(nodes=set(edges),edges=edges,recycle_y=[])
    assert find_path(graph,start,goal) == [start,goal]
    plate=Rect(15,25,-5,5)
    path=find_path(graph,start,goal,forbidden=[plate])
    assert path == [start,upper_left,upper_right,goal]
    assert not any(plate.intersects_segment(*a,*b) for a,b in zip(path,path[1:]))


def test_exact_measured_span_reserves_caption_despite_float_roundoff():
    from pandid.geometry import Frame
    from pandid.portgeom import resolve_size
    from pandid.routing.captions import line_plates, foreign_line_plates
    from pandid.render.line_groups import caption_size
    fs=Flowsheet('Measured interstage span')
    a=fs.add(Valve('a'));b=fs.add(Valve('b'))
    w,h=resolve_size(a)
    fs.stream_labels.font_size=17
    span=caption_size('100-L-048',17)[0]+2*fs.layout_options.stream_label_gap
    for unit,x in [(a,50),(b,50+w+span)]:
        unit.frame=Frame(x=x,y=100,w=w,h=h)
    stream=fs.connect(a.outlet,b.inlet,name='span');stream.display_label='100-L-048'
    fs.drawio_metadata['units']={u.name:{'attributes':{'layout-subsystem':'process'}} for u in fs.units}
    fs._planned_line_plates=line_plates(fs)
    assert list(fs._planned_line_plates) == ['span']
    assert foreign_line_plates(fs,stream) == []


def test_crossing_overlap_trial_matches_full_geometric_measurement():
    from pandid.routing.crossing_clearance import _OverlapPlan, _overlaps
    lines={0:[(0,0),(100,0),(100,80)],1:[(30,10),(130,10),(130,90)],
           2:[(0,40),(140,40)]}
    moved=[(30,10),(150,10),(150,90)]
    for clearance in (0,14):
        assert _OverlapPlan(lines,clearance).score(1,moved) == pytest.approx(
            _overlaps({**lines,1:moved},clearance),abs=1e-9)


def test_extra_cip_port_does_not_shift_the_two_pump_branch_nozzles():
    from pandid import Junction, Pump
    from pandid.profiles.process import apply
    from pandid.portgeom import port_point
    fs=apply(Flowsheet('Pump bank with shared cleaning connection'))
    fs.layout_options.parallel_trains=True
    fs.layout_options.parallel_train_clearance=32
    inlet=fs.add(Junction('inlet',outputs=2,header=True))
    outlet=fs.add(Junction('outlet',inputs=3,header=True))
    pumps=[]
    for i in range(2):
        p=fs.add(Pump('pump-'+str(i)));pumps.append(p)
        fs.connect(inlet.outlets[i],p.suction)
        fs.connect(p.discharge,outlet.inlets[i])
    feed=fs.add(Feed('CIP supply'));v=fs.add(Valve('CIP valve'))
    fs.connect(feed.outlet,v.inlet);fs.connect(v.outlet,outlet.inlets[2])
    fs.drawio_metadata['units']={u.name:{'attributes':{'layout-subsystem':'pumping'}} for u in fs.units}
    fs.layout()
    for i,p in enumerate(pumps):
        assert port_point(p,p.frame,'discharge')[1] == pytest.approx(
            port_point(outlet,outlet.frame,outlet.inlets[i].name)[1])
    assert port_point(v,v.frame,'outlet')[1] == pytest.approx(
        port_point(outlet,outlet.frame,outlet.inlets[2].name)[1])
    assert port_point(outlet,outlet.frame,'in_3')[1] > port_point(outlet,outlet.frame,'in_2')[1]+50


def test_compound_packer_keeps_all_ink_and_card_below_its_owner():
    pytest.importorskip('ortools')
    from pandid.layout.constraint_pack import pack
    shapes=[('process',80,50,[(0,0,20,50),(20,30,60,20)]),
            ('card',35,20,[(0,0,35,20)]),('small',35,20,[(0,0,35,20)])]
    result=pack(shapes,100,110,gap=4,below=[('process','card',5)])
    assert result is not None
    assert result['card'][1] >= result['process'][1]+55
    assert pack(shapes,20,20) is None
    parts=[(name,result[name][0]+x,result[name][1]+y,w,h)
           for name,_,_,rects in shapes for x,y,w,h in rects]
    for i,(name,x,y,w,h) in enumerate(parts):
        for other,xx,yy,ww,hh in parts[i+1:]:
            if name!=other:
                assert x+w<=xx or xx+ww<=x or y+h<=yy or yy+hh<=y


def test_positioned_nameplate_rejects_changed_engineering_text_and_crossing_pipe():
    from copy import deepcopy
    from dataclasses import replace
    from pandid import Pump
    from pandid.geometry import Frame
    from pandid.streams import Route
    from pandid.render.nameplates import plan,fixed_boxes
    fs=Flowsheet('Source-custody test')
    pump=fs.add(Pump('pump'));pump.frame=Frame(x=0,y=0,w=60,h=60)
    feed=fs.add(Feed('feed'));feed.frame=Frame(x=-100,y=0,w=80,h=40)
    stream=fs.connect(feed.outlet,pump.suction)
    fs.equipment_data={'pump':{'tags':'100-P-01','rows':['Capacity: 1 m³/h']}}
    block=plan(fs,(0,0,600,60))[0][0]
    fs._dense_nameplates={'pump':replace(block,x=0,y=100)}
    fs._dense_nameplate_source=deepcopy(fs.equipment_data)
    box=fixed_boxes(fs)[0]
    stream.route=Route(waypoints=[(-10,110),(box[2]+10,110)])
    assert any(i.code=='route-crosses-equipment-data' for i in fs.validate())
    fs.equipment_data['pump']['rows']=['Capacity: 2 m³/h']
    with pytest.raises(ValueError,match='EQUIPMENT_DATA_LAYOUT_STALE'):
        plan(fs,(0,0,600,60))


def test_capacity_overflow_never_silently_adds_a_second_nameplate_row():
    from pandid import Pump
    from pandid.geometry import Frame
    from pandid.render.nameplates import plan
    fs=Flowsheet('The one-row policy is retained at capacity')
    fs.layout_options.boundary_page='A1'
    for index in range(2):
        pump=fs.add(Pump('pump-'+str(index)))
        pump.frame=Frame(x=index*100,y=0,w=60,h=60)
        fs.equipment_data[pump.name]={'tags':'100-P-0'+str(index+1),
                                     'width':5000,'rows':['Capacity: source value']}
    blocks,bounds=plan(fs,(0,0,600,60))
    assert len({b.y for b in blocks})==1
    assert bounds[2]-bounds[0]>10000


def test_final_nameplate_row_reclaims_only_unused_gap_below_measured_ink():
    from copy import deepcopy
    from dataclasses import replace
    from pandid import Pump
    from pandid.geometry import Frame
    from pandid.render.nameplates import plan

    fs=Flowsheet('Measured ink bounds keep the complete common nameplate row')
    for i in range(2):
        pump=fs.add(Pump('pump-'+str(i)))
        pump.frame=Frame(x=i*300,y=0,w=60,h=60)
        fs.equipment_data[pump.name]={'tags':f'100-P-{i+1:02}',
            'rows':['Capacity: 41.37 m³/h'], 'font_size':14,'heading_font_size':24}
    original=plan(fs,(0,0,600,60))[0]
    fs._dense_nameplates={fs.units[b.unit_index].name:replace(b,y=800) for b in original}
    fs._dense_nameplate_source=deepcopy(fs.equipment_data)
    assert {b.y for b in plan(fs,(0,-20,600,400))[0]}=={800}
    blocks,_=plan(fs,(0,-20,600,400),fit_to_ink=True)
    assert {b.y for b in blocks}=={465}
    assert [b.annotation for b in blocks]==[b.annotation for b in original]
    assert plan(fs,(0,-20,600,500),fit_to_ink=True)[0]==blocks
    assert fs.equipment_data==fs._dense_nameplate_source


def test_equipment_caption_reserves_the_stroked_line_clearance():
    from pandid import Pump
    from pandid.geometry import Frame
    from pandid.routing.captions import equipment_tags
    from pandid.render.svg import SvgRenderer, _unit_label_box, escaped, _ink_pad, _stream_rung
    from pandid.portgeom import unit_box

    fs=Flowsheet('A route centre line must also clear its drawn ink')
    pump=fs.add(Pump('100-P-01'))
    pump.frame=Frame(x=100,y=100,w=60,h=60,label_pos='top')
    fs.drawio_metadata['units']={pump.name:{'attributes':{'layout-subsystem':'feed'}}}
    x0,y0,x1,y1=unit_box(pump,pump.frame)
    item=SvgRenderer()._unit_label_item(pump,pump.frame,x0,y0,x1-x0,y1-y0,escaped(pump.tag))
    x0,y0,x1,y1=_unit_label_box(item)
    pad=_ink_pad(_stream_rung(False))
    box=equipment_tags(fs)[pump]
    assert (box.x_min,box.y_min,box.x_max,box.y_max)==pytest.approx((x0-pad,y0-pad,x1+pad,y1+pad))


def test_line_caption_reservation_uses_clear_span_beside_an_occupied_midpoint():
    from pandid import Pump
    from pandid.geometry import Frame
    from pandid.routing.captions import line_plates
    from pandid.portgeom import port_point

    fs=Flowsheet('A label can move along its own line before routing')
    source=fs.add(Feed('source'));target=fs.add(Product('target'))
    source.frame=Frame(x=0,y=0,w=80,h=40)
    target.frame=Frame(x=400,y=0,w=80,h=40)
    obstacle=fs.add(Pump('nearby'))
    obstacle.frame=Frame(x=210,y=24,w=60,h=60,label_pos='bottom')
    stream=fs.connect(source.outlet,target.inlet,name='line')
    stream.display_label='100-L-001'
    fs.drawio_metadata['units']={u.name:{'attributes':{'layout-subsystem':'feed'}} for u in fs.units}
    box=line_plates(fs)['line']
    a=port_point(source,source.frame,'outlet');b=port_point(target,target.frame,'inlet')
    assert box.x_max < obstacle.frame.x or box.x_min > obstacle.frame.x+obstacle.frame.w
    assert (box.y_min+box.y_max)/2==pytest.approx(a[1])
    assert a[0]<box.x_min<box.x_max<b[0]


def test_explicit_adaptive_nameplates_fit_one_row_without_changing_type_or_values():
    from pandid import Pump
    from pandid.geometry import Frame
    from pandid.render.nameplates import plan
    from pandid.render.drawio import fitted_band
    fs=Flowsheet('Adaptive white space with fixed lettering')
    fs.layout_options.boundary_page='A1'
    for index in range(4):
        pump=fs.add(Pump('pump-'+str(index)))
        pump.frame=Frame(x=index*100,y=0,w=60,h=60)
        fs.equipment_data[pump.name]={'tags':f'100-P-{index+1:02}',
            'width':5000,'fit_width':True,'font_size':14,'heading_font_size':24,
            'rows':['Capacity: 41.37 m³/h','Material: SS316']}
    blocks,bounds=plan(fs,(0,0,fitted_band(fs,'A1')[0]-50,60))
    assert len({b.y for b in blocks})==1
    assert bounds[2]-bounds[0]<=fitted_band(fs,'A1')[0]-50
    for b in blocks:
        assert b.annotation.font_size==14 and b.annotation.title_font_size==24
        assert ' '.join(b.annotation.rows)=='Capacity: 41.37 m³/h Material: SS316'


def test_grouped_pfd_taps_keep_distinct_nozzles_and_both_parallel_witnesses():
    from pandid import Pump, Junction, Instrument
    from pandid.portgeom import port_point
    from pandid.profiles.process import apply
    fs=apply(Flowsheet('Grouped device with two witnessed tapping paths'))
    source=fs.add(Junction('source',outputs=2,header=True))
    target=fs.add(Junction('target',inputs=2,outputs=3,header=True))
    inlet=fs.add(Junction('inlet projection',inputs=2,header=True))
    outlet=fs.add(Junction('outlet projection',outputs=2,header=True))
    pump=fs.add(Pump('grouped pump'))
    fs.connect(inlet.outlets[0],pump.suction)
    fs.connect(pump.discharge,outlet.inlets[0])
    rows=[]
    for i in range(2):
        before=fs.add(Junction('before-'+str(i),header=True))
        after=fs.add(Junction('after-'+str(i),header=True))
        fs.connect(source.outlets[i],before.inlets[0])
        fs.connect(before.outlets[0],inlet.inlets[i])
        fs.connect(outlet.outlets[i],after.inlets[0])
        fs.connect(after.outlets[0],target.inlets[i])
        fs.add(Instrument('PIT-'+str(i))).attach(before,at='N')
        rows.append((before,after))
    fs.drawio_metadata['units']={u.name:{'id':u.name,'attributes':{'layout-subsystem':'process'}}
                                for u in fs.units}
    fs.drawio_metadata['units'][pump.name]['attributes']['equipment-group']='pair'
    for fan in (inlet,outlet):
        fs.drawio_metadata['units'][fan.name]['attributes']['projection-for']=pump.name
    fs.layout()
    for i,(before,after) in enumerate(rows):
        assert port_point(before,before.frame,'out_1')[1] == pytest.approx(
            port_point(inlet,inlet.frame,inlet.inlets[i].name)[1])
        assert port_point(after,after.frame,'in_1')[1] == pytest.approx(
            port_point(outlet,outlet.frame,outlet.outlets[i].name)[1])
    assert len({port_point(target,target.frame,p.name) for p in target.outlets})==3
    assert len(fs.streams)==10


def test_compound_footprint_reserves_the_internal_relief_spool():
    from pandid.geometry import Frame
    from pandid.layout.operating_banks import Assembly,footprint
    from pandid.portgeom import port_point
    fs=Flowsheet('Two fittings with one connected spool')
    a=fs.add(Valve('a'));b=fs.add(Valve('b'))
    fs.connect(a.outlet,b.inlet)
    frames={a:(0,0,30,20),b:(100,0,30,20)}
    assembly=Assembly('station',(a,b),frames,130,20)
    parts=footprint(fs,assembly,{})
    assert any(x<60<x+w and y<10<y+h for x,y,w,h in parts)


def test_intermediate_tag_plan_does_not_call_the_final_crossing_gate():
    from pandid import Instrument
    from pandid.geometry import Route
    from pandid.routing.captions import equipment_tags
    from pandid.render.drawio import _tag_pass
    from pandid.render.symbols import default_registry
    fs=Flowsheet('Unsettled crossing during obstacle repair')
    paths=[[(0,0),(100,0),(100,100)],[(50,-50),(99,-50),(99,1),(150,1)]]
    for i,points in enumerate(paths):
        a=fs.add(Feed('a'+str(i)));b=fs.add(Product('b'+str(i)))
        a.pin(port='outlet',x=points[0][0],y=points[0][1])
        b.pin(port='inlet',x=points[-1][0],y=points[-1][1])
        fs.connect(a.outlet,b.inlet)
    fs.add(Instrument('PIT',1)).annotate(high='PAHH')
    fs.layout()
    for stream,points in zip(fs.streams,paths):
        stream.route=Route(waypoints=points,manual=True)
    fs.drawio_metadata['units']={u.name:{'attributes':{'layout-subsystem':'process'}} for u in fs.units}
    equipment_tags(fs,settled=True)
    from pandid.routing.captions import reserve_leaders
    reserve_leaders(fs)
    assert fs._caption_repair_trace
    with pytest.raises(ValueError,match='CROSSING_CLEARANCE_REQUIRED'):
        _tag_pass(fs,default_registry,None,'auto')


def test_serial_path_wrap_keeps_its_final_station_with_its_predecessor():
    from pandid import Pump
    from pandid.layout.operating_paths import paths
    fs=Flowsheet('Serial path wrap')
    source,target=fs.add(Feed('source')),fs.add(Product('target'))
    pumps=[fs.add(Pump('station-'+str(i),width=70,height=70)) for i in range(4)]
    previous=source.outlet
    for pump in pumps:
        s=fs.connect(previous,pump.suction)
        s.display_label='LINE HOLD\nDN80 / DS1\nmembrane feed'
        previous=pump.discharge
    fs.connect(previous,target.inlet)
    fs.layout()
    assemblies=paths(fs,{u:'process' for u in pumps},{},set(),650)
    assert {u for a in assemblies for u in a.members}==set(pumps)
    assert all(len(a.members)>=2 and a.width<=650 for a in assemblies)
def test_shape_pack_tolerates_only_float_roundoff_at_the_assembly_origin():
    from pandid.layout.shape_pack import pack
    assert pack([('a',100,100,[(-2.8e-14,0,100,100)])],200,200) is not None
    with pytest.raises(ValueError,match='ASSEMBLY_FOOTPRINT_OUTSIDE_ENVELOPE'):
        pack([('a',100,100,[(-1.,0,100,100)])],200,200)


def test_compound_packing_keeps_connected_stations_near_each_other():
    from pandid.layout.shape_pack import pack
    shapes=[('a',180,50,[(0,0,180,50)]),('b',80,120,[(0,0,80,120)]),
            ('c',160,80,[(0,0,160,80)]),('d',60,60,[(0,0,60,60)])]
    links=[('a','d'),('a','b')]
    ordinary=pack(shapes,450,300)
    connected=pack(shapes,450,300,links=links)
    dimensions={key:(w,h) for key,w,h,_ in shapes}
    def length(result):
        return sum(abs(result[a][0]+dimensions[a][0]/2-result[b][0]-dimensions[b][0]/2)
                   +abs(result[a][1]+dimensions[a][1]/2-result[b][1]-dimensions[b][1]/2)
                   for a,b in links)
    assert length(connected)<length(ordinary)
    assert connected==pack(shapes,450,300,links=links)
    assert all(0<=connected[key][0]<=450-w and 0<=connected[key][1]<=300-h for key,w,h,_ in shapes)


def test_dense_flag_rail_follows_connected_equipment_instead_of_declaration_order(monkeypatch):
    from pandid import Pump
    from pandid.geometry import Frame
    from pandid.layout.operating_banks import Assembly
    from pandid.layout import dense_operating
    fs=Flowsheet('Composed feeds')
    lower,upper=fs.add(Feed('lower feed')),fs.add(Feed('upper feed'))
    a,b=fs.add(Pump('lower pump')),fs.add(Pump('upper pump'))
    fs.connect(lower.outlet,a.suction)
    fs.connect(upper.outlet,b.suction)
    for unit in fs.units:
        unit.frame=Frame(x=0,y=0,w=100,h=60)
    assemblies=[Assembly(p.name,(p,),{p:(0,0,100,60)},100,60) for p in (a,b)]
    monkeypatch.setattr(dense_operating,'pack',lambda *args,**kwargs:{a.name:(300,500),b.name:(300,100)})
    dense_operating.place(fs,assemblies,{},[],1000,1000)
    assert fs._dense_boundaries[upper.name][1] < fs._dense_boundaries[lower.name][1]
    assert fs._dense_boundaries[upper.name][0] == fs._dense_boundaries[lower.name][0]
    assert [u.name for u in fs.units]==['lower feed','upper feed','lower pump','upper pump']


def test_unit_tapped_balloon_does_not_chase_a_route_dependent_tag_cache():
    from pandid import Pump, Instrument
    from pandid.geometry import Frame
    from pandid.layout.attach import place_attached
    from pandid.routing.visibility import Rect
    fs=Flowsheet('Stable instrument attachment')
    pump=fs.add(Pump('pump'))
    pump.frame=Frame(x=200,y=200,w=70,h=70)
    instrument=fs.add(Instrument('PIT',1)).attach(pump,at='N',offset=80)
    fs.drawio_metadata['units']={pump.name:{'attributes':{'layout-subsystem':'process'}}}
    place_attached(fs)
    before=(instrument.frame.x,instrument.frame.y)
    fs._resolved_tag_boxes={pump:Rect(50,450,0,190)}
    assert not place_attached(fs)
    assert (instrument.frame.x,instrument.frame.y)==before
