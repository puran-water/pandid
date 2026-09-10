"""Regression checks for the actual drafting defects found in native reviews."""
import xml.etree.ElementTree as ET
import pytest
from pandid import Block, Flowsheet, Junction
from pandid.spec import from_dict, to_dict
from pandid.render.crossings import crossing_order
from pandid.render.drawio import _hops
from pandid.drawing_regions import Region, Caption
from pandid.profiles.circle_h2o import block_diagram


def test_cyclic_horizontal_vertical_crossings_keep_all_native_gaps():
    routes={'a':[(0,0),(120,0),(120,120)],'b':[(60,-60),(60,60),(180,60)]}
    order,hops,lost=_hops(routes,'auto','gap')
    assert set(order)==set(hops)=={'a','b'} and not lost
    # Orientation is deliberately irrelevant; non-connectivity is the fact.
    for direction in ('vertical','horizontal'):
        assert _hops(routes,direction,'gap')[2]


def test_crossing_order_protects_the_terminal_arrow():
    routes={'long':[(100,-100),(100,100)], 'arrow':[(0,0),(105,0)]}
    order,lost=crossing_order(routes,5)
    assert order==['arrow','long'] and not lost


@pytest.mark.parametrize('inputs,outputs',[(1,2),(1,3),(3,1),(2,2),(1,6)])
def test_pipe_junctions_roundtrip_with_real_ports_and_without_triangles(inputs,outputs):
    fs=Flowsheet('Pipe connections')
    junction=fs.add(Junction('header',inputs=inputs,outputs=outputs))
    restored=from_dict(to_dict(fs)).units[0]
    assert len(restored.inlets)==inputs and len(restored.outlets)==outputs
    from pandid.render.symbols import default_registry
    assert default_registry.for_unit(junction).bare_run
    assert default_registry.for_unit(junction).width==4
    xml=fs.to_drawio(diagram='p&id')
    assert 'triangle' not in xml
    assert 'shape=line' in xml if junction.is_header else 'shape=ellipse' in xml


def test_region_caption_and_block_font_roundtrip_and_bound_the_page():
    fs=Flowsheet('Process lane')
    unit=fs.add(Block('101\nScreen',width=280,height=150,label_pos='center',font_size=22))
    unit.pin(x=0,y=50)
    fs.regions=[Region('headworks',-20,0,400,230,'Pre-Treatment',22)]
    fs.captions=[Caption('note',10,280,250,60,'Source-backed description',15)]
    clone=from_dict(to_dict(fs))
    assert to_dict(fs)==to_dict(clone)
    xml=clone.to_drawio(diagram='bfd')
    assert 'region-headworks' in xml and 'region-note' in xml and 'fontSize=22' in xml
    assert 'Source-backed description' in clone.to_svg(diagram='bfd')


def test_lane_layout_reserves_explicit_slots_and_preserves_every_identity():
    blocks=[{'key':k,'id':'uid-'+k,'label':f'{i+1:03}\nProcess {k}','lane':lane,'order':i,'attributes':{'puran-kind':'bfd-node'},
             **({'column':1} if k=='b' else {})} for i,(k,lane) in enumerate([('a','first'),('b','first'),('c','second')])]
    streams=[{'key':'001-01','id':'stream-1','source':'a','target':'b','attributes':{}},
             {'key':'002-01','id':'stream-2','source':'b','target':'c','attributes':{}}]
    fs=block_diagram('Review',blocks,streams,title_block=None,page_id='page',graph_attributes={},
                     lanes=[{'id':'first','title':'Pre-Treatment'},{'id':'second','title':'Biological Treatment'}])
    xml=ET.fromstring(fs.to_drawio(diagram='bfd',jump_direction='auto'))
    objects={o.get('id'):o for o in xml.iter('object')}
    sizes={tuple(objects['uid-'+k].find('mxCell/mxGeometry').get(f) for f in ('width','height')) for k in 'abc'}
    assert len(sizes)==1
    ids = {o.get('id') for o in xml.iter() if o.get('id')}
    assert {'bfd-lane-first','bfd-lane-second','stream-1','stream-2'} <= ids
    assert fs.units[0].frame.x != fs.units[1].frame.x


def test_secondary_material_retains_connectivity_with_lighter_native_stroke():
    fs=Flowsheet('Weights')
    a,b,c=[fs.add(Block(k)) for k in 'ABC']
    main=fs.connect(a.outlets[0],b.inlets[0],name='main')
    secondary=fs.connect(b.outlets[0],c.inlets[0],name='secondary');secondary.flow_class='secondary'
    root=ET.fromstring(from_dict(to_dict(fs)).to_drawio())
    cells={c.get('id'):c for c in root.iter('mxCell')}
    def weight(cid):return float(dict(p.split('=',1) for p in cells[cid].get('style').split(';') if '=' in p)['strokeWidth'])
    assert weight('s0')==2*weight('s1')
    with pytest.raises(ValueError,match='flow_class'):secondary.flow_class='electrical'


def test_parallel_pumps_and_inline_isolations_share_each_branch_elevation():
    from pandid import Pump, Valve
    from pandid.portgeom import port_point
    fs=Flowsheet('Parallel trains');fs.layout_options.parallel_trains=True
    source=fs.add(Junction('in',outputs=3));target=fs.add(Junction('out',inputs=3,outputs=1))
    branches=[]
    for i in range(3):
        a=fs.add(Valve('HV-in-'+str(i)));p=fs.add(Pump('P-'+str(i),variant='rotary_lobe'));b=fs.add(Valve('HV-out-'+str(i)))
        for left,right in [(source.outlets[i],a.inlet),(a.outlet,p.suction),(p.discharge,b.inlet),(b.outlet,target.inlets[i])]:fs.connect(left,right)
        branches.append((a,p,b))
    fs.layout()
    tracks=[]
    for a,p,b in branches:
        ys=[port_point(u,u.frame,port)[1] for u,port in [(a,'inlet'),(p,'suction'),(p,'discharge'),(b,'inlet')]]
        assert max(ys)-min(ys)<1e-6
        tracks.append(ys[0])
    assert len(set(tracks))==3
    root=ET.fromstring(fs.to_drawio(diagram='p&id'))
    header=next(c for c in root.iter('mxCell') if 'shape=line;direction=south' in c.get('style',''))
    assert 'anchorPointDirection=0' in header.get('style')
    assert 'legacyAnchorPoints=1' in header.get('style')


def test_subpixel_automatic_terminal_jog_is_squared_without_moving_nozzles():
    from pandid.geometry import Route
    from pandid.routing.terminal_clearance import square_micro_jogs
    fs=Flowsheet('Small terminal jog')
    a=fs.add(Block('A')).pin(x=0,y=0);b=fs.add(Block('B')).pin(x=300,y=100)
    s=fs.connect(a.outlets[0],b.inlets[0]);fs.layout()
    from pandid.portgeom import port_point
    start=port_point(a,a.frame,s.source.name);end=port_point(b,b.frame,s.dest.name)
    s.route=Route(waypoints=[start,(start[0]+.1,start[1]),(start[0]+.1,end[1]),end])
    square_micro_jogs(fs)
    assert s.route.waypoints[0]==start and s.route.waypoints[-1]==end
    assert all(a[0]==b[0] or a[1]==b[1] for a,b in zip(s.route.waypoints,s.route.waypoints[1:]))
    assert len(s.route.waypoints)==3


def test_nameplate_heading_is_measured_separately_from_its_data():
    from pandid import Annotation
    fs=Flowsheet('Nameplate heading')
    fs.add(Block('P-01'))
    fs.equipment_data={'P-01':{'tags':'250-P-01 / 250-P-02 / 250-P-03','rows':['CAPACITY: 53 m3/h'],
                              'font_size':14,'heading_font_size':20}}
    fs.annotations.append(Annotation(title='Review',rows=['Data supplied'],title_font_size=18))
    clone=from_dict(to_dict(fs))
    assert to_dict(clone)==to_dict(fs)
    xml=ET.fromstring(clone.to_drawio())
    heading=next(c for c in xml.iter('mxCell') if c.get('id')=='np0-t')
    assert 'font-size:20px' in heading.get('value','') or 'fontSize=20' in heading.get('style','')
    with pytest.raises(ValueError,match='title_font_size'):Annotation(title_font_size=float('nan'))
