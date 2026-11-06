from datetime import date
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

import pytest

from app.domain.timephased import Item, Order
from app.db.repository import _snapshot_hash
from enterprise_workbench.rc35_planning import explain_supply, analyze
from g3.core import snapshot_hash, compare
from rc36_dsn_guard import GuardError, normalize_dsn


def _snapshot(uom='PCS'):
    return {
        'as_of': '2026-11-06',
        'orders': [{'order_id': 'SO-1', 'product': 'FG-1', 'qty': '2', 'due': '2026-11-30', 'priority': 1}],
        'items': {
            'FG-1': {'kind': 'MAKE', 'lead_days': 2, 'on_hand': '0', 'reserved': '0', 'blocked': '0',
                     'safety': '0', 'moq': '0', 'lot': '1', 'receipts': [], 'uom': 'PCS'},
            'RM-1': {'kind': 'BUY', 'lead_days': 4, 'on_hand': '0', 'reserved': '0', 'blocked': '0',
                     'safety': '0', 'moq': '10', 'lot': '10', 'receipts': [], 'uom': uom},
        },
        'bom': [['FG-1', 'RM-1', '3']],
    }


def test_material_uom_is_part_of_persisted_run_fingerprint():
    orders = [Order('SO-1', 'FG-1', Decimal('2'), '2026-11-30', 1)]
    a = {'FG-1': Item('FG-1', 'MAKE', uom='PCS'), 'RM-1': Item('RM-1', 'BUY', uom='PCS')}
    b = {'FG-1': Item('FG-1', 'MAKE', uom='PCS'), 'RM-1': Item('RM-1', 'BUY', uom='KG')}
    bom = [('FG-1', 'RM-1', Decimal('3'))]
    assert _snapshot_hash('2026-11-06', orders, a, bom) != _snapshot_hash('2026-11-06', orders, b, bom)


def test_native_ab_snapshot_fingerprint_binds_uom():
    assert snapshot_hash(_snapshot('PCS')) != snapshot_hash(_snapshot('KG'))


def test_strict_ab_comparison_rejects_missing_or_different_units():
    a = [{'material_id': 'RM-1', 'date': '2026-11-26', 'gross_qty': 6, 'net_qty': 6,
          'planned_qty': 10, 'closing_qty': 4, 'uom': 'PCS'}]
    b = [{'material': 'RM-1', 'date': '2026-11-26', 'gross': 6, 'net': 6,
          'planned': 10, 'closing': 4, 'uom': 'KG'}]
    result = compare(a, b, strict_units=True)
    assert result['status'] == 'DIFFERENT'
    assert any(x['field'] == 'uom' and x['reason'] == 'MATERIAL_MASTER_UNIT_MISSING_OR_MISMATCH'
               for x in result['differences'])


def test_supply_explanation_derives_release_from_frozen_master_when_fact_column_absent():
    row = {'material': 'RM-1', 'date': '2026-11-30', 'gross': '6', 'net': '6', 'planned': '10'}
    item = {'kind': 'BUY', 'lead_days': 4, 'moq': '10', 'lot': '10', 'uom': 'PCS'}
    result = explain_supply(row, item, '2026-11-06')
    assert result['status'] == 'VERIFIED'
    assert result['planned_release_date'] == '2026-11-26'
    assert result['release_date_source'] == 'DERIVED_FROM_FROZEN_SNAPSHOT'
    assert result['uom'] == 'PCS'
    assert result['moq_applied'] is True
    assert result['lot_rounding_applied'] is False


def test_daily_supply_analysis_keeps_release_date_and_unit_evidence():
    snapshot = {'as_of': '2026-11-06', 'items': {'RM-1': {'kind': 'BUY', 'lead_days': 4,
        'moq': '10', 'lot': '10', 'uom': 'PCS'}}, 'orders': []}
    lines = [{'material': 'RM-1', 'date': '2026-11-30', 'gross': '6', 'net': '6',
              'planned': '10', 'closing': '4', 'uom': 'PCS'}]
    result = analyze(snapshot, lines, 'day')
    explanation = result['supply_explanations'][0]
    assert explanation['status'] == 'VERIFIED'
    assert explanation['planned_release_date'] == '2026-11-26'
    assert explanation['uom'] == 'PCS'


def test_rc36_dsn_guard_accepts_only_the_new_branch_endpoint():
    good = 'postgresql://v19b_app_runtime:secret@ep-holy-star-bbv8lyg7.c-15.us-east-1.aws.neon.tech/industrial_v19b_preview?sslmode=require'
    assert normalize_dsn(good) == good
    bad_host = 'postgresql://v19b_app_runtime:secret@ep-patient-wind-bbme3mck.c-15.us-east-1.aws.neon.tech/industrial_v19b_preview?sslmode=require'
    with pytest.raises(GuardError, match='HOST_NOT_RC36_ISOLATED_ENDPOINT'):
        normalize_dsn(bad_host)
    bad_db = 'postgresql://v19b_app_runtime:secret@ep-holy-star-bbv8lyg7.c-15.us-east-1.aws.neon.tech/postgres?sslmode=require'
    with pytest.raises(GuardError, match='DATABASE_NOT_ALLOWED'):
        normalize_dsn(bad_db)
    no_ssl = 'postgresql://v19b_app_runtime:secret@ep-holy-star-bbv8lyg7.c-15.us-east-1.aws.neon.tech/industrial_v19b_preview'
    with pytest.raises(GuardError, match='SSL_REQUIRED'):
        normalize_dsn(no_ssl)
    pooled = 'postgresql://v19b_app_runtime:secret@ep-holy-star-bbv8lyg7-pooler.c-15.us-east-1.aws.neon.tech/industrial_v19b_preview?sslmode=require'
    with pytest.raises(GuardError):
        normalize_dsn(pooled)


def test_rc36_dsn_guard_requires_least_privilege_runtime_role_and_default_port():
    wrong_role = 'postgresql://v19b_preview_owner:secret@ep-holy-star-bbv8lyg7.c-15.us-east-1.aws.neon.tech/industrial_v19b_preview?sslmode=require'
    with pytest.raises(GuardError, match='ROLE_NOT_RC36_RUNTIME'):
        normalize_dsn(wrong_role)
    wrong_port = 'postgresql://v19b_app_runtime:secret@ep-holy-star-bbv8lyg7.c-15.us-east-1.aws.neon.tech:6543/industrial_v19b_preview?sslmode=require'
    with pytest.raises(GuardError, match='PORT_NOT_ALLOWED'):
        normalize_dsn(wrong_port)


def test_pg16_readonly_preflight_requires_runtime_role_and_all_gate_privileges():
    source = (ROOT / 'gates' / 'rc36_pg16_readonly.py').read_text(encoding='utf-8')
    assert "role_row[0] == 'v19b_app_runtime'" in source
    assert 'runtime_role_required_table_privileges' in source
    assert 'version_b_rc2.execution_receipts:INSERT' in source
    assert 'platform.requirement_pegs:INSERT' in source
    assert 'version_b_rc2.audit:SELECT' in source
    assert 'runtime_role_schema_usage' in source
    assert 'runtime_role_audit_sequence_usage' in source
    assert 'default_transaction_read_only=on' in source


def test_pg16_one_shot_never_runs_migrations_and_requires_explicit_dml_fault_ack():
    source = (ROOT / 'RUN_RC36_PG16_ONE_SHOT.ps1').read_text(encoding='utf-8')
    assert 'RUN_RC36_ISOLATED_PG16_WRITES_AND_FAULT_TESTS' in source
    assert 'v19b_app_runtime' in source
    assert 'No migrations or DDL are run' in source
    assert 'tests\\rc36_isolated_pg16_gate.py' in source
    assert 'gates\\rc36_pg16_readonly.py' in source


def test_rc36_dsn_guard_rejects_unreviewed_libpq_query_options():
    unsafe = 'postgresql://v19b_app_runtime:secret@ep-holy-star-bbv8lyg7.c-15.us-east-1.aws.neon.tech/industrial_v19b_preview?sslmode=require&options=-c%20search_path%3Dpublic'
    with pytest.raises(GuardError, match='URL_QUERY_PARAM_NOT_ALLOWED'):
        normalize_dsn(unsafe)


def test_pg16_business_gate_verifies_source_manifest_before_database_connect():
    source = (ROOT / 'tests' / 'rc36_isolated_pg16_gate.py').read_text(encoding='utf-8')
    assert 'def verify_source_manifest()' in source
    assert "mark('source_manifest_integrity', manifest_ok, manifest_detail)" in source


def test_current_rc36_source_manifest_matches_worktree():
    import importlib.util
    gate_path = ROOT / 'tests' / 'rc36_isolated_pg16_gate.py'
    spec = importlib.util.spec_from_file_location('rc36_pg16_gate_manifest_check', gate_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    passed, detail = module.verify_source_manifest()
    assert passed, detail
