"""An absorber drawn on the packed artwork draws the artwork's beds once.

``Absorber`` defaults to a composed bed (``internals="packing"``); on
``variant="packed"``, whose artwork already draws two beds on their support
grids, that default composed eight more over them. Column met the same thing
in #373.
"""
from pandid import Flowsheet
from pandid import units
from pandid.spec import from_dict, to_dict


def test_absorber_on_packed_artwork_draws_the_artworks_beds_once():
    tower = units.Absorber("T-1", variant="packed")
    assert tower.internals is None
    fs = Flowsheet("A")
    fs.add(tower)
    spec = to_dict(fs)
    assert "internals" not in spec["units"][0]
    assert to_dict(from_dict(spec)) == spec
    assert units.Absorber("T-2").internals == "packing"  # the plain shell keeps its bed
