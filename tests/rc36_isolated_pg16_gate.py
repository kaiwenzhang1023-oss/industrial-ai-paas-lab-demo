#!/usr/bin/env python3
"""RC3.6 isolated Neon PG16 enterprise integration gate (dedicated RC3.6 child branch).

Writes only uniquely-scoped test tenants/runs to the explicitly allowlisted
isolated Neon branch. No DDL/migrations, no source ERP/WMS mutation, no frozen
RC2 connection, no Docker, and no external ERP/MES/SRM calls.
"""
from __future__ import annotations
import concurrent.futures
import hashlib
import json
import os
from pathlib import Path
import secrets
import sys
import threading
import time
import traceback
import uuid
from datetime import date, datetime, timedelta, timezone

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'backend'))
sys.path.insert(0, str(ROOT / 'tests'))
OUT = ROOT / 'release_evidence' / 'rc36'
OUT.mkdir(parents=True, exist_ok=True)
REPORT = OUT / 'PG16_BUSINESS_RESULT.json'
SOURCE_TABLES = (
    'mock_erp.sales_orders', 'mock_erp.materials', 'mock_erp.bom_versions',
    'mock_erp.bom_items', 'mock_erp.supply_orders', 'mock_wms.inventory_balances',
)
RUN_TABLES = {
    'platform.requirement_runs': 'run_id=%s',
    'platform.run_snapshot_fences': 'run_id=%s',
    'platform.material_requirements': 'run_id=%s',
    'platform.requirement_pegs': 'run_id=%s',
    'version_b_rc2.run_tenants': 'run_id=%s',
    'version_b_rc2.run_inputs': 'run_id=%s',
    'version_b_rc2.workflow_states': 'run_id=%s',
    'version_b_rc2.decisions': 'run_id=%s',
    'version_b_rc2.outbox': 'run_id=%s',
    'version_b_rc2.execution_receipts': 'run_id=%s',
    'version_b_rc2.reconciliation': 'run_id=%s',
    'version_b_rc2.proposals': 'run_id=%s',
    'version_b_rc2.audit': "details->>'run_id'=%s",
}
result = {
    'scope': 'RC36_ISOLATED_NEON_PG16_BRANCH_ONLY',
    'target': {'project_id':'super-glade-55757112','branch_id':'br-green-glade-bbnahfli','branch_name':'rc36-pg16-isolated-20261106','endpoint_id':'ep-holy-star-bbv8lyg7','database':'industrial_v19b_preview'},
    'privacy': 'connection strings and identity tokens are never written to evidence',
    'frozen_rc2_touched': False,
    'rc35_branch_touched': False,
    'external_effect': 'NONE',
    'schema_changes': False,
    'migrations_executed': False,
    'source_erp_wms_mutations': False,
    'native_database_rls_claimed': False,
    'scope_notes': [
        'This RC36 branch is a child of the existing RC35 isolated PG16 branch; all writes remain branch-local.',
        'No migrations are executed by this gate; read-only preflight requires the inherited RC2/RC3/RC35 schema structure.',
        'Tenant authorization is tested at the API layer; this does not claim native PostgreSQL RLS.',
        'Worker fault injection is an application-level one-job failure plus lease recovery, not a Neon node outage.',
        'Worker receipts prove INTERNAL_VALIDATION_ONLY, not external factory-system command delivery.',
        'Scenario C is a seven-day customer due-date postponement; D is a BOM usage anomaly.',
    ],
    'checks': {}, 'run_ids': [], 'command_ids': [], 'a_b_findings': [], 'status': 'HOLD',
    'timestamp_utc': datetime.now(timezone.utc).isoformat(),
    'source_manifest_sha256': hashlib.sha256((ROOT / 'RC36_SOURCE_SHA256.json').read_bytes()).hexdigest() if (ROOT / 'RC36_SOURCE_SHA256.json').exists() else None,
}

class Halt(Exception):
    pass


def set_check(name, status, detail=None):
    item = {'status': status}
    if detail is not None:
        item['detail'] = detail
    result['checks'][name] = item


def mark(name, passed, detail=None):
    set_check(name, 'PASS' if passed else 'FAIL', detail)
    if not passed:
        raise Halt(name)


def record():
    REPORT.write_text(json.dumps(result, ensure_ascii=False, indent=2, default=str), encoding='utf-8')


def fail_closed():
    dsn = os.environ.get('RC36_ISOLATED_PG16_DSN', '')
    if not dsn:
        set_check('isolated_pg16_connection', 'HOLD', 'Secure Neon connection input was not supplied.')
        return None
    if os.environ.get('RC36_ENABLE_ISOLATED_WRITES') != 'YES':
        set_check('isolated_pg16_mutation_ack', 'HOLD', 'Explicit isolated-write acknowledgement is required.')
        return None
    if os.environ.get('RC36_ENABLE_WORKER_FAULT_INJECTION') != 'YES':
        set_check('worker_fault_injection_ack', 'HOLD', 'Explicit isolated worker fault-injection acknowledgement is required.')
        return None
    from rc36_dsn_guard import normalize_dsn, GuardError, safe_target
    try:
        dsn = normalize_dsn(dsn)
    except GuardError as exc:
        set_check('isolated_pg16_guard', 'FAIL', exc.code)
        return None
    mark('isolated_pg16_guard', True, safe_target())
    return dsn


def verify_source_manifest():
    """Verify the complete immutable source manifest before any DB connection."""
    manifest_path = ROOT / 'RC36_SOURCE_SHA256.json'
    if not manifest_path.is_file():
        return False, {'reason': 'SOURCE_MANIFEST_MISSING'}
    try:
        manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return False, {'reason': 'SOURCE_MANIFEST_INVALID'}
    if not isinstance(manifest, dict) or not manifest:
        return False, {'reason': 'SOURCE_MANIFEST_EMPTY'}
    missing, mismatched, unsafe = [], [], []
    for relative, expected in manifest.items():
        target = (ROOT / relative).resolve()
        if ROOT.resolve() not in target.parents:
            unsafe.append(relative)
            continue
        if not target.is_file():
            missing.append(relative)
            continue
        digest = hashlib.sha256(target.read_bytes()).hexdigest()
        if digest != expected:
            mismatched.append(relative)
    detail = {'manifest_file_count': len(manifest), 'missing': missing[:30],
              'mismatched': mismatched[:30], 'unsafe_paths': unsafe[:30]}
    return not (missing or mismatched or unsafe), detail


def _digest_rows(rows):
    chunks = sorted(json.dumps(row[0], default=str, sort_keys=True, ensure_ascii=False, separators=(',', ':')) for row in rows)
    return {'count': len(rows), 'sha256': hashlib.sha256(json.dumps(chunks, ensure_ascii=False).encode()).hexdigest()}


def source_snapshot(conn):
    snapshot = {}
    for table in SOURCE_TABLES:
        rows = conn.execute(f'SELECT to_jsonb(t) FROM {table} t ORDER BY to_jsonb(t)::text').fetchall()
        snapshot[table] = _digest_rows(rows)
    return snapshot


def run_snapshot(conn, run_id):
    evidence = {}
    for table, where in RUN_TABLES.items():
        rows = conn.execute(f'SELECT to_jsonb(t) FROM {table} t WHERE {where}', (run_id,)).fetchall()
        evidence[table] = _digest_rows(rows)
    return evidence


def mark_http(name, response, expected):
    mark(name, response.status_code == expected, {'http': response.status_code, 'expected': expected})
    try:
        return response.json()
    except Exception:
        return {}


def main():
    manifest_ok, manifest_detail = verify_source_manifest()
    mark('source_manifest_integrity', manifest_ok, manifest_detail)
    dsn = fail_closed()
    if not dsn:
        return

    import psycopg
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from enterprise_workbench.rc2 import router as rc2_router, fingerprint
    from enterprise_workbench.rc4 import router as rc4_router
    from enterprise_workbench.worker import claim, execute_internal, finish, process_batch
    from app.db.repository import connect as repository_connect, read_run
    from enterprise_workbench.rc35_planning import analyze
    from enterprise_workbench.rc35_pegging import reconcile as reconcile_pegs
    from enterprise_workbench.pg16_validation import reconcile_persisted_plan, reconcile_supply_caps

    with psycopg.connect(dsn, connect_timeout=15) as conn:
        version, db, user, workflow = conn.execute(
            "SELECT current_setting('server_version_num'), current_database(), current_user, to_regclass('version_b_rc2.workflow_states')"
        ).fetchone()
        mark('pg16_and_schema', str(version).startswith('16') and db == 'industrial_v19b_preview' and workflow is not None,
             {'pg_version_num': str(version), 'database': db, 'workflow_table': bool(workflow)})
        required = (
            'version_b_rc2.run_tenants', 'version_b_rc2.run_inputs', 'version_b_rc2.workflow_states',
            'version_b_rc2.decisions', 'version_b_rc2.outbox', 'version_b_rc2.execution_receipts',
            'version_b_rc2.audit', 'version_b_rc2.reconciliation', 'version_b_rc2.proposals', 'version_b_rc2.mcp_call_audit', 'platform.requirement_runs',
            'platform.material_requirements', 'platform.requirement_pegs', 'platform.run_snapshot_fences',
        ) + SOURCE_TABLES
        missing = [t for t in required if conn.execute('SELECT to_regclass(%s)', (t,)).fetchone()[0] is None]
        mark('required_pg16_tables', not missing, {'missing': missing})
        source_before = source_snapshot(conn)
        empty = [t for t, v in source_before.items() if v['count'] == 0]
        mark('seeded_source_data_available', not empty, {'empty_source_tables': empty})
    result['source_tables_before'] = source_before

    os.environ['DATABASE_URL'] = dsn
    tenant_a = 'rc36gate-' + uuid.uuid4().hex
    tenant_b = 'rc36gate-' + uuid.uuid4().hex
    roles = ['viewer', 'planner', 'approver', 'operator', 'admin']
    credentials = {}
    identities = []
    for tenant_key, tenant in [('A', tenant_a), ('B', tenant_b)]:
        for role in roles:
            token = secrets.token_urlsafe(32)
            credentials[(tenant_key, role)] = token
            identities.append({'token': token, 'tenant': tenant, 'actor': 'gate-' + role, 'role': role})
    os.environ['VERSION_B_RC2_IDENTITIES_JSON'] = json.dumps(identities)

    app = FastAPI()
    app.include_router(rc2_router)
    app.include_router(rc4_router)
    prefix = '/api/v1/version-b/enterprise'
    client = TestClient(app)

    def call(tenant_key, role, method, path, body=None, use_client=None):
        c = use_client or client
        return c.request(method, prefix + path,
                         headers={'Authorization': 'Bearer ' + credentials[(tenant_key, role)]}, json=body)

    mark('unauthenticated_401', client.get(prefix + '/me').status_code == 401)
    mark('invalid_token_401', client.get(prefix + '/me', headers={'Authorization': 'Bearer deliberately-invalid'}).status_code == 401)

    def new_run(scenario='A', role='planner'):
        response = call('A', role, 'POST', '/mrp/runs', {'scenario': scenario})
        data = mark_http('mrp_create_' + scenario + '_' + str(len(result['run_ids']) + 1), response, 201)
        run_id = data.get('run_id')
        mark('run_id_shape_' + str(len(result['run_ids']) + 1), isinstance(run_id, str) and run_id.startswith('MRP-'))
        result['run_ids'].append(run_id)
        return run_id

    def verify_persisted_plan_evidence(run_id, read_data=None, expected_scenario='A'):
        data = read_data or mark_http('verify_run_read_' + run_id, call('A', 'viewer', 'GET', '/mrp/runs/' + run_id), 200)
        snapshot = data['canonical_snapshot']
        persisted = data['run']
        missing_units = sorted(code for code, item in snapshot.get('items', {}).items()
                               if not str(item.get('uom') or '').strip())
        mark('snapshot_uom_bound_' + run_id, not missing_units,
             {'material_count': len(snapshot.get('items', {})), 'missing_uom': missing_units})
        line_unit_gaps = sorted({line['material'] for line in persisted['lines']
                                 if not str(line.get('uom') or '').strip()})
        mark('persisted_requirement_uom_' + run_id, not line_unit_gaps,
             {'line_count': len(persisted['lines']), 'missing_line_units': line_unit_gaps})
        with psycopg.connect(dsn) as conn:
            stored = conn.execute('''SELECT ri.input_hash,ri.payload,rr.input_hash,rr.status
                FROM version_b_rc2.run_inputs ri JOIN platform.requirement_runs rr USING(run_id)
                WHERE ri.tenant_id=%s AND ri.run_id=%s''', (tenant_a, run_id)).fetchone()
        mark('snapshot_hash_persisted_' + run_id, bool(stored) and stored[0] == stored[2]
             and fingerprint(stored[1]) == stored[0] and stored[3] == 'COMPLETED',
             {'run_input_hash_matches_run': bool(stored and stored[0] == stored[2]),
              'payload_fingerprint_matches': bool(stored and fingerprint(stored[1]) == stored[0]),
              'run_status': stored[3] if stored else None})
        fence = persisted.get('snapshot') or {}
        fence_versions = fence.get('source_versions') or {}
        scenario_fence = fence_versions.get('scenario') or {}
        mark('snapshot_fence_time_and_scenario_' + run_id,
             fence.get('as_of') == snapshot.get('as_of')
             and scenario_fence.get('code') == expected_scenario,
             {'snapshot_as_of': snapshot.get('as_of'), 'fence_as_of': fence.get('as_of'),
              'scenario': scenario_fence.get('code')})
        explanation = analyze(snapshot, persisted['lines'], 'day')
        explanations = explanation['supply_explanations']
        invalid_explanations = [x for x in explanations if x.get('status') != 'VERIFIED'
                                or x.get('release_date_verified') is not True
                                or not x.get('planned_release_date')
                                or not x.get('uom')]
        mark('daily_moq_lot_lead_explanations_' + run_id, not invalid_explanations,
             {'line_explanations': len(explanations), 'invalid': invalid_explanations[:12]})
        snapshot_plan = reconcile_persisted_plan(snapshot, persisted['lines'])
        mark('persisted_mrp_recomputed_from_frozen_snapshot_' + run_id,
             snapshot_plan.get('status') == 'MATCH',
             {'expected_line_count': snapshot_plan.get('expected_line_count'),
              'actual_line_count': snapshot_plan.get('actual_line_count'),
              'difference_count': snapshot_plan.get('difference_count'),
              'differences': snapshot_plan.get('differences', [])[:8]})
        supply_caps = reconcile_supply_caps(snapshot, persisted['lines'], persisted['pegs'])
        mark('persisted_peg_supply_source_caps_' + run_id,
             supply_caps.get('status') == 'MATCH',
             {'difference_count': supply_caps.get('difference_count'),
              'differences': supply_caps.get('differences', [])[:8]})
        pegging = reconcile_pegs(persisted['lines'], persisted['pegs'], snapshot)
        mark('persisted_pegging_and_bom_lineage_' + run_id,
             pegging.get('status') == 'PASS' and pegging.get('bom_lineage', {}).get('bom_lineage_verified') is True,
             {'line_count': pegging.get('line_count'), 'peg_count': pegging.get('peg_count'),
              'difference_count': len(pegging.get('differences', [])),
              'lineage_path_count': len((pegging.get('bom_lineage') or {}).get('paths', [])),
              'physical_supply_trace_verified': False})
        rule_inputs = {code: {key: item.get(key) for key in ('kind','uom','lead_days','moq','lot')}
                       for code,item in sorted(snapshot.get('items', {}).items())}
        rule_fingerprint = hashlib.sha256(json.dumps(rule_inputs, sort_keys=True, ensure_ascii=False,
            default=str, separators=(',', ':')).encode()).hexdigest()
        summary = {
            'run_id': run_id, 'input_hash': persisted['input_hash'],
            'snapshot_uom_count': len(snapshot.get('items', {})),
            'requirement_lines': len(persisted['lines']), 'pegging_lines': len(persisted['pegs']),
            'supply_explanations_verified': len(explanations),
            'rule_fingerprint': rule_fingerprint, 'material_rule_inputs': rule_inputs,
            'pegging_status': pegging.get('status'),
            'bom_lineage_verified': (pegging.get('bom_lineage') or {}).get('bom_lineage_verified'),
            'physical_supply_trace_verified': False, 'external_receipt_claimed': False,
        }
        (OUT / ('PLAN_EVIDENCE_' + run_id + '.json')).write_text(
            json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
        (OUT / ('SUPPLY_EXPLANATIONS_' + run_id + '.json')).write_text(
            json.dumps(explanations, ensure_ascii=False, indent=2), encoding='utf-8')
        return data, explanation, pegging

    run_a = new_run('A')
    read_a = mark_http('tenant_A_run_read', call('A', 'viewer', 'GET', '/mrp/runs/' + run_a), 200)
    mark('pg16_source_and_snapshot', read_a.get('source') == 'postgresql' and isinstance(read_a.get('canonical_snapshot'), dict) and bool(read_a.get('snapshot_hash')))
    snapshot = read_a['canonical_snapshot']
    verify_persisted_plan_evidence(run_a, read_a)
    item_code = snapshot['bom'][0][1]
    item = snapshot['items'][item_code]
    order = snapshot['orders'][0]

    # Full API role matrix. Positive reads are allowed to all five roles.
    for role in roles:
        mark('role_read_run_' + role, call('A', role, 'GET', '/mrp/runs/' + run_a).status_code == 200)
        mark('role_read_workflow_' + role, call('A', role, 'GET', '/workflows/' + run_a).status_code == 200)
        mark('role_read_overview_' + role, call('A', role, 'GET', '/review/overview/' + run_a).status_code == 200)
    for role in ('viewer', 'approver', 'operator'):
        mark('role_' + role + '_mrp_create_403', call('A', role, 'POST', '/mrp/runs', {'scenario': 'A'}).status_code == 403)
    decision_probe = {'run_id': run_a, 'decision': 'APPROVED', 'reason': 'role matrix probe', 'idempotency_key': uuid.uuid4().hex}
    for role in ('viewer', 'planner', 'operator'):
        mark('role_' + role + '_decision_403', call('A', role, 'POST', '/decisions', decision_probe).status_code == 403)
    for role in ('viewer', 'planner', 'approver'):
        mark('role_' + role + '_worker_403', call('A', role, 'POST', '/worker/dispatch').status_code == 403)
    for role in ('viewer', 'approver', 'operator'):
        mark('role_' + role + '_whatif_403', call('A', role, 'POST', '/what-if', {
            'run_id': run_a, 'kind': 'stock', 'target': item_code, 'quantity': str(float(item['on_hand']) + 10)
        }).status_code == 403)
    for role in ('viewer', 'operator'):
        mark('role_' + role + '_dynamic_reconcile_403', call('A', role, 'POST', '/reconciliation/dynamic', {
            'run_id': run_a, 'idempotency_key': uuid.uuid4().hex
        }).status_code == 403)

    for role in roles:
        for path, label in [('/mrp/runs/' + run_a, 'run'), ('/workflows/' + run_a, 'workflow'), ('/review/overview/' + run_a, 'overview')]:
            mark('cross_tenant_' + role + '_' + label + '_404', call('B', role, 'GET', path).status_code == 404)
    mark('cross_tenant_whatif_404', call('B', 'planner', 'POST', '/what-if', {
        'run_id': run_a, 'kind': 'stock', 'target': item_code, 'quantity': str(float(item['on_hand']) + 10)
    }).status_code == 404)

    # What-if for stock, receipt and due date; hash every persisted run table before/after each call.
    what_if_cases = [
        ('stock', {'kind': 'stock', 'target': item_code, 'quantity': str(float(item['on_hand']) + 10)}),
        ('receipt', {'kind': 'receipt', 'target': item_code, 'quantity': '5',
                     'date': (date.fromisoformat(snapshot['as_of']) + timedelta(days=3)).isoformat()}),
        ('due', {'kind': 'due', 'target': order['order_id'],
                 'date': (date.fromisoformat(order['due']) + timedelta(days=7)).isoformat()}),
    ]
    for label, change in what_if_cases:
        with psycopg.connect(dsn) as conn:
            before = run_snapshot(conn, run_a)
        response = call('A', 'planner', 'POST', '/what-if', {'run_id': run_a, **change})
        payload = mark_http('whatif_' + label + '_http', response, 200)
        mark('whatif_' + label + '_no_external_effect', payload.get('side_effect') == 'NONE' and payload.get('workflow_unchanged') is True and payload.get('external_execution') is False)
        mark('whatif_' + label + '_detached_snapshot', payload.get('candidate_snapshot_sha256') != payload.get('baseline_snapshot_sha256'))
        with psycopg.connect(dsn) as conn:
            after = run_snapshot(conn, run_a)
        mark('whatif_' + label + '_pg16_unchanged', before == after, {'tables_compared': len(before)})
        (OUT / ('WHAT_IF_' + label.upper() + '_BEFORE.json')).write_text(json.dumps(before, indent=2), encoding='utf-8')
        (OUT / ('WHAT_IF_' + label.upper() + '_AFTER.json')).write_text(json.dumps(after, indent=2), encoding='utf-8')
    mark('whatif_unknown_material_422', call('A', 'planner', 'POST', '/what-if', {
        'run_id': run_a, 'kind': 'stock', 'target': 'NOT_A_MATERIAL', 'quantity': '80'
    }).status_code == 422)

    # Same-input dynamic A/B: execute frozen native Version A JS and compare with persisted B PG16.
    scenarios = [('A', run_a), ('B', new_run('B')), ('C', new_run('C')), ('D', new_run('D'))]
    for scenario_code, scenario_run in scenarios:
        if scenario_run != run_a:
            verify_persisted_plan_evidence(scenario_run, expected_scenario=scenario_code)
    # Golden evidence is derived from persisted PG16 requirement rows and pegging rows.
    # G01/G02/G03 are honest aliases of B/C/D, not independent factory datasets.
    from decimal import Decimal
    golden = {}
    for code, scenario_code in [('G01','B'),('G02','C'),('G03','D')]:
        run_id = dict(scenarios)[scenario_code]
        with psycopg.connect(dsn) as conn:
            persisted = read_run(conn, run_id)
            source_input = conn.execute('SELECT payload FROM version_b_rc2.run_inputs WHERE tenant_id=%s AND run_id=%s',(tenant_a,run_id)).fetchone()[0]
        lines = persisted['lines']; pegs = persisted['pegs']
        total_gross = sum((Decimal(x['gross']) for x in lines),Decimal(0))
        total_pegged = sum((Decimal(x['gross']) for x in pegs),Decimal(0))
        split = {k: str(sum((Decimal(x[k]) for x in pegs),Decimal(0))) for k in ('from_stock','from_receipts','from_planned')}
        peg_conserved = all(Decimal(x['gross'])==sum((Decimal(x[k]) for k in ('from_stock','from_receipts','from_planned')),Decimal(0)) for x in pegs)
        quantity_conserved = total_gross==total_pegged and peg_conserved
        golden[code] = {
            'scenario':scenario_code, 'run_id':run_id, 'input_hash':persisted['input_hash'],
            'order_count':len(source_input['orders']), 'requirement_lines':len(lines),'pegging_lines':len(pegs),
            'gross_requirement':str(total_gross), 'pegged_requirement':str(total_pegged),
            'pegging_supply_allocation':split, 'quantity_conserved':quantity_conserved,
            'uom_by_material':{k:v.get('uom') for k,v in sorted(source_input['items'].items())},
            'total_net_replenishment':str(sum((Decimal(x['net']) for x in lines),Decimal(0))),
            'total_planned_replenishment':str(sum((Decimal(x['planned']) for x in lines),Decimal(0))),
            'scope':'PG16_PERSISTED_SIMULATED_SCENARIO',
            'physical_factory_execution':'NOT_CLAIMED',
        }
        mark('golden_'+code+'_pg16_quantity_conservation',quantity_conserved,{'gross':str(total_gross),'pegged':str(total_pegged)})
    (OUT/'RC36_GOLDEN_SCENARIOS_PG16.json').write_text(json.dumps(golden,ensure_ascii=False,indent=2),encoding='utf-8')
    result['golden_scenario_evidence']='RC36_GOLDEN_SCENARIOS_PG16.json'
    parity_all_match = True
    for scenario, run_id in scenarios:
        key = uuid.uuid4().hex
        response = call('A', 'planner', 'POST', '/reconciliation/dynamic', {'run_id': run_id, 'idempotency_key': key})
        compared = mark_http('a_b_dynamic_' + scenario + '_http', response, 201)
        unit_differences = [x for x in compared.get('differences', []) if x.get('field') == 'uom']
        mark('a_b_unit_parity_' + scenario, not unit_differences, {'unit_difference_count': len(unit_differences)})
        valid = (compared.get('independent_a_execution_this_request') is True
                 and compared.get('a_result_untrusted') is False
                 and compared.get('a_input_hash') == compared.get('b_input_hash')
                 and compared.get('status') in ('MATCH', 'DIFFERENT')
                 and isinstance(compared.get('differences'), list)
                 and all(bool(x.get('reason')) for x in compared.get('differences', [])))
        mark('a_b_same_snapshot_and_explained_' + scenario, valid, {
            'status': compared.get('status'), 'difference_count': len(compared.get('differences', [])),
            'same_input_hash': compared.get('a_input_hash') == compared.get('b_input_hash'),
            'material_rule_fingerprint': compared.get('material_rule_fingerprint')
        })
        mark('a_b_order_level_pegging_parity_' + scenario,
             compared.get('pegging_status') == 'MATCH' and compared.get('pegging_pass') is True,
             {'pegging_status': compared.get('pegging_status'),
              'a_rows': compared.get('pegging_a_rows'), 'b_rows': compared.get('pegging_b_rows'),
              'ambiguous_rows': compared.get('pegging_ambiguous_rows', [])[:8],
              'differences': compared.get('pegging_differences', [])[:8]})
        if compared.get('status') != 'MATCH' or compared.get('pegging_status') != 'MATCH':
            parity_all_match = False
        scenario_data = call('A', 'viewer', 'GET', '/mrp/runs/' + run_id).json()
        rule_inputs = {code: {key: item.get(key) for key in ('kind','uom','lead_days','moq','lot')}
                       for code,item in sorted(scenario_data['canonical_snapshot'].get('items', {}).items())}
        rule_fingerprint = hashlib.sha256(json.dumps(rule_inputs, sort_keys=True, ensure_ascii=False,
            default=str, separators=(',', ':')).encode()).hexdigest()
        result['a_b_findings'].append({'scenario': scenario, 'run_id': run_id,
            'status': compared.get('status'), 'difference_count': len(compared.get('differences', [])),
            'rule_fingerprint': rule_fingerprint, 'material_rule_inputs': rule_inputs,
            'a_input_hash': compared.get('a_input_hash'), 'b_input_hash': compared.get('b_input_hash'),
            'differences': compared.get('differences', [])})
        replay = mark_http('a_b_replay_' + scenario, call('A', 'planner', 'POST', '/reconciliation/dynamic', {
            'run_id': run_id, 'idempotency_key': key
        }), 201)
        mark('a_b_idempotent_replay_' + scenario, replay.get('idempotent_replay') is True)
    if parity_all_match:
        set_check('a_b_exact_result_parity', 'PASS', 'All A/B/C/D scenario outputs matched within engine tolerance.')
    else:
        set_check('a_b_exact_result_parity', 'HOLD', 'Dynamic same-snapshot comparison ran and differences are explained; business parity needs review.')
    approver_dynamic = mark_http('approver_dynamic_reconciliation_allowed', call('A', 'approver', 'POST', '/reconciliation/dynamic', {
        'run_id': run_a, 'idempotency_key': uuid.uuid4().hex
    }), 201)
    mark('approver_dynamic_same_snapshot', approver_dynamic.get('a_input_hash') == approver_dynamic.get('b_input_hash'))

    # Concurrent approval with the same idempotency key on independent HTTP clients.
    idem_key = uuid.uuid4().hex
    approval = {'run_id': run_a, 'decision': 'APPROVED',
                'reason': 'RC3.6 isolated PG16 concurrent idempotency verification',
                'idempotency_key': idem_key}
    barrier = threading.Barrier(2)
    def concurrent_approve():
        with TestClient(app) as c:
            barrier.wait(timeout=15)
            return call('A', 'approver', 'POST', '/decisions', approval, use_client=c)
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        responses = [f.result(timeout=90) for f in [pool.submit(concurrent_approve), pool.submit(concurrent_approve)]]
    mark('concurrent_decision_http_202', all(r.status_code == 202 for r in responses), {'codes': [r.status_code for r in responses]})
    bodies = [r.json() for r in responses]
    command_id = bodies[0].get('command_id')
    mark('concurrent_decision_single_command', bool(command_id) and bodies[0].get('command_id') == bodies[1].get('command_id'))
    mark('concurrent_decision_replay_observed', sum(x.get('idempotent_replay') is True for x in bodies) == 1)
    result['command_ids'].append(command_id)
    mark('same_key_different_payload_409', call('A', 'approver', 'POST', '/decisions', {
        **approval, 'reason': 'conflicting payload'
    }).status_code == 409)
    mark('new_key_after_terminal_decision_409', call('A', 'approver', 'POST', '/decisions', {
        **approval, 'idempotency_key': uuid.uuid4().hex
    }).status_code == 409)
    mark('cross_tenant_command_404', call('B', 'viewer', 'GET', '/commands/' + command_id).status_code == 404)
    with psycopg.connect(dsn) as conn:
        decision_count = conn.execute('SELECT count(*) FROM version_b_rc2.decisions WHERE tenant_id=%s AND run_id=%s', (tenant_a, run_a)).fetchone()[0]
        outbox_count = conn.execute('SELECT count(*) FROM version_b_rc2.outbox WHERE tenant_id=%s AND run_id=%s', (tenant_a, run_a)).fetchone()[0]
        approval_audit_count = conn.execute("SELECT count(*) FROM version_b_rc2.audit WHERE tenant_id=%s AND details->>'run_id'=%s AND action='APPROVED'", (tenant_a, run_a)).fetchone()[0]
    mark('pg16_one_decision_one_outbox_one_approval_audit', decision_count == outbox_count == approval_audit_count == 1,
         {'decisions': decision_count, 'outbox': outbox_count, 'approval_audit': approval_audit_count})

    def db_connect():
        return psycopg.connect(dsn, connect_timeout=15)

    # Application-level single-job failure, persisted RETRY, then successful recovery.
    failed = process_batch(db_connect, owner='RC36-FAULT-' + uuid.uuid4().hex[:12], tenant=tenant_a, limit=1, fail_injection=True)
    mark('worker_fault_injected', len(failed) == 1 and failed[0]['status'] == 'RETRY_OR_DEAD')
    with psycopg.connect(dsn) as conn:
        status, attempts, receipts = conn.execute('''SELECT o.status,o.attempts,
          (SELECT count(*) FROM version_b_rc2.execution_receipts e WHERE e.command_id=o.command_id)
          FROM version_b_rc2.outbox o WHERE o.command_id=%s''', (command_id,)).fetchone()
    mark('worker_retry_no_premature_receipt', status == 'RETRY' and attempts == 1 and receipts == 0,
         {'status': status, 'attempts': attempts, 'receipts': receipts})
    time.sleep(2.5)
    recovered = process_batch(db_connect, owner='RC36-RECOVER-' + uuid.uuid4().hex[:12], tenant=tenant_a, limit=1, fail_injection=False)
    mark('worker_retry_recovered', len(recovered) == 1 and recovered[0]['status'] == 'DONE')
    with psycopg.connect(dsn) as conn:
        status, attempts, last_error = conn.execute('SELECT status,attempts,last_error FROM version_b_rc2.outbox WHERE command_id=%s', (command_id,)).fetchone()
        receipts = conn.execute('SELECT result FROM version_b_rc2.execution_receipts WHERE command_id=%s', (command_id,)).fetchall()
        audit_actions = {r[0] for r in conn.execute("SELECT action FROM version_b_rc2.audit WHERE tenant_id=%s AND details->>'run_id'=%s", (tenant_a, run_a)).fetchall()}
        workflow = conn.execute('SELECT status FROM version_b_rc2.workflow_states WHERE tenant_id=%s AND run_id=%s', (tenant_a, run_a)).fetchone()[0]
    mark('worker_retry_final_pg16_evidence', status == 'DONE' and attempts == 2 and last_error is None and len(receipts) == 1 and workflow == 'EXECUTED_INTERNAL',
         {'status': status, 'attempts': attempts, 'receipts': len(receipts), 'workflow': workflow})
    receipt = receipts[0][0]
    mark('worker_receipt_internal_only', receipt.get('execution_type') == 'INTERNAL_VALIDATION_ONLY' and receipt.get('external_effect') == 'NONE')
    mark('worker_retry_and_success_audited', {'WORKER_RETRY_PENDING', 'WORKER_EXECUTED_INTERNAL'}.issubset(audit_actions))
    mark('worker_duplicate_dispatch_no_reexecution', not process_batch(db_connect, owner='RC36-IDEMP-' + uuid.uuid4().hex[:12], tenant=tenant_a, limit=1))

    # Two pending jobs claimed by two concurrent PG16 workers via SKIP LOCKED.
    run_e, run_f = new_run('A'), new_run('A')
    commands = []
    for run_id in (run_e, run_f):
        body = {'run_id': run_id, 'decision': 'APPROVED', 'reason': 'parallel worker SKIP LOCKED test', 'idempotency_key': uuid.uuid4().hex}
        commands.append(mark_http('parallel_approve_' + run_id, call('A', 'approver', 'POST', '/decisions', body), 202)['command_id'])
    result['command_ids'].extend(commands)
    worker_barrier = threading.Barrier(2)
    def parallel_worker(index):
        worker_barrier.wait(timeout=15)
        return process_batch(db_connect, owner=f'RC36-PAR-{index}-' + uuid.uuid4().hex[:8], tenant=tenant_a, limit=1)
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        batches = [f.result(timeout=90) for f in [pool.submit(parallel_worker, 1), pool.submit(parallel_worker, 2)]]
    processed = [job for batch in batches for job in batch]
    processed_ids = [job['command_id'] for job in processed]
    mark('pg16_skip_locked_two_distinct_jobs', len(processed_ids) == 2 and set(processed_ids) == set(commands) and len(set(processed_ids)) == 2,
         {'processed_count': len(processed_ids), 'unique_command_count': len(set(processed_ids))})
    with psycopg.connect(dsn) as conn:
        parallel_rows = conn.execute('''SELECT o.command_id,o.status,o.attempts,
          (SELECT count(*) FROM version_b_rc2.execution_receipts e WHERE e.command_id=o.command_id)
          FROM version_b_rc2.outbox o WHERE o.command_id=ANY(%s) ORDER BY o.command_id''', (commands,)).fetchall()
    mark('pg16_parallel_one_receipt_each', len(parallel_rows) == 2 and all(r[1] == 'DONE' and r[2] == 1 and r[3] == 1 for r in parallel_rows))

    # Lease expiry/reclaim: stale owner cannot acknowledge; new owner completes once.
    run_g = new_run('A')
    lease_command = mark_http('lease_test_approval', call('A', 'approver', 'POST', '/decisions', {
        'run_id': run_g, 'decision': 'APPROVED', 'reason': 'lease expiry recovery test', 'idempotency_key': uuid.uuid4().hex
    }), 202)['command_id']
    result['command_ids'].append(lease_command)
    stale_owner = 'RC36-STALE-' + uuid.uuid4().hex[:8]
    with db_connect() as conn:
        stale_jobs = claim(conn, stale_owner, tenant=tenant_a, limit=1, lease_seconds=1)
    mark('worker_lease_initial_claim', len(stale_jobs) == 1 and stale_jobs[0]['command_id'] == uuid.UUID(lease_command))
    time.sleep(1.3)
    recovery_owner = 'RC36-LEASE-RECOVER-' + uuid.uuid4().hex[:8]
    with db_connect() as conn:
        recovered_jobs = claim(conn, recovery_owner, tenant=tenant_a, limit=1, lease_seconds=30)
    mark('worker_expired_lease_reclaimed', len(recovered_jobs) == 1 and recovered_jobs[0]['command_id'] == uuid.UUID(lease_command) and recovered_jobs[0]['attempts'] == 2)
    with db_connect() as conn:
        stale_ack = finish(conn, lease_command, stale_owner,
                           receipt={'execution_type': 'INTERNAL_VALIDATION_ONLY', 'external_effect': 'NONE'})
    mark('worker_stale_owner_ack_rejected', stale_ack is False)
    job = recovered_jobs[0]
    with db_connect() as conn:
        internal_receipt = execute_internal(conn, job)
    with db_connect() as conn:
        finished = finish(conn, lease_command, recovery_owner, receipt=internal_receipt)
    mark('worker_lease_recovery_finished', finished is True)
    with db_connect() as conn:
        st, attempts, receipt_count = conn.execute('''SELECT o.status,o.attempts,
          (SELECT count(*) FROM version_b_rc2.execution_receipts e WHERE e.command_id=o.command_id)
          FROM version_b_rc2.outbox o WHERE o.command_id=%s''', (lease_command,)).fetchone()
    mark('worker_lease_final_exactly_once', st == 'DONE' and attempts == 2 and receipt_count == 1,
         {'status': st, 'attempts': attempts, 'receipts': receipt_count})

    # Admin positive-path coverage, including its own dispatch permission.
    admin_run = new_run('A', role='admin')
    admin_snapshot = mark_http('admin_read_own_run', call('A', 'admin', 'GET', '/mrp/runs/' + admin_run), 200)['canonical_snapshot']
    admin_item = admin_snapshot['bom'][0][1]
    mark_http('admin_whatif_allowed', call('A', 'admin', 'POST', '/what-if', {
        'run_id': admin_run, 'kind': 'stock', 'target': admin_item, 'quantity': '999'
    }), 200)
    admin_dynamic = mark_http('admin_dynamic_allowed', call('A', 'admin', 'POST', '/reconciliation/dynamic', {
        'run_id': admin_run, 'idempotency_key': uuid.uuid4().hex
    }), 201)
    mark('admin_dynamic_same_snapshot', admin_dynamic.get('a_input_hash') == admin_dynamic.get('b_input_hash'))
    admin_decision = mark_http('admin_decision_allowed', call('A', 'admin', 'POST', '/decisions', {
        'run_id': admin_run, 'decision': 'APPROVED', 'reason': 'admin positive role path', 'idempotency_key': uuid.uuid4().hex
    }), 202)
    result['command_ids'].append(admin_decision['command_id'])
    admin_dispatch = mark_http('admin_worker_dispatch_allowed', call('A', 'admin', 'POST', '/worker/dispatch'), 200)
    mark('admin_worker_dispatch_completed', any(x.get('status') == 'DONE' for x in admin_dispatch.get('processed', [])))
    operator_dispatch = mark_http('operator_worker_dispatch_allowed', call('A', 'operator', 'POST', '/worker/dispatch'), 200)
    mark('operator_no_duplicate_pending_job', operator_dispatch.get('processed') == [])

    # Persisted proposal -> approver decision -> Outbox -> internal receipt.
    proposal_run = new_run('A')
    proposal_data = mark_http('proposal_run_read', call('A', 'planner', 'GET', '/mrp/runs/' + proposal_run), 200)
    verify_persisted_plan_evidence(proposal_run, proposal_data)
    proposal_snapshot = proposal_data['canonical_snapshot']
    proposal_material = next((code for code, item in sorted(proposal_snapshot['items'].items())
                              if item.get('kind') == 'BUY'), None)
    mark('proposal_fixture_has_buy_material', proposal_material is not None)
    proposal_item = proposal_snapshot['items'][proposal_material]
    proposal_qty = str(Decimal(str(proposal_item.get('on_hand', '0'))) + Decimal('1'))
    preview = mark_http('proposal_whatif_preview', call('A', 'planner', 'POST', '/what-if', {
        'run_id': proposal_run, 'kind': 'stock', 'target': proposal_material, 'quantity': proposal_qty
    }), 200)
    proposal_key = uuid.uuid4().hex
    proposal_body = {
        'expected_candidate_hash': preview['candidate_snapshot_sha256'],
        'run_id': proposal_run, 'kind': 'stock', 'target': proposal_material,
        'quantity': proposal_qty, 'idempotency_key': proposal_key,
    }
    saved_proposal = mark_http('proposal_save_persisted', call('A', 'planner', 'POST', '/proposals', proposal_body), 201)
    proposal_id = saved_proposal.get('proposal_id')
    mark('proposal_saved_draft', bool(proposal_id) and saved_proposal.get('status') == 'DRAFT'
         and saved_proposal.get('source') == 'PERSISTED_POSTGRESQL')
    proposal_replay = mark_http('proposal_idempotent_replay', call('A', 'planner', 'POST', '/proposals', proposal_body), 201)
    mark('proposal_save_idempotent', proposal_replay.get('proposal_id') == proposal_id
         and proposal_replay.get('idempotent_replay') is True)
    proposal_read = mark_http('proposal_read_back', call('A', 'viewer', 'GET', '/proposals/' + proposal_id), 200)
    mark('proposal_snapshot_hash_bound', proposal_read.get('candidate_hash') == preview.get('candidate_snapshot_sha256'))
    proposal_review_key = uuid.uuid4().hex
    proposal_review_body = {'idempotency_key': proposal_review_key, 'reason': 'RC3.6 isolated PG16 proposal review',
                            'decision': 'APPROVED'}
    proposal_review = mark_http('proposal_approval_persisted', call('A', 'approver', 'POST',
        '/proposals/' + proposal_id + '/review', proposal_review_body), 202)
    proposal_review_replay = mark_http('proposal_approval_replay', call('A', 'approver', 'POST',
        '/proposals/' + proposal_id + '/review', proposal_review_body), 202)
    mark('proposal_approval_idempotent', proposal_review.get('status') == 'APPROVED'
         and proposal_review_replay.get('idempotent_replay') is True
         and proposal_review.get('command_id') == proposal_review_replay.get('command_id'))
    proposal_command = proposal_review['command_id']
    result['command_ids'].append(proposal_command)
    proposal_worker = process_batch(db_connect, owner='RC36-PROPOSAL-' + uuid.uuid4().hex[:10],
                                    tenant=tenant_a, limit=1, fail_injection=False)
    mark('proposal_worker_internal_execution', len(proposal_worker) == 1
         and proposal_worker[0].get('status') == 'DONE')
    with psycopg.connect(dsn) as conn:
        proposal_db = conn.execute('''SELECT p.status,p.command_id,o.status,
              (SELECT count(*) FROM version_b_rc2.execution_receipts e WHERE e.command_id=o.command_id),
              w.status,
              (SELECT count(*) FROM version_b_rc2.audit a WHERE a.tenant_id=p.tenant_id
                 AND a.details->>'run_id'=p.run_id AND a.ref_id=p.proposal_id::text),
              (SELECT d.created_at FROM version_b_rc2.decisions d WHERE d.command_id=p.command_id),
              o.created_at,
              (SELECT e.processed_at FROM version_b_rc2.execution_receipts e WHERE e.command_id=o.command_id),
              (SELECT max(a.created_at) FROM version_b_rc2.audit a WHERE a.tenant_id=p.tenant_id
                 AND a.details->>'run_id'=p.run_id AND a.action='WORKER_EXECUTED_INTERNAL')
            FROM version_b_rc2.proposals p
            JOIN version_b_rc2.outbox o ON o.command_id=p.command_id
            JOIN version_b_rc2.workflow_states w ON w.tenant_id=p.tenant_id AND w.run_id=p.run_id
            WHERE p.tenant_id=%s AND p.proposal_id=%s''', (tenant_a, proposal_id)).fetchone()
    timeline_ok = bool(proposal_db) and proposal_db[6] <= proposal_db[7] <= proposal_db[8] <= proposal_db[9]
    mark('proposal_outbox_receipt_audit_closed', bool(proposal_db)
         and proposal_db[0] == 'APPROVED' and str(proposal_db[1]) == proposal_command
         and proposal_db[2] == 'DONE' and proposal_db[3] == 1 and proposal_db[4] == 'EXECUTED_INTERNAL'
         and proposal_db[5] >= 2 and timeline_ok,
         {'proposal_status': proposal_db[0] if proposal_db else None,
          'outbox_status': proposal_db[2] if proposal_db else None,
          'receipt_count': proposal_db[3] if proposal_db else None,
          'workflow_status': proposal_db[4] if proposal_db else None,
          'proposal_audit_count': proposal_db[5] if proposal_db else None,
          'decision_at': str(proposal_db[6]) if proposal_db else None,
          'outbox_created_at': str(proposal_db[7]) if proposal_db else None,
          'receipt_processed_at': str(proposal_db[8]) if proposal_db else None,
          'worker_audit_at': str(proposal_db[9]) if proposal_db else None,
          'timeline_order_valid': timeline_ok})

    # A real PG statement timeout and a fresh connection afterwards; no other sessions are killed.
    canceled = False
    try:
        with psycopg.connect(dsn, connect_timeout=10) as conn:
            conn.execute("SET LOCAL statement_timeout = '50ms'")
            conn.execute('SELECT pg_sleep(0.25)')
    except psycopg.errors.QueryCanceled:
        canceled = True
    mark('pg16_statement_timeout_cancelled', canceled)
    with psycopg.connect(dsn, connect_timeout=10) as conn:
        recovered_connection = conn.execute('SELECT 1').fetchone()[0]
    mark('pg16_connection_recovered_after_timeout', recovered_connection == 1)

    # Prove the shared mock ERP/WMS source records were not modified by this gate.
    with psycopg.connect(dsn) as conn:
        source_after = source_snapshot(conn)
    mark('mock_erp_wms_source_unchanged', source_before == source_after)
    result['source_tables_after'] = source_after
    result['source_erp_wms_mutations'] = False
    result['schema_changes'] = False
    result['migrations_executed'] = False
    result['status'] = 'PASS' if all(x['status'] == 'PASS' for x in result['checks'].values()) else 'HOLD'


if __name__ == '__main__':
    try:
        main()
    except Halt as exc:
        result['failed_check'] = str(exc)
        result['status'] = 'FAIL'
    except Exception as exc:
        result['exception_class'] = type(exc).__name__
        result['traceback_location_only'] = ' '.join(f'{Path(f.filename).name}:{f.lineno}' for f in traceback.extract_tb(exc.__traceback__)[-5:])
        result['status'] = 'FAIL'
    finally:
        record()
        print('RC36_ENTERPRISE_PG16=' + result['status'])
        for key, entry in result['checks'].items():
            print(key + '=' + entry['status'])
        print('EVIDENCE=' + str(REPORT))
    sys.exit(0 if result['status'] == 'PASS' else 2)
