import copy
from types import SimpleNamespace
import xml.etree.ElementTree as ET

from pandid import Feed, Flowsheet, Product
from pandid.geometry import Frame, Route
from pandid.units import HeldPipeEnd
from pandid.drawio_metadata import physical_page
from pandid.render.symbols import default_registry, wears_arrowhead
from pandid.render.svg import stream_polyline
from pandid.routing.terminal_clearance import arrow_lead_preserved, square_interior_micro_jogs


def test_physical_page_scales_native_gap_radius_without_scaling_the_constant():
    sheet=SimpleNamespace(print_scale=2.7,width_mm=841,height_mm=594)
    xml='<mxfile><diagram><mxGraphModel><root><mxCell id="s" style="strokeWidth=1;jumpStyle=gap;jumpSize=6;"/></root></mxGraphModel></diagram></mxfile>'
    tree=ET.fromstring(physical_page(xml,sheet))
    style=dict(p.split('=',1) for p in tree.find('.//mxCell').get('style').split(';') if '=' in p)
    factor=sheet.print_scale*100/96
    radius=(int(style['jumpSize'])-2)/2+float(style['strokeWidth'])
    assert abs(radius-3*factor) <= .25
    assert int(style['jumpSize']) == 13


def test_a_held_pipe_cut_is_a_continuing_bare_run():
    fs=Flowsheet('Held continuation')
    source=fs.add(Feed('source'));target=fs.add(HeldPipeEnd('held'))
    stream=fs.connect(source.outlet,target.pipe)
    assert not wears_arrowhead(stream,default_registry)


def test_crossing_repair_cannot_shorten_a_pfd_arrow_lead():
    fs=Flowsheet('Arrow clearance');fs._drawn_as='pfd'
    source=fs.add(Feed('source'));target=fs.add(Product('target'))
    stream=fs.connect(source.outlet,target.inlet)
    before=[(0,0),(200,0),(200,100),(400,100)]
    short=[(0,0),(388,0),(388,100),(400,100)]
    assert not arrow_lead_preserved(fs,stream,before,short)
    assert arrow_lead_preserved(fs,stream,before,[(0,0),(376,0),(376,100),(400,100)])
    fs._drawn_as='p&id'
    assert arrow_lead_preserved(fs,stream,before,short)


def test_four_point_micro_step_retains_both_nozzles_with_a_visible_dogleg():
    fs=Flowsheet('Near aligned nozzles')
    source=fs.add(Feed('source'));target=fs.add(Product('target'))
    source.frame=Frame(x=-50,y=-10,w=50,h=20)
    target.frame=Frame(x=40,y=-9.6,w=50,h=20)
    stream=fs.connect(source.outlet,target.inlet)
    from pandid.portgeom import port_point
    end=port_point(target,target.frame,'inlet')
    stream.route=Route(waypoints=[(0,0),(15,0),(15,end[1]),end])
    before=copy.deepcopy(stream.route.waypoints)
    square_interior_micro_jogs(fs)
    after=stream_polyline(stream)
    assert len(after)==6
    assert after[0]==before[0] and after[-1]==before[-1]
    assert all(a[0]==b[0] or a[1]==b[1] for a,b in zip(after,after[1:]))
    assert min(abs(a[0]-b[0])+abs(a[1]-b[1]) for a,b in zip(after,after[1:]))>10
    square_interior_micro_jogs(fs)
    assert stream_polyline(stream)==after


def test_whole_path_reroute_separates_nearly_coincident_ink():
    from pandid.routing.overlap_reroute import repair_one
    from pandid.routing.crossing_clearance import _overlaps
    fs=Flowsheet('Nearly coincident services');fs.layout_options.stream_spacing=14
    paths={0:[(0,0),(300,0),(300,120),(400,120)],
           1:[(0,50),(100,50),(100,.05),(350,.05),(350,170),(450,170)]}
    for key,points in paths.items():
        source=fs.add(Feed('source'+str(key)));target=fs.add(Product('target'+str(key)))
        source.frame=Frame(x=-50,y=points[0][1]-10,w=50,h=20)
        target.frame=Frame(x=points[-1][0],y=points[-1][1]-10,w=50,h=20)
        stream=fs.connect(source.outlet,target.inlet)
        stream.route=Route(waypoints=copy.deepcopy(points))
    result=repair_one(fs,paths,14,5)
    assert result is not None
    _,key,points,_=result
    assert points[0]==paths[key][0] and points[-1]==paths[key][-1]
    assert _overlaps({**paths,key:points},4)<_overlaps(paths,4)
    for stream in fs.streams:stream.route.manual=True
    assert repair_one(fs,paths,14,5) is None


def test_free_controller_recovers_exact_measurement_axis_without_moving_the_host():
    from pandid import Instrument, Pump
    from pandid.layout.control import _align_measurement
    fs = Flowsheet('Fractional measurement alignment')
    pump = fs.add(Pump('pump'))
    meter = fs.add(Instrument('FIT', 1)).attach(pump, at='N')
    meter.frame = Frame(x=100.13, y=200, w=60, h=60)
    controller = fs.add(Instrument('FIC', 1))
    fs.connect(meter.sig_out, controller.sig_in, kind='electric')
    assert _align_measurement(controller, 100, 80, 60, 60, [meter.frame]) == (100.13, 80)
    assert meter.frame.x == 100.13
    # An already occupied side or a sheet boundary retains the safe position.
    occupied = Frame(x=190.1, y=80, w=60, h=60)
    assert _align_measurement(controller, 100, 80, 60, 60, [occupied]) == (100, 80)
    assert _align_measurement(controller, 100, 80, 60, 60, [], (0,0,160,300)) == (100, 80)
    # Another free controller cannot become a moving alignment reference.
    meter.host = None
    assert _align_measurement(controller, 100, 80, 60, 60, []) == (100, 80)


def test_body_repair_reserves_ink_clearance_for_native_stroke_alignment():
    from pandid import Pump
    from pandid.routing.body_clearance import repair
    from pandid.routing.visibility import Rect
    fs = Flowsheet('Native pen alignment clearance')
    source = fs.add(Feed('source'))
    target = fs.add(Product('target'))
    obstacle = fs.add(Pump('obstacle'))
    source.frame = Frame(x=-50, y=-10, w=50, h=20)
    target.frame = Frame(x=400, y=190, w=50, h=20)
    obstacle.frame = Frame(x=175, y=100, w=50, h=40)
    stream = fs.connect(source.outlet, target.inlet)
    before = [(0,0), (100,0), (100,99.9), (300,99.9), (300,200), (400,200)]
    stream.route = Route(waypoints=copy.deepcopy(before))
    repair(fs)
    after = stream.route.waypoints
    assert after[0] == before[0] and after[-1] == before[-1]
    ink_box = Rect(174,226,99,141)
    assert not any(ink_box.intersects_segment(*a,*b) for a,b in zip(after,after[1:]))
    stream.route = Route(waypoints=copy.deepcopy(before), manual=True)
    repair(fs)
    assert stream.route.waypoints == before
