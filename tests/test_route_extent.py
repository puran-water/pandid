import pytest
from pandid import Flowsheet, Feed, Product, Tank
from pandid.geometry import Route
from pandid.routing.extent import fit


def drawing(*, obstruction=False, manual=False, shift=0):
    fs=Flowsheet('Measured escape track')
    a,b=fs.add(Feed('a')),fs.add(Product('b'))
    a.pin(port='outlet',x=100+shift,y=100+shift)
    b.pin(port='inlet',x=500+shift,y=200+shift)
    line=fs.connect(a.outlet,b.inlet)
    if obstruction:
        fs.add(Tank('obstacle',width=100,height=10)).pin(x=250+shift,y=-5+shift)
    fs.layout()
    points=[(100,100),(150,100),(150,-20),(450,-20),(450,200),(500,200)]
    line.route=Route(waypoints=[(x+shift,y+shift) for x,y in points],manual=manual)
    def measured(fs):
        route=line.route.waypoints
        return (min(shift,*(x for x,y in route)),min(shift,*(y for x,y in route)),
                max(600+shift,*(x for x,y in route)),max(300+shift,*(y for x,y in route)))
    return fs,line,measured


@pytest.mark.parametrize('shift',[0,-500,800])
def test_escape_track_fits_measured_band_without_assuming_an_origin(shift):
    fs,line,measure=drawing(shift=shift)
    ends=(line.route.waypoints[0],line.route.waypoints[-1])
    assert fit(fs,width=600,height=300,measure=measure)==[line.name]
    assert min(y for x,y in line.route.waypoints)==shift
    assert (line.route.waypoints[0],line.route.waypoints[-1])==ends


@pytest.mark.parametrize('option',['obstruction','manual'])
def test_escape_track_is_retained_when_moving_it_would_break_a_contract(option):
    fs,line,measure=drawing(**{option:True})
    original=list(line.route.waypoints)
    assert fit(fs,width=600,height=300,measure=measure)==[]
    assert line.route.waypoints==original
