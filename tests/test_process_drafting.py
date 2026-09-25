"""Observed drawing invariants, independent of topology density."""
import xml.etree.ElementTree as ET
import pytest
from pandid import Flowsheet, Feed, Product, Pump, Instrument, ConcreteBasin, AirDiffuser, Block, Junction
from pandid.profiles.process import apply, lettering
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


def test_house_line_number_search_can_leave_a_crowded_corridor():
    from pandid.render.svg import stream_numbers, _meets, stream_polyline
    fs=Flowsheet('Line number clearance')
    source=fs.add(Feed('Feed')).pin(x=100,y=100)
    target=fs.add(Product('Product')).pin(x=600,y=100)
    stream=fs.connect(source.outlet,target.inlet)
    stream.display_label='100-L-001 / DN80 / SPEC'
    fs.stream_labels.font_size=14
    fs.layout();fs.route()
    points=stream_polyline(stream);y=points[0][1]
    reservation=(-10000,y-200,10000,y+200)
    crowded=stream_numbers(fs,[reservation],None,'vertical')[0]
    assert _meets(crowded.box,reservation)
    apply(fs)
    clear=stream_numbers(fs,[reservation],None,'vertical')[0]
    assert not _meets(clear.box,reservation)
    assert clear.text==crowded.text


@pytest.mark.parametrize('value',[0,-1,1.5,True])
def test_line_number_search_budget_requires_positive_integer(value):
    fs=Flowsheet('Invalid search budget');fs.layout_options.stream_label_bands=value
    with pytest.raises(ValueError,match='stream_label_bands'):
        fs.layout_options.validate()


def _short_supply_link(block_top_line=True):
    """The short 000-04 connection beside a five-nozzle boundary block."""
    fs = Flowsheet("Short supply leader")
    supply = fs.add(Block(
        "BL Chemical Supply", inputs=0, outputs=["E"] * 5,
        width=180, height=150)).pin(x=100, y=100)
    antiscalant = fs.add(Block(
        "Antiscalant Dosing", inputs=["W"], outputs=0,
        width=180, height=150)).pin(x=325, y=100)
    receivers = [
        fs.add(Block(f"Other {i}", inputs=["W"], outputs=0,
                     width=140, height=80)).pin(x=600 + 25 * i, y=y)
        for i, y in enumerate((20, 210, 320, 430))
    ]

    short = fs.connect(supply.out_2, antiscalant.in_1, name="000-04")
    siblings = zip(
        (supply.out_1, supply.out_3, supply.out_4, supply.out_5),
        receivers,
        ("000-03", "000-05", "000-06", "000-07"),
    )
    for port, receiver, name in siblings:
        if name == "000-03" and not block_top_line:
            continue
        line = fs.connect(port, receiver.in_1, name=name)
        line.display_label = ""

    short.display_label = "000-04"
    fs.stream_labels.font_size = 22
    fs.layout_options.stream_label_bands = 7
    fs.layout_options.strict_label_clearance = True
    fs.layout()
    fs.route()
    return fs, short


def test_a_short_supply_link_uses_a_line_crossing_leader_as_the_last_resort():
    """A sibling line may be crossed only after every clean leader loses."""
    from pandid.render.svg import (
        _crosses, _ink, _meets, _near_segment, label_findings,
        stream_numbers, stream_polyline,
    )

    fs, short = _short_supply_link()
    number = stream_numbers(
        fs, [], None, "vertical", (50, 0, 850, 550))[0]

    assert number.leader is not None
    assert number.leader_crossed == ("000-03",)
    assert any(
        _near_segment(number.leader[1], start, end)
        for start, end in zip(stream_polyline(short), stream_polyline(short)[1:])
    ), "the leader must land on 000-04's own run"
    assert not [
        unit.name for unit in fs.units
        if _crosses(*number.leader, unit_box(unit, unit.frame))
    ]
    assert not [
        line.line for line in _ink(fs, "vertical")
        if line.line != short.name and _meets(number.box, line.box)
    ], "the halo must not paint out another line"

    issues = label_findings(fs, "none", [number], "vertical")
    crossed = [issue for issue in issues if issue.code == "leader-crosses-line"]
    assert len(crossed) == 1 and crossed[0].severity == "warning"
    assert "000-04" in crossed[0].message and "000-03" in crossed[0].message
    assert not [
        issue for issue in issues
        if issue.code == "leader-placement-unresolved"
    ]


def _crossing_leader_at(fs, short, seg, box):
    """The last-resort leader a halo at *box* would draw to *seg*.

    Scored the way the stream-number search scores it, so the test can
    compare the leader the search chose against one it passed over.
    """
    from pandid.render.svg import _ink, _line_crossing_leader, _obstacle

    (sx1, sy1), (sx2, sy2) = seg
    axis, at = (("v", (sx1 + sx2) / 2) if abs(sx2 - sx1) < abs(sy2 - sy1)
                else ("h", (sy1 + sy2) / 2))
    relevant = [line for line in _ink(fs, "vertical")
                if not (line.axis == axis and abs(line.at - at) < 0.5)]
    crossing = [line for line in relevant
                if line.line and line.line != short.name and line.kind != "tap"]
    hard = [_obstacle(unit_box(u, u.frame)) for u in fs.units] + [
        line.box for line in relevant if line not in crossing]
    leader, crossed, _keys = _line_crossing_leader(box, seg, hard, crossing)
    return leader, crossed


def _length(leader):
    import math
    (ax, ay), (bx, by) = leader
    return math.hypot(bx - ax, by - ay)


def test_among_leaders_crossing_as_many_lines_the_shorter_wins():
    """Owner ruling 2026-09-25: fewest lines crossed, then the shortest leader.

    Two halos on the short supply link both need a leader across 000-03
    and nothing else. The one nearer the run ties back 62.6 units the
    long way round; the one a little further off drops 51.2 units
    straight onto it. Ranking by halo distance before length chose the
    long one; the reader follows the leader, not the halo, so the short
    one must win. No cap is involved: nothing here is refused for length.
    """
    from pandid.render.svg import stream_numbers

    fs, short = _short_supply_link()
    number = stream_numbers(
        fs, [], None, "vertical", (50, 0, 850, 550))[0]

    assert number.leader is not None
    assert number.leader_crossed == ("000-03",)

    # The halo the old ranking chose: written along the horizontal leg,
    # nearer the run, crossing the same one line, and longer.
    nearer, nearer_crossed = _crossing_leader_at(
        fs, short, number.seg, (208.73, 55.2, 303.77, 83.8))
    assert nearer_crossed == number.leader_crossed
    assert _length(nearer) == pytest.approx(62.63, abs=0.01)

    assert _length(number.leader) < _length(nearer)
    assert tuple(value for point in number.leader for value in point) == pytest.approx(
        (285.1, 95.04, 296.3333333333, 145.0))


def test_a_clean_short_supply_leader_is_the_shortest_clean_one():
    """Three sibling lines do not license the fallback while a clean route exists.

    Among the clean leaders the shortest wins before the halo's distance
    (owner ruling, 2026-09-25): 51.2 units, where the nearest clean halo's
    leader ran 94.9 units to the far end of the run.
    """
    from pandid.render.svg import _crosses, _ink, label_findings, stream_numbers

    fs, short = _short_supply_link(block_top_line=False)
    number = stream_numbers(
        fs, [], None, "vertical", (50, 0, 850, 550))[0]

    assert number.leader is not None
    assert tuple(value for point in number.leader for value in point) == pytest.approx(
        (285.1, 95.04, 296.3333333333, 145.0))
    assert _length(number.leader) < 94.88
    assert getattr(number, "leader_crossed", ()) == ()
    assert not [
        line.line for line in _ink(fs, "vertical")
        if line.line != short.name and _crosses(*number.leader, line.box)
    ]
    assert not label_findings(fs, "none", [number], "vertical")


def test_svg_and_drawio_report_the_same_line_crossing_leader():
    def render(kind):
        fs, _short = _short_supply_link()
        document = getattr(fs, f"to_{kind}")(
            check=False, jump_direction="vertical")
        issues = [
            (issue.severity, issue.code, issue.message)
            for issue in fs.warnings
            if issue.code in {"leader-crosses-line", "leader-placement-unresolved"}
        ]
        return document, issues

    svg, svg_issues = render("svg")
    drawio, drawio_issues = render("drawio")
    assert drawio_issues == svg_issues
    assert len(svg_issues) == 1 and svg_issues[0][1] == "leader-crosses-line"
    assert '<line x1=' in svg
    assert 'id="s0-lead"' in drawio


def test_house_line_number_uses_clear_external_paper_when_every_nearby_band_is_taken():
    from pandid.render.svg import stream_numbers, _crosses
    fs = Flowsheet('External caption')
    source = fs.add(Block('source', inputs=0, outputs=['S'], width=180, height=100))
    target = fs.add(Block('target', inputs=['N'], outputs=0, width=180, height=100))
    source.pin(x=410, y=100)
    target.pin(x=410, y=230)
    line = fs.connect(source.out_1, target.in_1)
    line.display_label = '801-04'
    fs.stream_labels.font_size = 22
    fs.layout_options.stream_label_bands = 7
    fs.layout_options.strict_label_clearance = True
    fs.layout(); fs.route()
    number = stream_numbers(fs, [], None, 'vertical', (200, 50, 800, 450))[0]
    assert number.leader is not None and number.crossed == ()
    assert not any(
        _crosses(*number.leader, unit_box(unit, unit.frame)) for unit in fs.units
    )


def test_a_displaced_line_number_never_leads_through_the_unit_between_it_and_its_run():
    """A clear halo on the far side of a unit is not a usable label position.

    The short run cannot carry ``801-04``, and the two side blocks consume the
    nearby bands.  The closest remaining paper is below ``target``; accepting
    it makes every possible leader cut the target's body and lettering.  The
    bounded search must leave that placement unresolved instead of drawing the
    crossing leader.
    """
    from pandid.render.svg import _crosses, label_findings, stream_numbers

    fs = Flowsheet("Leader clearance")
    source = fs.add(Block("source", inputs=0, outputs=["S"], width=180, height=100))
    target = fs.add(Block("target", inputs=["N"], outputs=0, width=180, height=100))
    source.pin(x=410, y=100)
    target.pin(x=410, y=230)
    fs.add(Block("left", width=70, height=26)).pin(x=330, y=202)
    fs.add(Block("right", width=70, height=26)).pin(x=600, y=202)
    line = fs.connect(source.out_1, target.in_1)
    line.display_label = "801-04"
    fs.stream_labels.font_size = 22
    fs.layout_options.stream_label_bands = 7
    fs.layout_options.strict_label_clearance = True
    fs.layout()
    fs.route()

    number = stream_numbers(fs, [], None, "vertical", (300, 50, 680, 450))[0]
    crossed = sorted(
        unit.name for unit in fs.units
        if number.leader is not None and _crosses(*number.leader, unit_box(unit, unit.frame))
    )
    assert not crossed, f"801-04's leader crosses {', '.join(crossed)}"
    assert number.leader is None
    unresolved = [
        issue for issue in label_findings(fs, "none", [number], "vertical")
        if issue.code == "leader-placement-unresolved"
    ]
    assert len(unresolved) == 1
    assert "801-04" in unresolved[0].message


def test_nameplate_row_tracks_displaced_captions_in_both_writers(monkeypatch):
    import pandid.render.drawio as drawio
    import pandid.render.svg as svg
    original=svg.stream_numbers
    displacement=[0]
    def numbers(*args,**kw):
        items=original(*args,**kw)
        n=items[0];dy=displacement[0]
        def move(box):return None if box is None else (box[0],box[1]+dy,box[2],box[3]+dy)
        items[0]=n._replace(y=n.y+dy,box=move(n.box),words=move(n.words))
        return items
    monkeypatch.setattr(drawio,'stream_numbers',numbers)
    monkeypatch.setattr(svg,'stream_numbers',numbers)
    fs=example();fs.streams[0].display_label='100-L-001 / DN80 / LONG LINE SPECIFICATION'
    fs.equipment_data={'101-P-01':{'tags':'101-P-01','rows':['TYPE: Pump','DUTY: Example']}}
    native_rows=[];svg_rows=[]
    for dy in (0,300):
        displacement[0]=dy
        doc=ET.fromstring(fs.to_drawio(page_size='A1'))
        row=doc.find(".//mxCell[@id='np2']/mxGeometry")
        pump=doc.find(".//mxCell[@id='u2']/mxGeometry")
        native_rows.append(float(row.get('y'))-float(pump.get('y')))
        image=ET.fromstring(fs.to_svg(page_size='A1'))
        heading=next(t for t in image.iter('{http://www.w3.org/2000/svg}text')
                     if ''.join(t.itertext())=='101-P-01' and t.get('font-weight')=='bold')
        svg_rows.append(float(heading.get('y')))
    assert native_rows[1] > native_rows[0]+100
    assert svg_rows[1] > svg_rows[0]+100


def basin_example():
    f=apply(Flowsheet('Aeration'))
    b=f.add(ConcreteBasin('101-T-01',inputs=2)); a=f.add(AirDiffuser('101-DF-01'))
    src=f.add(Feed('Feed'));air=f.add(Feed('Air'));dst=f.add(Product('Product'))
    f.contain(a,b)
    for x,y in [(src.outlet,b.inlets[0]),(b.outlets[0],dst.inlet),(air.outlet,a.air_in)]: f.connect(x,y).display_label=''
    s=f.connect(a.dispersed_air,b.inlets[1]);s.representation='internal';s.display_label=''
    return f,b,a,s


@pytest.mark.parametrize('dimensions', [(400,300), (700,450)])
def test_basin_contains_diffuser_and_air_enters_through_open_top(dimensions):
    from pandid.containment import wall_boxes
    fs,b,a,internal=basin_example();b.width,b.height=dimensions;fs.layout();fs.route()
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
    # Both writers must handle semantic internal transfers without a pipe.
    restored.to_svg(page_size='A1')
    fs.streams[0].representation='internal'
    with pytest.raises(ValueError,match='INTERNAL_CONNECTION_OUTSIDE_BASIN'):
        fs.layout()


@pytest.mark.parametrize('damage', ['balloon', 'flag', 'text', 'alignment', 'lineweight'])
def test_set_audit_rejects_one_page_with_different_drafting(damage):
    from pandid.profiles.process import inspect_drawio
    root=ET.Element('mxfile')
    for extra in (False,True):
        fs=example(extra)
        fs.drawio_metadata={'page_id': str(extra), 'units': {
            u.name: {'id': u.name, 'attributes': {'puran-kind':'entity',
                'symbol-key': 'boundary.reference' if u.kind in {'feed','product'} else
                    'instrument.field' if u.kind=='instrument' else 'pump.centrifugal'}}
            for u in fs.units}, 'streams': {
                s.name: {'id': s.name, 'attributes': {'puran-kind': 'connection',
                    'connection-kind': 'material', 'flow-class': 'main'}} for s in fs.streams}}
        # A second feed proves that one off-column flag is rejected.
        if damage=='alignment':
            f=fs.add(Feed('air',width=190,height=85));f.reference_code='C'
            fs.drawio_metadata['units']['air']={'id':'air','attributes':{
                'puran-kind':'entity','symbol-key':'boundary.reference'}}
            pump=fs.add(Pump('202-P-01'))
            product=fs.add(Product('waste',width=190,height=85))
            fs.connect(f.outlet,pump.suction).display_label=''
            fs.connect(pump.discharge,product.inlet).display_label=''
        root.extend(ET.fromstring(fs.to_drawio(page_size='A1')).findall('diagram'))
    assert inspect_drawio(root)['samples']['symbol:instrument.field']['appearances']==2
    page=root.findall('diagram')[1]
    uid='S1' if damage=='lineweight' else '101-PI-01' if damage in {'balloon','text'} else 'feed'
    cell=page.find(f".//object[@id='{uid}']/mxCell")
    if damage in {'text','lineweight'}:
        key='fontSize' if damage=='text' else 'strokeWidth'
        values=style(cell);values[key]=str(float(values[key])+1)
        cell.set('style',';'.join(k+'='+v for k,v in values.items())+';')
    else:
        geo=cell.find('mxGeometry');key='x' if damage=='alignment' else 'width'
        geo.set(key,str(float(geo.get(key))+1))
    with pytest.raises(ValueError,match='INCONSISTENT_PRINTED_SIZE|BOUNDARY_COLUMNS_MISALIGNED'):
        inspect_drawio(root)


def test_set_audit_keeps_declared_main_and_secondary_energy_weights_distinct():
    from pandid.profiles.process import inspect_drawio
    root=ET.Element('mxfile')
    for line_class in ('main','secondary'):
        fs=example()
        for stream in fs.streams:
            stream.kind='energy'
            stream.flow_class=line_class
        fs.drawio_metadata={'page_id':line_class, 'streams': {
            s.name: {'id':s.name,'attributes': {'puran-kind':'connection',
                'connection-kind':'energy','flow-class':line_class}} for s in fs.streams}}
        root.extend(ET.fromstring(fs.to_drawio(page_size='A1')).findall('diagram'))
    samples=inspect_drawio(root)['samples']
    assert samples['lineweight:energy:main']['value'][0] == 2*samples['lineweight:energy:secondary']['value'][0]


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


def _tick_fixture():
    """A feed that drops to a header and runs on to a selector.

    Reproduces the tick-length leader the shortest-first ranking found on the
    LB TEX r05 IX sheet (330-L-001): a halo parked hard against the run's own
    bend, tied back by a leader shorter than its own arrowhead.
    """
    fs = Flowsheet("tick")
    feed = fs.add(Feed("FEED", width=190, height=85))
    head = fs.add(Junction("HDR", inputs=1, outputs=1))
    sel = fs.add(Block("SELECTOR", inputs=1, outputs=1, label_pos="center"))
    out = fs.add(Product("OUT", width=190, height=85))
    feed.pin(port="outlet", x=100, y=100)
    head.pin(x=200, y=160)
    sel.pin(x=700, y=115)
    out.pin(port="inlet", x=1100, y=160)
    first = fs.connect(feed.outlet, head.inlets[0])
    first.display_label = "330-L-001 / SIZE HOLD / CLASS HOLD"
    second = fs.connect(head.outlets[0], sel.in_1)
    second.display_label = "330-L-003 / SIZE HOLD / CLASS HOLD"
    fs.connect(sel.out_1, out.inlet).display_label = ""
    lettering(fs, body=17, heading=17)
    fs.layout_options.strict_label_clearance = True
    fs.layout()
    fs.route()
    return fs


def test_no_leader_is_shorter_than_two_arrowheads():
    """Owner ruling 2026-09-25: shortest first, but never a tick.

    A leader shorter than its own head is an arrowhead with no line behind it,
    and at two heads it still barely reads as a leader. The floor is two
    leader heads, derived from the head, never a bare number -- about 3.8 mm
    at the house 1:2.21 scale. It is a floor, not the length cap the owner
    ruled out: nothing long is refused.
    """
    import math
    from pandid.render.svg import _LEADER_HEAD, stream_numbers

    fs = _tick_fixture()
    numbers = stream_numbers(fs, [], None, "vertical", None)
    ticks = [(n.name, round(math.hypot(n.leader[1][0] - n.leader[0][0],
                                       n.leader[1][1] - n.leader[0][1]), 2))
             for n in numbers if n.leader is not None
             and math.hypot(n.leader[1][0] - n.leader[0][0],
                            n.leader[1][1] - n.leader[0][1]) < 2 * _LEADER_HEAD]
    assert ticks == []


# --- own-line rule (owner rulings 2026-09-25) ---------------------------------
#
# A line number led away from its run must not be written along another named
# line at a clear gap less than or equal to its gap to its own line, within the
# spread of the ink pads a line can be drawn with. The checks below measure that
# independently of the engine: the caption's halo box against each line's padded
# ink box, and "along" by the engine's own _along share over the other line's
# collinear pieces.


def _own_line_measure(fs, number):
    """(own gap, nearest other line along the caption and its gap), or Nones."""
    import math
    from pandid.render.svg import _along, _ink, _ink_pad
    from pandid.render.weights import LineWeight

    def gap(a, b):
        dx = max(b[0] - a[2], a[0] - b[2], 0.0)
        dy = max(b[1] - a[3], a[1] - b[3], 0.0)
        return math.hypot(dx, dy)

    ink = _ink(fs, "vertical")
    box, vertical = number.box, number.vertical
    own = min(gap(box, line.box) for line in ink if line.line == number.name)
    axis = "v" if vertical else "h"
    runs = {}
    for line in ink:
        if line.line and line.line != number.name and line.kind == "pipe" and line.axis == axis:
            lo, hi = (line.y0, line.y1) if vertical else (line.x0, line.x1)
            runs.setdefault((line.line, round(line.at, 3)), []).append((lo, hi, line.box))
    nearest = None
    for (name, _at), pieces in runs.items():
        if _along(box, vertical, min(p[0] for p in pieces), max(p[1] for p in pieces)):
            g = min(gap(box, p[2]) for p in pieces)
            if nearest is None or g < nearest[1]:
                nearest = (name, g)
    tolerance = _ink_pad(LineWeight.MAIN_FLOW) - _ink_pad(LineWeight.DETAIL)
    return own, nearest, tolerance


def _junction_tie():
    """330-L-001 as LB TEX r05 ix-1 drew it: a feed that drops and runs a short
    way to a header, where its line runs straight on as 330-L-003. The number
    settled under the junction with its own leg and 330-L-003 exactly as far
    above it -- a tie -- so it read as 330-L-003's."""
    fs = Flowsheet("junction tie")
    feed = fs.add(Feed("FEED", width=190, height=85))
    head = fs.add(Junction("HDR", inputs=1, outputs=1))
    sel = fs.add(Block("SELECTOR", inputs=1, outputs=1, label_pos="center"))
    out = fs.add(Product("OUT", width=190, height=85))
    feed.pin(port="outlet", x=100, y=100)
    head.pin(x=280, y=160)
    sel.pin(x=700, y=115)
    out.pin(port="inlet", x=1100, y=160)
    first = fs.connect(feed.outlet, head.inlets[0])
    first.display_label = "330-L-001 / SIZE HOLD / CLASS HOLD"
    second = fs.connect(head.outlets[0], sel.in_1)
    second.display_label = "330-L-003 / SIZE HOLD / CLASS HOLD"
    fs.connect(sel.out_1, out.inlet).display_label = ""
    lettering(fs, body=17, heading=17)
    fs.layout_options.strict_label_clearance = True
    fs.layout()
    fs.route()
    return fs


def _strictly_nearer():
    """A 60-unit run between two flags, with long lines 140 above and 110 below
    it. The flags leave no paper near the short run, so every halo is nearer one
    of the long lines than its own: led down past the flags, the number lands 15
    units from the line below and 69 from its own."""
    fs = Flowsheet("strict")
    a0 = fs.add(Feed("A IN", width=190, height=85))
    a1 = fs.add(Product("A OUT", width=190, height=85))
    b0 = fs.add(Feed("B IN", width=190, height=85))
    b1 = fs.add(Product("B OUT", width=190, height=85))
    c0 = fs.add(Feed("C IN", width=190, height=85))
    c1 = fs.add(Product("C OUT", width=190, height=85))
    a0.pin(port="outlet", x=300, y=200)
    a1.pin(port="inlet", x=360, y=200)
    b0.pin(port="outlet", x=100, y=60)
    b1.pin(port="inlet", x=900, y=60)
    c0.pin(port="outlet", x=100, y=310)
    c1.pin(port="inlet", x=900, y=310)
    fs.connect(b0.outlet, b1.inlet).display_label = ""
    fs.connect(c0.outlet, c1.inlet).display_label = ""
    short = fs.connect(a0.outlet, a1.inlet)
    short.display_label = "104-L-002 / SIZE HOLD / CLASS HOLD"
    lettering(fs, body=17, heading=17)
    fs.layout_options.strict_label_clearance = True
    fs.layout()
    fs.route()
    return fs, short


def _number(fs, label):
    from pandid.render.svg import stream_numbers
    return next(n for n in stream_numbers(fs, [], None, "vertical", None)
                if n.display_label.startswith(label))


def test_a_number_is_not_led_from_under_the_line_its_own_runs_into():
    fs = _junction_tie()
    number = _number(fs, "330-L-001")
    assert number.leader is not None
    own, nearest, tolerance = _own_line_measure(fs, number)
    assert nearest is None or nearest[1] > own + tolerance, (own, nearest)


def test_a_number_strictly_nearer_another_line_is_never_led_there():
    """Owner ruling 2026-09-25: a halo strictly nearer another line along it is
    refused outright. Here nothing else is admissible, so the number falls
    through to the unresolved finding -- a strict flag is the one case that may
    end without a leader -- rather than being tied to the wrong line's paper."""
    from pandid.render.svg import label_findings, stream_numbers

    fs, short = _strictly_nearer()
    number = _number(fs, "104-L-002")
    own, nearest, tolerance = _own_line_measure(fs, number)
    if number.leader is not None:
        assert nearest is None or nearest[1] > own + tolerance, (own, nearest)
    else:
        issues = label_findings(fs, "none", stream_numbers(fs, [], None, "vertical", None),
                                "vertical")
        assert any(i.code == "leader-placement-unresolved" and "104-L-002" in i.message
                   for i in issues)
    assert number.leader is None


def test_a_tie_with_no_alternative_keeps_its_leader():
    """Owner ruling 2026-09-25, "keep the tie leader": where every readable
    halo is a tie with another line, the tie position is kept WITH its leader,
    which is the readable state -- only a strict flag may end without one.

    The drawing region is cut down to the paper beside the junction, so every
    halo left straddles it, as near 330-L-003 as its own leg. With ties refused
    outright the number went unresolved there, leaderless; that is what this
    exemption exists to prevent.
    """
    import math
    from pandid.render.svg import stream_numbers

    fs = _junction_tie()
    number = next(n for n in stream_numbers(fs, [], None, "vertical", (240, 120, 720, 200))
                  if n.display_label.startswith("330-L-001"))
    own, nearest, tolerance = _own_line_measure(fs, number)
    assert nearest is not None and nearest[1] <= own + tolerance      # still a tie
    assert number.leader is not None and number.leader_crossed == ()
    assert tuple(round(v, 1) for v in number.box) == (240.0, 171.2, 608.6, 193.3)
    assert math.hypot(number.leader[1][0] - number.leader[0][0],
                      number.leader[1][1] - number.leader[0][1]) == pytest.approx(13.0, abs=0.05)
