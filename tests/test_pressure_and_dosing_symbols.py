"""Source-bound schematic candidates, native anchors and additive admission."""
import importlib.util
from pathlib import Path
import sys

import pytest

from pandid import InjectionQuill, PressureMembrane, PressureMembraneArray
from pandid.profiles.templates import _unit, symbol_type
from pandid.render.house_artwork import ARTWORK
from pandid.render.symbols import default_registry


@pytest.mark.parametrize('key,cls,ports', [
    ('house.dosing.injection_quill', InjectionQuill, {'chemical_in': 'inlet', 'injection': 'outlet'}),
    ('house.membrane.pressure_vessel', PressureMembrane, {'inlet': 'inlet', 'concentrate': 'outlet', 'permeate': 'outlet'}),
    ('house.membrane.pressure_array', PressureMembraneArray, {'inlet': 'inlet', 'concentrate': 'outlet', 'permeate': 'outlet'}),
])
def test_artwork_has_real_ports_reference_hook_and_native_paths(key, cls, ports):
    art = ARTWORK[key]
    assert art.version == '1'
    assert art.reference_document.startswith(('DuPont ', 'SAF-T-FLO '))
    assert len(art.reference_sha256) == 64 and art.reference_pages
    unit = cls('candidate')
    assert {p.name: p.direction for p in unit.ports.values()} == ports
    symbol = default_registry.for_unit(unit)
    assert symbol.drawio_shape.startswith('stencil(')
    assert set(symbol.ports) == set(ports)
    assert symbol_type(key) == (unit.kind, 'default')
    assert art.aspect == 'fixed'
    for name, face in cls.PLACES.items():
        x, y = next((x, y) for side, x, y in art.anchors if side == face)
        assert symbol.ports[name] == (x * symbol.width, y * symbol.height)


def test_ion_exchanger_template_selection_retains_all_four_device_ports():
    unit = _unit({'key': 'ix', 'symbol': 'stencil.pid.filters.liquid_filter_ion_exchanger'}, [], [])
    assert type(unit).__name__ == 'IonExchanger'
    assert set(unit.ports) == {'inlet', 'outlet', 'regenerant_in', 'spent_regenerant'}


def test_generator_is_deterministic_and_existing_versions_stay_unchanged():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / 'scripts'))
    try:
        spec = importlib.util.spec_from_file_location('house_symbol_builder', root / 'scripts/house_symbols.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        assert module.render() == (root / 'pandid/render/_house_symbols.py').read_text()
    finally:
        sys.path.pop(0)
    assert {key: ARTWORK[key].version for key in (
        'house.air.diffuser_grid', 'house.basin.concrete', 'house.mbr.airlift',
        'house.mbr.membrane_cage', 'house.mixer.agitator', 'house.mixer.submersible',
        'house.pump.rotary_lobe')} == {
        'house.air.diffuser_grid': '1', 'house.basin.concrete': '1', 'house.mbr.airlift': '1',
        'house.mbr.membrane_cage': '2', 'house.mixer.agitator': '1', 'house.mixer.submersible': '1',
        'house.pump.rotary_lobe': '1'}
