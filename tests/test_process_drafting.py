"""Observed drawing invariants, independent of topology density."""
import xml.etree.ElementTree as ET
import pytest
from pandid import Flowsheet, Feed, Product, Pump, Instrument, ConcreteBasin, AirDiffuser
from pandid.profiles.process import apply
from pandid.portgeom import unit_box


def example(extra=False):
    fs=apply(Flowsheet('Example'))
    src=fs.add(Feed('feed',width=190,height=85)); dst=fs.add(Product('product',width=190,height=85))
    src.reference_code='A'; dst.reference_code='B'
    src.display_label='WATER';dst.display_label='WATER'
    pump=fs.add(Pump('101-P-01'))
    fs.connect(src.outlet,pump.suction).display_label=''
    if extra:
        other=fs.add(Pump('101-P-02'));fs.connect(pump.discharge,other.suction).display_label=''
        fs.connect(other.discharge,dst.inlet).display_label=''
    else: fs.connect(pump.discharge,dst.inlet).display_label=''
    fs.add(Instrument('101-PI-01')).attach(pump,at='N')
    return fs


def style(cell):
    return dict(x.split('=',1) for x in cell.get('style','').split(';') if '=' in x)


def test_adding_equipment_does_not_change_printed_flags_balloons_or_text():
    values=[]
    for extra in (False,True):
        fs=example(extra)
        doc=ET.fromstring(fs.to_drawio(page_size='A1'))
        def signature(name):
            n=next(i for i,u in enumerate(fs.units) if u.name==name)
            cell=doc.find(f".//mxCell[@id='u{n}']")
            g=cell.find('mxGeometry');s=style(cell)
            return tuple(round(float(g.get(k)),4) for k in ('width','height'))+(s.get('fontSize'),s.get('strokeWidth'))
        values.append((signature('feed'),signature('101-PI-01'),signature('101-P-01')))
    assert values[0]==values[1]


def test_fixed_drafting_refuses_capacity_instead_of_shrinking():
    fs=example(True);fs.units[2].pin(x=100,y=100);fs.units[3].pin(x=10000,y=100)
    with pytest.raises(ValueError,match='FIXED_SCALE_CAPACITY'):
        fs.to_drawio(page_size='A1')


def basin_example():
    f=apply(Flowsheet('Aeration'))
    b=f.add(ConcreteBasin('101-T-01',inputs=2)); a=f.add(AirDiffuser('101-DF-01'))
    src=f.add(Feed('Feed'));air=f.add(Feed('Air'));dst=f.add(Product('Product'))
    f.contain(a,b)
    for x,y in [(src.outlet,b.inlets[0]),(b.outlets[0],dst.inlet),(air.outlet,a.air_in)]: f.connect(x,y).display_label=''
    s=f.connect(a.dispersed_air,b.inlets[1]);s.representation='internal';s.display_label=''
    return f,b,a,s


def test_basin_contains_diffuser_and_air_enters_through_open_top():
    from pandid.containment import wall_boxes
    fs,b,a,internal=basin_example();fs.layout();fs.route()
    x,y,r,bottom=unit_box(a,a.frame)
    assert b.frame.x < x < r < b.frame.x_max
    assert b.frame.y < y < bottom < b.frame.y_max
    line=next(s for s in fs.streams if s.dest is a.air_in)
    assert any(p[1] < b.frame.y for p in line.route.waypoints)
    assert not any(w.intersects_segment(*p,*q) for w in wall_boxes(b) for p,q in zip(line.route.waypoints,line.route.waypoints[1:]))
    doc=ET.fromstring(fs.to_drawio(page_size='A1',diagram='p&id'))
    cell=doc.find(".//mxCell[@id='s3']")
    assert cell is not None and cell.get('visible')=='0'
    assert internal.route is None
    assert {s.name for s in fs.streams}=={'S1','S2','S3','S4'}
    flags=[u for u in fs.units if u.kind=='feed']
    assert len({round(unit_box(u,u.frame)[0],5) for u in flags})==1


def test_containment_roundtrip_and_rejection_of_external_internal_connection():
    fs,b,a,s=basin_example()
    restored=Flowsheet.from_dict(fs.to_dict())
    assert restored.containments=={a.name:b.name}
    assert restored.streams[-1].representation=='internal'
    restored.to_drawio(page_size='A1')
    fs.streams[0].representation='internal'
    with pytest.raises(ValueError,match='INTERNAL_CONNECTION_OUTSIDE_BASIN'):
        fs.layout()


def test_only_declared_host_is_accessible_to_diffuser_air_line():
    from pandid.containment import accessible
    from pandid.routing.visibility import VisibilityGraph,Rect
    fs,b,a,_=basin_example();fs.layout()
    supply=next(s for s in fs.streams if s.dest is a.air_in)
    allowed=accessible(fs,supply)
    assert allowed=={b.name}
    external=next(s for s in fs.streams if s.dest.owner is b)
    assert not accessible(fs,external)
    closed=VisibilityGraph(fs)
    opened=VisibilityGraph(fs,accessible=allowed)
    probe=(b.frame.x+40,b.frame.y-10,b.frame.x+40,b.frame.cy)
    assert any(o.intersects_segment(*probe) for o in closed.obstacles)
    assert not any(o.intersects_segment(*probe) for o in opened.obstacles)


def test_near_terminal_crossing_can_clear_more_than_two_parallel_tracks(monkeypatch):
    import json
    from pathlib import Path
    from types import SimpleNamespace
    from pandid.geometry import Frame,Route
    from pandid.routing.crossing_clearance import repair,_overlaps
    from pandid.render.crossings import crossing_order
    data=json.loads((Path(__file__).parent/'fixtures/crowded_crossing.json').read_text())
    units=[SimpleNamespace(kind='unit',frame=Frame(x=a,y=b,w=c-a,h=d-b)) for a,b,c,d in data['bodies']]
    streams=[SimpleNamespace(route=Route(waypoints=p,manual=False)) for p in data['paths']]
    fs=SimpleNamespace(units=units,streams=streams,containments={},captions=[],regions=[],layout_options=SimpleNamespace(stream_spacing=14))
    monkeypatch.setattr('pandid.render.svg.stream_polyline',lambda s:s.route.waypoints)
    before={i:s.route.waypoints for i,s in enumerate(streams)}
    assert crossing_order(before,5)[1]
    ends=[(p[0],p[-1]) for p in before.values()]
    repair(fs)
    after={i:s.route.waypoints for i,s in enumerate(streams)}
    assert not crossing_order(after,5)[1]
    assert _overlaps(after)<=_overlaps(before)
    assert [(p[0],p[-1]) for p in after.values()]==ends
