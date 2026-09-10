import base64
import json
import xml.etree.ElementTree as ET
import zlib

import pytest

from pandid import AirDiffuser, Feed, Flowsheet, MembraneCage, Product
from pandid.discovery import describe_unit
from pandid.house_library import export_library, library_xml
from pandid.render.house_artwork import ARTWORK
from pandid.render.symbols import default_registry
from pandid.spec import from_dict, to_dict


def test_importable_library_has_exact_engine_artwork_and_named_anchors(tmp_path):
    entries = json.loads(ET.fromstring(library_xml()).text)
    assert {row['title'] for row in entries} == set(ARTWORK)
    for row in entries:
        art = ARTWORK[row['title']]
        obj = ET.fromstring(row['xml']).find('root/object')
        style = obj.find('mxCell').get('style')
        assert f'aspect={art.aspect};' in style
        encoded = style.split('shape=stencil(', 1)[1].split(')', 1)[0]
        stencil = zlib.decompress(base64.b64decode(encoded), -15).decode()
        assert stencil == art.stencil
        assert len(ET.fromstring(stencil).findall('connections/constraint')) == len(art.anchors)
        assert obj.get('house-symbol-version') == art.version
    target = export_library(tmp_path/'symbols.xml')
    assert target.read_bytes() == library_xml()
    with pytest.raises(FileExistsError):
        export_library(target)


def test_diffuser_is_discoverable_roundtrippable_native_equipment():
    fs = Flowsheet('Nanded-derived diffuser candidate')
    air = fs.add(Feed('air'))
    grid = fs.add(AirDiffuser('230-DF-01'))
    basin = fs.add(Product('basin-air'))
    fs.connect(air.outlet, grid.air_in)
    fs.connect(grid.dispersed_air, basin.inlet)
    spec = to_dict(fs)
    assert to_dict(from_dict(spec)) == spec
    assert 'air_diffuser' in str(describe_unit('AirDiffuser'))
    symbol = default_registry.for_unit(grid)
    assert symbol.ports['air_in'] == (0, 24)
    assert symbol.ports['dispersed_air'] == (60, 24)
    xml = fs.to_drawio(diagram='p&id')
    assert 'shape=stencil(' in xml
    assert not any(w.code == 'drawio-approximated' for w in fs.warnings)
    assert 'ellipse' in fs.to_svg()


def test_nanded_evidence_is_bound_without_inferring_equipment_quantities():
    cage = ARTWORK['house.mbr.membrane_cage']
    diffuser = ARTWORK['house.air.diffuser_grid']
    assert cage.reference_sha256 == diffuser.reference_sha256
    assert cage.reference_pages == (10, 11, 12)
    assert diffuser.reference_pages == (8, 9)
    assert cage.version == '2'
    assert '100' not in cage.meaning
    assert default_registry.for_unit(MembraneCage('cage')).ports['permeate'] == (22.5, 0)
