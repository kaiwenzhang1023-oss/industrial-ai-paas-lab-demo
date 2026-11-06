"""RC3.6 isolated Neon PG16 read-only preflight. No DDL, DML or fault injection."""
from __future__ import annotations
import hashlib
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tests'))
from rc36_dsn_guard import GuardError, normalize_dsn, safe_target

OUT = ROOT / 'release_evidence' / 'rc36' / 'PG16_READONLY_RESULT.json'
OUT.parent.mkdir(parents=True, exist_ok=True)
report = {
    'gate': 'PG16_READONLY_PREFLIGHT', 'status': 'HOLD',
    'scope': safe_target(), 'mutations': False, 'migrations_executed': False,
    'fault_injection_executed': False, 'secrets_logged': False, 'checks': {},
}


def finish(code=None):
    OUT.write_text(json.dumps(report, indent=2, ensure_ascii=False, default=str), encoding='utf-8')
    print('PG16_READONLY=' + report['status'] + ' REPORT=' + str(OUT))
    return code if code is not None else (0 if report['status'] == 'PASS' else 2)


def check(name, status, detail=None):
    item = {'status': status}
    if detail is not None:
        item['detail'] = detail
    report['checks'][name] = item


def main():
    raw = os.environ.get('RC36_ISOLATED_PG16_DSN', '')
    if not raw:
        check('connection_string', 'HOLD', 'RC36_ISOLATED_PG16_DSN was not supplied.')
        return finish()
    try:
        dsn = normalize_dsn(raw)
    except GuardError as exc:
        check('endpoint_allowlist', 'FAIL', exc.code)
        report['status'] = 'FAIL'
        return finish()
    check('endpoint_allowlist', 'PASS', safe_target())
    try:
        import psycopg
        with psycopg.connect(
            dsn, connect_timeout=12,
            options='-c default_transaction_read_only=on',
        ) as conn:
            with conn.cursor() as cur:
                cur.execute('SELECT current_setting(%s), current_database(), current_user, pg_is_in_recovery()',
                            ('server_version_num',))
                version, database, role, recovery = cur.fetchone()
                cur.execute('SHOW transaction_read_only')
                readonly = cur.fetchone()[0]
                version_num = int(version)
                check('pg16_version', 'PASS' if 160000 <= version_num < 170000 else 'FAIL', version_num)
                check('database_identity', 'PASS' if database == safe_target()['database'] else 'FAIL', database)
                check('read_only_session', 'PASS' if readonly == 'on' else 'FAIL', readonly)
                check('endpoint_branch_scope', 'PASS', safe_target()['branch_id'])
                check('role_identity', 'PASS', hashlib.sha256(str(role).encode()).hexdigest())
                check('standby_state', 'INFO', {'in_recovery': recovery})

                required_tables = [
                    'mock_erp.sales_orders', 'mock_erp.materials', 'mock_erp.bom_versions',
                    'mock_erp.bom_items', 'mock_erp.supply_orders', 'mock_wms.inventory_balances',
                    'platform.requirement_runs', 'platform.material_requirements',
                    'platform.requirement_pegs', 'platform.run_snapshot_fences',
                    'version_b_rc2.run_tenants', 'version_b_rc2.run_inputs',
                    'version_b_rc2.workflow_states', 'version_b_rc2.decisions',
                    'version_b_rc2.outbox', 'version_b_rc2.execution_receipts',
                    'version_b_rc2.audit', 'version_b_rc2.reconciliation',
                    'version_b_rc2.proposals', 'version_b_rc2.mcp_call_audit',
                ]
                missing = []
                for table in required_tables:
                    cur.execute('SELECT to_regclass(%s)', (table,))
                    if cur.fetchone()[0] is None:
                        missing.append(table)
                check('required_tables', 'PASS' if not missing else 'FAIL',
                      {'count': len(required_tables), 'missing': missing})
                if missing:
                    report['status'] = 'FAIL'
                    report['failed_checks'] = ['required_tables']
                    return finish()

                required_columns = {
                    'mock_erp.sales_orders': {'order_id','product_id','quantity','due_date','priority','status','version'},
                    'mock_erp.materials': {'material_id','make_buy','lead_days','safety_stock','moq','lot_multiple','uom'},
                    'mock_erp.bom_versions': {'bom_id','version','status','effective_from','effective_to'},
                    'mock_erp.bom_items': {'bom_id','version','line_id','parent_id','component_id','qty_per'},
                    'mock_erp.supply_orders': {'supply_id','material_id','open_qty','arrival_date','status'},
                    'mock_wms.inventory_balances': {'material_id','warehouse_id','lot_id','on_hand','reserved','blocked','snapshot_at','version'},
                    'platform.requirement_runs': {'run_id','order_set_hash','input_hash','rule_version','status','created_at'},
                    'platform.material_requirements': {'run_id','material_id','need_date','gross','net','planned','projected_balance'},
                    'platform.requirement_pegs': {'run_id','material_id','need_date','order_id','gross','from_stock','from_receipts','from_planned'},
                    'platform.run_snapshot_fences': {'run_id','as_of','source_versions','created_at'},
                    'version_b_rc2.run_tenants': {'tenant_id','run_id','actor_id','created_at'},
                    'version_b_rc2.run_inputs': {'tenant_id','run_id','input_hash','payload','created_at'},
                    'version_b_rc2.workflow_states': {'tenant_id','run_id','status','version','updated_at'},
                    'version_b_rc2.decisions': {'tenant_id','run_id','actor_id','idempotency_key','decision','reason','command_id','created_at'},
                    'version_b_rc2.outbox': {'command_id','tenant_id','run_id','payload','status','attempts','last_error','created_at','updated_at','lease_owner','lease_until','next_attempt_at'},
                    'version_b_rc2.execution_receipts': {'command_id','tenant_id','run_id','result','processed_at'},
                    'version_b_rc2.audit': {'id','tenant_id','actor_id','action','ref_id','details','created_at'},
                    'version_b_rc2.reconciliation': {'tenant_id','run_id','actor_id','idempotency_key','payload','created_at'},
                    'version_b_rc2.proposals': {'proposal_id','tenant_id','run_id','actor_id','idempotency_key','request_hash','input_hash','candidate_hash','change_request','simulation_result','status','command_id','created_at','updated_at'},
                    'version_b_rc2.mcp_call_audit': {'id','tenant_id','actor_id','tool_name','arguments_sha256','request_id','outcome','created_at'},
                }
                column_gaps = {}
                for table, expected in required_columns.items():
                    schema, name = table.split('.', 1)
                    cur.execute("SELECT column_name FROM information_schema.columns WHERE table_schema=%s AND table_name=%s", (schema, name))
                    actual = {r[0] for r in cur.fetchall()}
                    gap = sorted(expected - actual)
                    if gap:
                        column_gaps[table] = gap
                check('required_columns', 'PASS' if not column_gaps else 'FAIL', column_gaps)
                if column_gaps:
                    report['status'] = 'FAIL'
                    report['failed_checks'] = ['required_columns']
                    return finish()

                cur.execute("SELECT rolname, rolsuper, rolcreatedb, rolcreaterole FROM pg_roles WHERE rolname=current_user")
                role_row = cur.fetchone()
                role_ok = bool(role_row) and role_row[0] == 'v19b_app_runtime' and not role_row[1] and not role_row[2] and not role_row[3]
                check('least_privilege_runtime_role', 'PASS' if role_ok else 'FAIL',
                      {'role_name': role_row[0] if role_row else None,
                       'is_superuser': role_row[1] if role_row else None,
                       'can_create_db': role_row[2] if role_row else None,
                       'can_create_role': role_row[3] if role_row else None})

                privilege_checks = {
                    'mock_erp.sales_orders:SELECT': ('mock_erp.sales_orders', 'SELECT'),
                    'mock_erp.materials:SELECT': ('mock_erp.materials', 'SELECT'),
                    'mock_erp.bom_versions:SELECT': ('mock_erp.bom_versions', 'SELECT'),
                    'mock_erp.bom_items:SELECT': ('mock_erp.bom_items', 'SELECT'),
                    'mock_erp.supply_orders:SELECT': ('mock_erp.supply_orders', 'SELECT'),
                    'mock_wms.inventory_balances:SELECT': ('mock_wms.inventory_balances', 'SELECT'),
                    'platform.requirement_runs:SELECT': ('platform.requirement_runs', 'SELECT'),
                    'platform.requirement_runs:INSERT': ('platform.requirement_runs', 'INSERT'),
                    'platform.material_requirements:SELECT': ('platform.material_requirements', 'SELECT'),
                    'platform.material_requirements:INSERT': ('platform.material_requirements', 'INSERT'),
                    'platform.requirement_pegs:SELECT': ('platform.requirement_pegs', 'SELECT'),
                    'platform.requirement_pegs:INSERT': ('platform.requirement_pegs', 'INSERT'),
                    'platform.run_snapshot_fences:SELECT': ('platform.run_snapshot_fences', 'SELECT'),
                    'platform.run_snapshot_fences:INSERT': ('platform.run_snapshot_fences', 'INSERT'),
                    'version_b_rc2.run_tenants:SELECT': ('version_b_rc2.run_tenants', 'SELECT'),
                    'version_b_rc2.run_tenants:INSERT': ('version_b_rc2.run_tenants', 'INSERT'),
                    'version_b_rc2.run_inputs:SELECT': ('version_b_rc2.run_inputs', 'SELECT'),
                    'version_b_rc2.run_inputs:INSERT': ('version_b_rc2.run_inputs', 'INSERT'),
                    'version_b_rc2.workflow_states:SELECT': ('version_b_rc2.workflow_states', 'SELECT'),
                    'version_b_rc2.workflow_states:INSERT': ('version_b_rc2.workflow_states', 'INSERT'),
                    'version_b_rc2.workflow_states:UPDATE': ('version_b_rc2.workflow_states', 'UPDATE'),
                    'version_b_rc2.decisions:SELECT': ('version_b_rc2.decisions', 'SELECT'),
                    'version_b_rc2.decisions:INSERT': ('version_b_rc2.decisions', 'INSERT'),
                    'version_b_rc2.outbox:SELECT': ('version_b_rc2.outbox', 'SELECT'),
                    'version_b_rc2.outbox:INSERT': ('version_b_rc2.outbox', 'INSERT'),
                    'version_b_rc2.outbox:UPDATE': ('version_b_rc2.outbox', 'UPDATE'),
                    'version_b_rc2.execution_receipts:SELECT': ('version_b_rc2.execution_receipts', 'SELECT'),
                    'version_b_rc2.execution_receipts:INSERT': ('version_b_rc2.execution_receipts', 'INSERT'),
                    'version_b_rc2.audit:SELECT': ('version_b_rc2.audit', 'SELECT'),
                    'version_b_rc2.audit:INSERT': ('version_b_rc2.audit', 'INSERT'),
                    'version_b_rc2.reconciliation:SELECT': ('version_b_rc2.reconciliation', 'SELECT'),
                    'version_b_rc2.reconciliation:INSERT': ('version_b_rc2.reconciliation', 'INSERT'),
                    'version_b_rc2.proposals:SELECT': ('version_b_rc2.proposals', 'SELECT'),
                    'version_b_rc2.proposals:INSERT': ('version_b_rc2.proposals', 'INSERT'),
                    'version_b_rc2.proposals:UPDATE': ('version_b_rc2.proposals', 'UPDATE'),
                    'version_b_rc2.mcp_call_audit:SELECT': ('version_b_rc2.mcp_call_audit', 'SELECT'),
                }
                missing_privileges = []
                for label, (table, privilege) in privilege_checks.items():
                    cur.execute('SELECT has_table_privilege(current_user,%s,%s)', (table, privilege))
                    if not cur.fetchone()[0]:
                        missing_privileges.append(label)
                check('runtime_role_required_table_privileges',
                      'PASS' if not missing_privileges else 'FAIL',
                      {'checked': len(privilege_checks), 'missing': missing_privileges})
                schema_usage = {}
                for schema in ('mock_erp', 'mock_wms', 'platform', 'version_b_rc2'):
                    cur.execute('SELECT has_schema_privilege(current_user,%s,\'USAGE\')', (schema,))
                    schema_usage[schema] = bool(cur.fetchone()[0])
                check('runtime_role_schema_usage', 'PASS' if all(schema_usage.values()) else 'FAIL', schema_usage)
                cur.execute("SELECT has_sequence_privilege(current_user,'version_b_rc2.audit_id_seq','USAGE')")
                audit_sequence_usage = bool(cur.fetchone()[0])
                check('runtime_role_audit_sequence_usage', 'PASS' if audit_sequence_usage else 'FAIL', audit_sequence_usage)

                source_counts = {}
                for table in ('mock_erp.sales_orders', 'mock_erp.materials', 'mock_erp.bom_versions',
                              'mock_erp.bom_items', 'mock_erp.supply_orders', 'mock_wms.inventory_balances'):
                    cur.execute('SELECT count(*) FROM ' + table)
                    source_counts[table] = int(cur.fetchone()[0])
                check('seed_source_data', 'PASS' if all(v > 0 for v in source_counts.values()) else 'FAIL', source_counts)
                cur.execute("SELECT count(*), count(*) FILTER (WHERE uom IS NULL OR btrim(uom)='') FROM mock_erp.materials")
                material_count, missing_uom = cur.fetchone()
                check('material_uom_coverage', 'PASS' if material_count > 0 and missing_uom == 0 else 'FAIL',
                      {'materials': material_count, 'missing_uom': missing_uom,
                       'uom_snapshot_source': 'mock_erp.materials.uom -> version_b_rc2.run_inputs.payload.items[*].uom'})

                cur.execute("""SELECT count(*) FROM pg_indexes
                    WHERE schemaname='version_b_rc2' AND indexname='rc2_single_terminal_decision'""")
                single_decision = int(cur.fetchone()[0])
                cur.execute("""SELECT count(*) FROM pg_indexes
                    WHERE schemaname='version_b_rc2' AND indexname='rc2_outbox_lease_poll'""")
                lease_index = int(cur.fetchone()[0])
                check('approval_and_worker_indexes', 'PASS' if single_decision == 1 and lease_index == 1 else 'FAIL',
                      {'single_terminal_decision': single_decision, 'outbox_lease_poll': lease_index})

                cur.execute("""SELECT count(*) FROM pg_constraint
                    WHERE conrelid='version_b_rc2.proposals'::regclass AND contype='c'
                      AND pg_get_constraintdef(oid) ILIKE '%COMPENSATION_REQUESTED%'""")
                proposal_state_check = int(cur.fetchone()[0])
                check('proposal_state_constraint', 'PASS' if proposal_state_check == 1 else 'FAIL', proposal_state_check)

                cur.execute("""SELECT count(*) FROM information_schema.tables
                    WHERE table_schema NOT IN ('pg_catalog','information_schema')
                      AND (table_name ILIKE '%migration%' OR table_name ILIKE '%schema_version%')""")
                ledger_count = int(cur.fetchone()[0])
                check('migration_provenance', 'STRUCTURE_VERIFIED_NO_LEDGER' if ledger_count == 0 else 'LEDGER_PRESENT',
                      {'ledger_tables': ledger_count, 'note': 'Schema structure is checked; no migration ledger table is present.'})

        failing = [k for k, v in report['checks'].items() if v['status'] == 'FAIL']
        report['status'] = 'FAIL' if failing else 'PASS'
        report['failed_checks'] = failing
    except Exception as exc:
        check('connection_or_query', 'HOLD', {'exception_type': type(exc).__name__})
        report['status'] = 'HOLD'
    return finish()


if __name__ == '__main__':
    sys.exit(main())
