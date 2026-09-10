"""Grouped PFD appearances keep member paths without duplicate port binding."""
import xml.etree.ElementTree as ET

import pytest

from pandid.profiles.templates import from_template


def node(key,symbol,*,group=False):
    return dict(key=key,id=key,symbol=symbol,label=key,
                attributes={'equipment-group':'members'} if group else {})


def edge(key,source,target,sp='outlet',tp='inlet',kind='material'):
    return dict(key=key,id=key,source=source,target=target,source_port=sp,target_port=tp,
                kind=kind,attributes={'semantic-path':key},label='')


def test_grouped_pump_from_distinct_sources_keeps_each_path_and_adds_pipe_fan():
    nodes=[node('a','boundary'),node('b','boundary'),node('pump','house.pump.rotary_lobe',group=True),node('out','boundary')]
    edges=[edge('a-p','a','pump'),edge('b-p','b','pump'),edge('p-out','pump','out')]
    fs=from_template('Grouped duty pumps',nodes,edges,metadata={})
    assert len(fs.streams)==4
    assert len({s.dest.name for s in fs.streams if s.name in {'a-p','b-p'}})==2
    fans=[u for u in fs.units if u.name.startswith('projection-')]
    assert len(fans)==1 and fans[0].kind=='junction'
    xml=ET.fromstring(fs.to_drawio(diagram='pfd'))
    assert all(xml.find(f".//object[@id='{key}']") is not None for key in ('a-p','b-p','p-out'))
    assert xml.find(".//object[@puran-kind='projection-junction']") is not None


def test_ungrouped_equipment_rejects_duplicate_physical_port():
    nodes=[node('a','boundary'),node('b','boundary'),node('pump','pump.centrifugal')]
    with pytest.raises(ValueError,match='PANDID_DUPLICATE_PROCESS_PORT'):
        from_template('Invalid',nodes,[edge('a-p','a','pump'),edge('b-p','b','pump')],metadata={})


def test_material_and_energy_inlets_use_distinct_vessel_ports():
    nodes=[node('a','boundary'),node('mixer','process.package'),node('tank','tank.vertical')]
    fs=from_template('Mixed tank',nodes,[edge('feed','a','tank'),edge('drive','mixer','tank',tp='mixing-duty',kind='energy')],metadata={})
    assert len({s.dest.name for s in fs.streams})==2


def test_cooling_tower_generic_inlet_maps_to_water_nozzle():
    nodes=[node('a','boundary'),node('tower','stencil.pid.vessels.forced_draft_cooling_tower'),node('b','boundary')]
    fs=from_template('Cooling',nodes,[edge('feed','a','tower'),edge('product','tower','b')],metadata={})
    assert fs.streams[0].dest.name=='water_in'
    assert fs.streams[1].source.name=='water_out'
