"""Pack handling is a semantic delivery, never a hidden process pipe."""
import xml.etree.ElementTree as ET

import pytest

from pandid import Feed, Flowsheet, Pump, Product, Tank
from pandid.containment import validate


def specimen():
    fs = Flowsheet('Purchased full reagent pack')
    delivery, store, pump, outlet = Feed('Full packs'), Tank('Store'), Pump('Metering'), Product('Injection')
    for unit in (delivery, store, pump, outlet):
        fs.add(unit)
    receipt = fs.connect(delivery.outlet, store.inlet, name='pack-delivery')
    receipt.representation = 'internal'
    fs.connect(store.outlet, pump.suction, name='metering-suction')
    fs.connect(pump.discharge, outlet.inlet, name='dose')
    fs.drawio_metadata = {'units': {'Store': {'attributes': {'semantic-class': 'PortableReagentStore'}}},
                          'streams': {'pack-delivery': {'id': 'receipt'}, 'metering-suction': {'id': 'outlet'}}}
    return fs, receipt


def test_pack_delivery_has_no_drawn_fill_and_outlet_is_preserved():
    fs, receipt = specimen()
    root = ET.fromstring(fs.to_drawio(page_size='A1'))
    assert receipt.route is None
    assert root.find(".//mxCell[@id='receipt']").get('visible') == '0'
    assert root.find(".//mxCell[@id='outlet']").get('visible') != '0'
    from pandid.render.svg import _ink
    assert not any(mark.line == 'pack-delivery' for mark in _ink(fs, 'auto'))
    restored = Flowsheet.from_dict(fs.to_dict())
    validate(restored)
    assert len(restored.streams) == 3


def test_only_declared_pack_delivery_gets_the_internal_exception():
    fs, receipt = specimen()
    fs.drawio_metadata = {}
    with pytest.raises(ValueError, match='INTERNAL_CONNECTION_OUTSIDE_BASIN'):
        validate(fs)
    fs, receipt = specimen()
    fs.streams[1].representation = 'internal'
    with pytest.raises(ValueError, match='INTERNAL_CONNECTION_OUTSIDE_BASIN'):
        validate(fs)
