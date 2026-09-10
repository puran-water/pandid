import json

import pytest

from pandid import Flowsheet
from pandid.discovery import EXAMPLES, catalog, describe_unit, example, main


def test_catalog_is_bounded_and_filterable():
    first = catalog(limit=3)
    second = catalog(offset=first['next_offset'], limit=3)
    assert len(first['items']) == 3
    assert not {r['key'] for r in first['items']} & {r['key'] for r in second['items']}
    rows = catalog(query='magnetic')['items']
    assert any('magnetic' in row['matched_variants'] for row in rows)
    assert 'ports' not in first['items'][0]
    with pytest.raises(ValueError, match='limit'):
        catalog(limit=101)


def test_describe_resolves_actual_variable_and_actuator_ports():
    header = describe_unit('Junction', parameters={'inputs': 1, 'outputs': 3})
    assert len(header['ports']) == 4
    valve = describe_unit('Valve', variant='butterfly_pneumatic')
    assert any(p['name'] == 'actuator' and p['role'] == 'signal' for p in valve['ports'])
    assert any(p['name'] == 'variant' for p in valve['parameters']) is False
    with pytest.raises(TypeError):
        describe_unit('Pump', parameters={'invented_argument': True})
    with pytest.raises(ValueError, match='Unknown unit'):
        describe_unit('invented')


@pytest.mark.parametrize('key', sorted(EXAMPLES))
def test_examples_are_executable_and_round_trip(key):
    result = example(key)
    restored = Flowsheet.from_dict(json.loads(json.dumps(result['spec'])))
    assert result['synthetic']
    assert restored.to_dict() == result['spec']
    restored.layout()
    restored.route()
    assert all(s.route and s.route.waypoints for s in restored.streams)


def test_cli_discloses_one_unit(capsys):
    assert main(['unit', 'Pump', '--variant', 'rotary_lobe']) == 0
    result = json.loads(capsys.readouterr().out)
    assert {p['name'] for p in result['ports']} == {'suction', 'discharge'}
