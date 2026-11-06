from enterprise_workbench.rc35_scenarios import SCENARIOS,scenario
import pytest

def test_three_distinct_reproducible_scenario_entries():
    assert set(SCENARIOS)=={'G01','G02','G03'}
    assert {v['backend'] for v in SCENARIOS.values()}=={'B','C','D'}
    assert all('确认' in v['claim'] or '人工' in v['claim'] for v in SCENARIOS.values())

def test_unknown_scenario_rejected():
    with pytest.raises(ValueError):scenario('G04')
