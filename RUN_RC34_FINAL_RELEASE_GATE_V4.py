"""Non-mutating V4 readiness summary. Final promotion still requires independent cloud review."""
from __future__ import annotations
import datetime
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
EV = ROOT / 'release_evidence'
EXPECTED = (
    'candidate_http', 'brand_rc34', 'session_connected', 'mrp_created',
    'refresh_run_restored', 'approval_outbox_visible', 'session_token_available',
    'worker_persisted_done', 'audit_rendered', 'backend_overview',
    'backend_pg16_source', 'backend_approval', 'backend_worker_done',
    'backend_receipt', 'backend_internal_only', 'backend_audit_approval_and_execution',
    'whatif_source_http', 'whatif_http', 'whatif_no_effect_contract',
    'whatif_snapshot_detached', 'whatif_recheck_http', 'whatif_snapshot_recheck_http',
    'whatif_business_state_unchanged', 'dynamic_native_a_b_http',
    'dynamic_a_b_independent', 'dynamic_a_b_explained', 'other_guest_session',
    'other_guest_token', 'cross_tenant_404', 'unauthenticated_401',
    'page_errors_zero', 'failed_requests_zero',
)


def read(relative):
    f = ROOT / relative
    return json.loads(f.read_text(encoding='utf-8')) if f.exists() else None


def manifest_check(name):
    data = read(name)
    if not isinstance(data, dict):
        return {'status': 'HOLD', 'detail': name + ' is missing'}
    bad = [k for k, digest in data.items() if not (ROOT / k).is_file()
           or hashlib.sha256((ROOT / k).read_bytes()).hexdigest() != digest]
    return {'status': 'PASS' if not bad else 'FAIL', 'files': len(data), 'mismatched': bad}


def main():
    base = ROOT / 'FINAL_SOURCE_SHA256.json'
    base_sha = hashlib.sha256(base.read_bytes()).hexdigest() if base.exists() else ''
    results = {}
    results['original_106_file_source_manifest'] = manifest_check('FINAL_SOURCE_SHA256.json')
    results['v4_audit_overlay_manifest'] = manifest_check('RC34_LIVE_V4_OVERLAY_SHA256.json')
    pg = read('release_evidence/pg16_enterprise/RESULT.json')
    pg_ok = bool(pg and pg.get('status') == 'PASS'
        and pg.get('source_manifest_sha256') == base_sha
        and len(pg.get('checks', {})) == 137
        and all(v.get('status') == 'PASS' for v in pg['checks'].values())
        and pg.get('frozen_rc2_touched') is False
        and pg.get('external_effect') == 'NONE'
        and pg.get('source_tables_before') == pg.get('source_tables_after'))
    results['isolated_pg16_137'] = {'status': 'PASS' if pg_ok else 'HOLD', 'count': len(pg.get('checks', {})) if pg else 0}
    fr = read('release_evidence/frozen_rc2/RESULT.json')
    frozen_ok = bool(fr and fr.get('branch_id') == 'br-patient-surf-bb9nyu0h'
        and fr.get('matched_runs') == 0 and fr.get('write_operations') == 0
        and fr.get('source_manifest_sha256') == base_sha
        and fr.get('checked_run_ids') == (pg.get('run_ids') if pg else None))
    results['frozen_rc2_readonly_test_run_absence'] = {
        'status': 'PASS' if frozen_ok else 'HOLD',
        'scope': '11 isolated and live Run IDs absent; no full historical-content hash claim',
    }
    live = read('release_evidence/live_business/RESULT.json')
    missing = [k for k in EXPECTED if not live or live.get('checks', {}).get(k, {}).get('status') != 'PASS']
    live_ok = bool(live and live.get('status') == 'PASS'
        and live.get('source_manifest_sha256') == base_sha
        and live.get('gate_version') == 'RC34_LIVE_BUSINESS_V4'
        and live.get('live_gate_script_sha256') == hashlib.sha256((ROOT / 'tests/live_business_workflow_gate_v4.py').read_bytes()).hexdigest()
        and live.get('target') == 'https://industrial-ai-paas-v19b-ux-rc31-candidate.onrender.com/workbench/'
        and not missing and not live.get('page_errors') and not live.get('failed_requests')
        and live.get('external_execution') is False)
    results['real_render_browser_business_flow'] = {'status': 'PASS' if live_ok else 'HOLD', 'missing_or_failed': missing}
    # A local artifact cannot independently verify that the cloud service still points to
    # the recorded commit when the user runs this offline. Verify it via Render separately.
    results['post_gate_render_commit_recheck'] = {
        'status': 'HOLD', 'reason': 'Requires independent current Render deploy/commit verification after live browser result',
        'expected_commit': '638665eb2640818b323def120071b0036f80a0a7',
    }
    all_evidence = all(v['status'] == 'PASS' for k, v in results.items() if k != 'post_gate_render_commit_recheck')
    report = {
        'run_at_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'base_manifest_sha256': base_sha, 'checks': results,
        'evidence_complete_except_cloud_recheck': all_evidence,
        'final_release_gate': 'HOLD',
        'reason': 'Final online Render commit and release evidence signoff have not yet been performed',
        'no_runtime_mutations': True,
    }
    EV.mkdir(exist_ok=True)
    (EV / 'FINAL_RELEASE_GATE_V4_RESULT.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print('V4_EVIDENCE_COMPLETE_EXCEPT_CLOUD_RECHECK=' + ('YES' if all_evidence else 'NO'))
    for k, v in results.items():
        print(k + '=' + v['status'])
    print('FINAL_RELEASE_GATE=HOLD (post-gate cloud verification required)')
    print('EVIDENCE=' + str(EV / 'FINAL_RELEASE_GATE_V4_RESULT.json'))
    return 0 if all_evidence else 2


if __name__ == '__main__':
    raise SystemExit(main())
