#!/usr/bin/env python3
"""RC3.5 isolated Neon PG16 enterprise integration gate (separate RC3.5 branch).

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
OUT = ROOT / 'release_evidence' / 'pg16_enterprise'
OUT.mkdir(parents=True, exist_ok=True)
REPORT = OUT / 'RESULT.json'
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
    'scope': 'ISOLATED_NEON_PG16_CANDIDATE_ONLY',
    'privacy': 'connection strings and identity tokens are never written to evidence',
    'frozen_rc2_touched': False,
    'external_effect': 'NONE',
    'schema_changes': False,
    'source_erp_wms_mutations': False,
    'native_database_rls_claimed': False,
    'scope_notes': [
        'Tenant authorization is tested at the API layer; this does not claim native PostgreSQL RLS.',
        'Worker fault injection is an application-level one-job failure plus lease recovery, not a Neon node outage.',
        'Worker receipts prove INTERNAL_VALIDATION_ONLY, not external factory-system command delivery.',
        'Scenario C is a seven-day customer due-date postponement; D is a BOM usage anomaly.',
    ],
    'checks': {}, 'run_ids': [], 'command_ids': [], 'a_b_findings': [], 'status': 'HOLD',
    'timestamp_utc': datetime.now(timezone.utc).isoformat(),
    'source_manifest_sha256': hashlib.sha256((ROOT / 'FINAL_SOURCE_SHA256.json').read_bytes()).hexdigest(),
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
    dsn = os.environ.get('V19B_RC35_ISOLATED_TEST_DATABASE_URL', '')
    if not dsn:
        set_check('isolated_pg16_connection', 'HOLD', 'Secure Neon connection input was not supplied.')
        return None
    if os.environ.get('V19B_RC35_ENABLE_ISOLATED_MUTATIONS') != 'YES':
        set_check('isolated_pg16_mutation_ack', 'HOLD', 'Explicit isolated-write acknowledgement is required.')
        return None
    from rc35_dsn_guard import normalize_dsn, GuardError
    try:
        dsn = normalize_dsn(dsn)
    except GuardError as exc:
        set_check('isolated_pg16_guard', 'FAIL', exc.code)
        return None
    mark('isolated_pg16_guard', True, {'database': 'industrial_v19b_preview', 'endpoint_label': 'rc35-final-gate-isolated-20261105'})
    return dsn


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
    dsn = fail_closed()
    if not dsn:
        return

    import psycopg
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from enterprise_workbench.rc2 import router as rc2_router
    from enterprise_workbench.rc4 import router as rc4_router
    from enterprise_workbench.worker import claim, execute_internal, finish, process_batch
    from app.db.repository import connect as repository_connect, read_run

    with psycopg.connect(dsn, connect_timeout=15) as conn:
        version, db, user, workflow = conn.execute(
            "SELECT current_setting('server_version_num'), current_database(), current_user, to_regclass('version_b_rc2.workflow_states')"
        ).fetchone()
        mark('pg16_and_schema', str(version).startswith('16') and db == 'industrial_v19b_preview' and workflow is not None,
             {'pg_version_num': str(version), 'database': db, 'workflow_table': bool(workflow)})
        required = (
            'version_b_rc2.run_tenants', 'version_b_rc2.run_inputs', 'version_b_rc2.workflow_states',
            'version_b_rc2.decisions', 'version_b_rc2.outbox', 'version_b_rc2.execution_receipts',
            'version_b_rc2.audit', 'version_b_rc2.reconciliation', 'version_b_rc2.proposals', 'platform.requirement_runs',
            'platform.material_requirements', 'platform.requirement_pegs', 'platform.run_snapshot_fences',
        ) + SOURCE_TABLES
        missing = [t for t in required if conn.execute('SELECT to_regclass(%s)', (t,)).fetchone()[0] is None]
        mark('required_pg16_tables', not missing, {'missing': missing})
        source_before = source_snapshot(conn)
        empty = [t for t, v in source_before.items() if v['count'] == 0]
        mark('seeded_source_data_available', not empty, {'empty_source_tables': empty})
    result['source_tables_before'] = source_before

    os.environ['DATABASE_URL'] = dsn
    tenant_a = 'rc35gate-' + uuid.uuid4().hex
    tenant_b = 'rc35gate-' + uuid.uuid4().hex
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

    run_a = new_run('A')
    read_a = mark_http('tenant_A_run_read', call('A', 'viewer', 'GET', '/mrp/runs/' + run_a), 200)
    mark('pg16_source_and_snapshot', read_a.get('source') == 'postgresql' and isinstance(read_a.get('canonical_snapshot'), dict) and bool(read_a.get('snapshot_hash')))
    snapshot = read_a['canonical_snapshot']
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
            'total_net_replenishment':str(sum((Decimal(x['net']) for x in lines),Decimal(0))),
            'total_planned_replenishment':str(sum((Decimal(x['planned']) for x in lines),Decimal(0))),
            'scope':'PG16_PERSISTED_SIMULATED_SCENARIO',
            'physical_factory_execution':'NOT_CLAIMED',
        }
        mark('golden_'+code+'_pg16_quantity_conservation',quantity_conserved,{'gross':str(total_gross),'pegged':str(total_pegged)})
    (OUT/'RC35_GOLDEN_SCENARIOS_PG16.json').write_text(json.dumps(golden,ensure_ascii=False,indent=2),encoding='utf-8')
    result['golden_scenario_evidence']='RC35_GOLDEN_SCENARIOS_PG16.json'
    parity_all_match = True
    for scenario, run_id in scenarios:
        key = uuid.uuid4().hex
        response = call('A', 'planner', 'POST', '/reconciliation/dynamic', {'run_id': run_id, 'idempotency_key': key})
        compared = mark_http('a_b_dynamic_' + scenario + '_http', response, 201)
        valid = (compared.get('independent_a_execution_this_request') is True
                 and compared.get('a_result_untrusted') is False
                 and compared.get('a_input_hash') == compared.get('b_input_hash')
                 and compared.get('status') in ('MATCH', 'DIFFERENT')
                 and isinstance(compared.get('differences'), list)
                 and all(bool(x.get('reason')) for x in compared.get('differences', [])))
        mark('a_b_same_snapshot_and_explained_' + scenario, valid, {
            'status': compared.get('status'), 'difference_count': len(compared.get('differences', [])),
            'same_input_hash': compared.get('a_input_hash') == compared.get('b_input_hash')
        })
        if compared.get('status') != 'MATCH':
            parity_all_match = False
        result['a_b_findings'].append({'scenario': scenario, 'run_id': run_id,
            'status': compared.get('status'), 'difference_count': len(compared.get('differences', [])),
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
                'reason': 'RC3.5 isolated PG16 concurrent idempotency verification',
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
    failed = process_batch(db_connect, owner='RC35-FAULT-' + uuid.uuid4().hex[:12], tenant=tenant_a, limit=1, fail_injection=True)
    mark('worker_fault_injected', len(failed) == 1 and failed[0]['status'] == 'RETRY_OR_DEAD')
    with psycopg.connect(dsn) as conn:
        status, attempts, receipts = conn.execute('''SELECT o.status,o.attempts,
          (SELECT count(*) FROM version_b_rc2.execution_receipts e WHERE e.command_id=o.command_id)
          FROM version_b_rc2.outbox o WHERE o.command_id=%s''', (command_id,)).fetchone()
    mark('worker_retry_no_premature_receipt', status == 'RETRY' and attempts == 1 and receipts == 0,
         {'status': status, 'attempts': attempts, 'receipts': receipts})
    time.sleep(2.5)
    recovered = process_batch(db_connect, owner='RC35-RECOVER-' + uuid.uuid4().hex[:12], tenant=tenant_a, limit=1, fail_injection=False)
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
    mark('worker_duplicate_dispatch_no_reexecution', not process_batch(db_connect, owner='RC35-IDEMP-' + uuid.uuid4().hex[:12], tenant=tenant_a, limit=1))

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
        return process_batch(db_connect, owner=f'RC35-PAR-{index}-' + uuid.uuid4().hex[:8], tenant=tenant_a, limit=1)
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
    stale_owner = 'RC35-STALE-' + uuid.uuid4().hex[:8]
    with db_connect() as conn:
        stale_jobs = claim(conn, stale_owner, tenant=tenant_a, limit=1, lease_seconds=1)
    mark('worker_lease_initial_claim', len(stale_jobs) == 1 and stale_jobs[0]['command_id'] == uuid.UUID(lease_command))
    time.sleep(1.3)
    recovery_owner = 'RC35-LEASE-RECOVER-' + uuid.uuid4().hex[:8]
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
        print('RC35_ENTERPRISE_PG16=' + result['status'])
        for key, entry in result['checks'].items():
            print(key + '=' + entry['status'])
        print('EVIDENCE=' + str(REPORT))
    sys.exit(0 if result['status'] == 'PASS' else 2)
