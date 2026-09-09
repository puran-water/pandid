"""Contract tests for source custody, native branding and MBR flow sensing."""

import base64
import xml.etree.ElementTree as ET

import pytest

from pandid import Block, Fitting, Flowsheet, Instrument, Pump, Revision, TitleBlock
from pandid.drawio_metadata import validate_bindings
from pandid.spec import from_dict, to_dict


def cells_by_id(document):
    """draw.io user objects carry the id and label of their inner cell."""
    cells = {c.get('id'): c for c in document.iter('mxCell') if c.get('id')}
    for obj in document.iter('object'):
        cell = ET.fromstring(ET.tostring(obj.find('mxCell')))
        cell.set('id', obj.get('id'))
        cell.set('value', obj.get('label', ''))
        cells[obj.get('id')] = cell
    return cells


def simple():
    fs = Flowsheet("Native engine")
    a = fs.add(Block("feed"))
    b = fs.add(Pump("250-P-01"))
    fs.connect(a.outlets[0], b.suction, name="250-01")
    fs.drawio_metadata = {
        "page_id": "process-sheet",
        "graph": {"puran-document-no": "LBT-1100KLD-CH2O-PR-1001"},
        "units": {"feed": {"id": "feed-uuid"}, "250-P-01": {
            "id": "pump-uuid", "attributes": {"canonical-uid": "equipment-uuid", "puran-kind": "entity"}}},
        "streams": {"250-01": {"id": "stream-uuid", "attributes": {"puran-kind": "connection"}}},
    }
    return fs


def test_stable_identity_and_endpoints_survive_insertion_and_spec_roundtrip():
    fs = simple()
    fs.add(Block("other"))
    spec = to_dict(fs)
    assert to_dict(from_dict(spec)) == spec
    root = ET.fromstring(fs.to_drawio()).find("diagram/mxGraphModel/root")
    pump = root.find("object[@id='pump-uuid']")
    stream = root.find("object[@id='stream-uuid']/mxCell")
    assert pump.get("canonical-uid") == "equipment-uuid"
    assert (stream.get("source"), stream.get("target")) == ("feed-uuid", "pump-uuid")
    assert root.find("object[@id='1']").get("puran-document-no") == "LBT-1100KLD-CH2O-PR-1001"


@pytest.mark.parametrize("entry", [{"attributes": {"source": "hijack"}}, {"id": ""}, {"attributes": []}])
def test_invalid_bindings_are_rejected(entry):
    with pytest.raises(ValueError):
        validate_bindings({"units": {"pump": entry}})


def test_duplicate_appearance_ids_are_rejected():
    fs = simple()
    fs.drawio_metadata["units"]["250-P-01"]["id"] = "feed-uuid"
    with pytest.raises(ValueError, match="duplicate stable"):
        fs.to_drawio()


def test_logo_uses_native_company_cell_and_control_values_are_whole():
    fs = simple()
    from pandid import Annotation
    fs.add_annotation(Annotation(title='STREAM KEY', rows=['Process material'], align='bottom-left'))
    logo = b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 300 100"><path d="M0 0H300V100H0Z"/></svg>'
    fs.title_block = TitleBlock(company="Circle H2O", logo="data:image/svg+xml;base64," + base64.b64encode(logo).decode(),
        logo_aspect=3, fit_fields=True, drawing_number="LBT-1100KLD-CH2O-PR-1001",
        checked_by="PENDING", approved_by="PENDING", revisions=[Revision("01", "2026-09-09", "Held review")])
    fs.print_scale = 2.7
    fs.layout_options.column_gap = 80
    assert to_dict(from_dict(to_dict(fs))) == to_dict(fs)
    document = ET.fromstring(fs.to_drawio(page_size="A1"))
    model = document.find("diagram/mxGraphModel")
    assert (model.get("pageWidth"), model.get("pageHeight")) == ("3311", "2339")
    cells = cells_by_id(model)
    image = cells["f0-logo"]
    g = image.find("mxGeometry")
    assert float(g.get("width")) / float(g.get("height")) == pytest.approx(3, abs=.001)
    assert "shape=image;" in image.get("style")
    assert "data:image/svg+xml," in image.get("style")
    assert "data:image/svg+xml;base64;" not in image.get("style")
    assert sum(c.get("value") == "PENDING" for c in cells.values()) == 2
    assert cells['f1-t'].get('value') == 'STREAM KEY'
    assert not any(w.code in {"text-truncated", "text-overruns-cell"} for w in fs.warnings)
    for rectangle in model.iter("mxRectangle"):
        parent = next(g for g in model.iter("mxGeometry") if rectangle in list(g))
        assert float(rectangle.get("width")) == float(parent.get("width"))
        assert float(rectangle.get("height")) == float(parent.get("height"))


@pytest.mark.parametrize("logo,aspect", [("https://example.com/logo.png", 3), ("data:image/svg+xml;base64,broken", 3), ("", 0)])
def test_branding_rejects_external_or_invalid_images(logo, aspect):
    with pytest.raises(ValueError):
        TitleBlock(logo=logo, logo_aspect=aspect)


def test_mag_element_balloon_and_control_signal_are_one_instrument():
    fs = Flowsheet("Mag flow control")
    a, b = fs.add(Block("feed")), fs.add(Block("product"))
    mag = fs.add(Fitting("250-FIT-01", variant="magnetic"))
    fs.connect(a.outlets[0], mag.inlet, name="250-01")
    fs.connect(mag.outlet, b.inlets[0], name="250-02")
    fit = fs.add_balloon(mag, at="N")
    fic = fs.add(Instrument("250-FIC-01", variant="shared"))
    fs.connect(fit.sig_out, fic.sig_in, kind="electric")
    spec = to_dict(fs)
    assert to_dict(from_dict(spec)) == spec
    assert (fit.type, fit.number, fit.area, fit.tag) == ("FIT", "01", "250", "250-FIT-01")
    xml = fs.to_drawio(diagram="p&id")
    assert "mxgraph.pid.flow_sensors.magnetic" in xml
    root = ET.fromstring(xml)
    assert any(c.get("value") == "M" for c in root.iter("mxCell"))
    assert "FIT&lt;br&gt;250-01" in xml
    assert any(c.get("id", "").endswith("-bar0") and "shape=line;" in c.get("style", "")
               for c in root.iter("mxCell"))
    assert not any(w.code == "drawio-approximated" for w in fs.warnings)


def test_solid_stream_exports_as_solid_not_a_nan_dash():
    fs = simple()
    fs.streams[0].dasharray = "none"
    xml = ET.fromstring(fs.to_drawio())
    edge = xml.find(".//object[@id='stream-uuid']/mxCell")
    assert "dashed=1" not in edge.get("style")


def test_hidden_and_relabelled_lines_keep_identity_and_use_visible_text_for_measurement():
    from pandid.render.svg import stream_numbers
    fs = simple()
    stream = fs.streams[0]
    stream.display_label = ''
    xml = ET.fromstring(fs.to_drawio())
    assert xml.find(".//object[@id='stream-uuid']").get('label') == ''
    assert stream.name == '250-01'
    assert not stream_numbers(fs, [], None, 'vertical')
    assert from_dict(to_dict(fs)).streams[0].display_label == ''
    stream.display_label = 'DN 100 - PERMEATE - CLASS A1'
    fs.to_drawio()
    number = stream_numbers(fs, [], None, 'vertical')[0]
    assert number.name == '250-01' and number.text == stream.display_label
    assert max(number.box[2] - number.box[0], number.box[3] - number.box[1]) > 100


def test_individual_nameplates_preserve_all_rows_on_common_horizontal():
    from pandid.render.nameplates import plan
    from pandid.render.drawio import DrawioRenderer
    fs = simple()
    fs.equipment_data = {
        'feed': {'tags': '250-TK-01 / 250-TK-02', 'rows': ['Storage tanks', 'Volume: 120 m³', 'Material: SS304']},
        '250-P-01': {'tags': '250-P-01', 'rows': ['Rotary lobe', 'Capacity: 53 m³/h', 'Motor: HOLD', 'Reversible CIP/backwash']},
    }
    fs.drawio_metadata['cells'] = {
        'np0': {'id': 'tank-nameplate', 'attributes': {'puran-kind': 'equipment-data'}},
        'np1': {'id': 'pump-nameplate', 'attributes': {'puran-kind': 'equipment-data'}},
    }
    xml = ET.fromstring(fs.to_drawio())
    assert to_dict(from_dict(to_dict(fs))) == to_dict(fs)
    blocks, bounds = plan(fs, DrawioRenderer._drawing_box(fs, equipment_data=False))
    assert len({b.y for b in blocks}) == 1
    assert blocks[0].x + blocks[0].w < blocks[1].x
    assert bounds[3] >= max(b.y + b.h for b in blocks)
    texts = [c.get('label', c.get('value', '')) for c in xml.iter()]
    for fields in fs.equipment_data.values():
        for line in [fields['tags'], *fields['rows']]:
            assert any(line in text for text in texts)
    assert all('shape=table;' not in o.find('mxCell').get('style') for o in xml.findall(".//object[@puran-kind='equipment-data']"))
    fs.to_svg()  # both exporters consume the same placement


def test_house_mbr_symbols_have_native_artwork_and_real_ports():
    from pandid import Airlift, MembraneCage
    fs = Flowsheet('House membrane train')
    cage = fs.add(MembraneCage('250-MEM-01'))
    pump = fs.add(Pump('250-P-01', variant='rotary_lobe'))
    fs.add(Airlift('250-AL-01'))
    fs.connect(cage.permeate, pump.suction, name='250-01')
    xml = fs.to_drawio(diagram='p&id')
    assert xml.count('shape=stencil(') == 3
    assert not any(w.code == 'drawio-approximated' for w in fs.warnings)
    assert to_dict(from_dict(to_dict(fs))) == to_dict(fs)


def test_fixed_nozzle_overlap_is_removed_without_moving_nozzles_or_manual_routes():
    from types import SimpleNamespace
    from pandid.geometry import Route
    from pandid.routing.separation import _shorten_conflicting_terminal_runs
    def stream(points, manual=False):
        return SimpleNamespace(route=Route(waypoints=points, manual=manual))
    upper = stream([(0, 0), (94, 0), (94, 50), (120, 50)], manual=True)
    lower = stream([(0, 50), (100, 50), (100, 70), (120, 70)])
    manual = list(upper.route.waypoints)
    endpoints = lower.route.waypoints[0], lower.route.waypoints[-1]
    fs = SimpleNamespace(units=[], streams=[upper, lower])
    _shorten_conflicting_terminal_runs(fs, 6)
    assert upper.route.waypoints == manual
    assert (lower.route.waypoints[0], lower.route.waypoints[-1]) == endpoints
    assert lower.route.waypoints[1][0] < upper.route.waypoints[-2][0]
    assert all(a[0] == b[0] or a[1] == b[1] for a,b in zip(lower.route.waypoints,lower.route.waypoints[1:]))
    settled = list(lower.route.waypoints)
    _shorten_conflicting_terminal_runs(fs, 6)
    assert lower.route.waypoints == settled


def test_nameplate_rules_fit_with_their_text_and_keep_left_aligned_tags():
    fs = simple()
    fs.equipment_data = {'250-P-01': {'tags':'250-P-01', 'rows':['Pump','53 m³/h'], 'width': 240}}
    xml=ET.fromstring(fs.to_drawio(page_size='A1'))
    cells=cells_by_id(xml)
    box=cells['np1'].find('mxGeometry')
    points=cells['np1-r'].findall('mxGeometry/mxPoint')
    assert float(points[0].get('x')) == pytest.approx(float(box.get('x')), abs=.02)
    assert float(points[1].get('x')) == pytest.approx(float(box.get('x'))+float(box.get('width')), abs=.02)
    assert 'align=left;' in cells['np1-t'].get('style')


def test_divided_reference_flag_preserves_code_and_service_in_both_exports():
    from pandid.profiles.templates import from_template
    fs=from_template('Reference', [{'key':'feed','symbol':'boundary.reference','id':'ref-uuid','label':'',
        'connector':{'code':'A','description':'PERMEATE\nFROM SHEET 2'},'attributes':{'puran-kind':'entity'}}], [], metadata={})
    xml=fs.to_drawio()
    assert 'ref-uuid-code' in xml and 'PERMEATE&lt;br&gt;FROM SHEET 2' in xml
    assert 'PERMEATE' in fs.to_svg()
    assert from_dict(to_dict(fs)).units[0].reference_code == 'A'
