"""RC3.4 live Business-First browser gate V4.

Tests the real isolated Render candidate only; creates exactly one new guest MRP.
No production ERP/MES/SRM operation, schema migration or direct PG16 write.
"""
from __future__ import annotations

import json
import hashlib
import uuid
import os
import pathlib
import sys
import time
import traceback
from decimal import Decimal, InvalidOperation
from datetime import datetime, timezone

from playwright.sync_api import sync_playwright

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / 'release_evidence' / 'live_business'
OUT.mkdir(parents=True, exist_ok=True)
URL = os.getenv('V19B_RC34_LIVE_URL', 'https://industrial-ai-paas-v19b-ux-rc31-candidate.onrender.com/workbench/')
BASE = URL.split('/workbench')[0]
API = BASE + '/api/v1/version-b/enterprise'
result = {
    'gate_version': 'RC34_LIVE_BUSINESS_V4',
    'source_manifest_sha256': hashlib.sha256((ROOT / 'FINAL_SOURCE_SHA256.json').read_bytes()).hexdigest(),
    'live_gate_script_sha256': hashlib.sha256(pathlib.Path(__file__).read_bytes()).hexdigest(),
    'target': URL,
    'timestamp_utc': datetime.now(timezone.utc).isoformat(),
    'scope': 'RENDER_RC34_CANDIDATE_GUEST_TENANT_ONLY',
    'checks': {},
    'run_id': None,
    'page_errors': [],
    'failed_requests': [],
    'external_execution': False,
    'status': 'HOLD',
}


def record():
    (OUT / 'RESULT.json').write_text(json.dumps(result, ensure_ascii=False, indent=2, default=str), encoding='utf-8')


def check(name, condition, detail=None):
    result['checks'][name] = {
        'status': 'PASS' if condition else 'FAIL',
        'detail': detail if detail is not None else '',
    }
    record()
    print(name + '=' + result['checks'][name]['status'], flush=True)
    if not condition:
        raise AssertionError(name + ': ' + str(detail)[:400])


def request(ctx, method, path, body=None, token=None, timeout=45000):
    # Make the JSON API content type explicit. Pydantic v2 does not coerce int->str.
    headers = {}
    if token:
        headers['Authorization'] = 'Bearer ' + token
    opts = {'method': method, 'headers': headers, 'timeout': timeout}
    if body is not None:
        headers['Content-Type'] = 'application/json'
        opts['data'] = json.dumps(body, ensure_ascii=False)
    response = ctx.request.fetch(API + path, **opts)
    try:
        payload = response.json()
    except ValueError:
        payload = {'detail': 'NON_JSON_RESPONSE'}
    return response.status, payload


def screenshot(page, filename, *, mandatory=False):
    try:
        page.screenshot(path=str(OUT / filename), full_page=True, timeout=12000)
    except Exception as exc:
        result.setdefault('screenshot_warnings', []).append(filename + ': ' + str(exc)[:180])
        if mandatory:
            raise


def choose_valid_stock_change(snapshot):
    """Use the *persisted* snapshot, not a hardcoded material or quantity."""
    if not isinstance(snapshot, dict):
        raise AssertionError('canonical_snapshot is not a JSON object')
    items = snapshot.get('items')
    if not isinstance(items, dict) or not items:
        raise AssertionError('canonical_snapshot has no item catalog')
    # Prefer a purchased material; only use a make-item if there are no BUY items.
    candidate_items = sorted(items.items(), key=lambda kv: (str(kv[1].get('kind', '')).upper() != 'BUY' if isinstance(kv[1], dict) else True, str(kv[0])))
    for material, fields in candidate_items:
        if not isinstance(fields, dict):
            continue
        try:
            old = Decimal(str(fields['on_hand']))
            allocated = Decimal(str(fields['reserved'])) + Decimal(str(fields['blocked']))
            proposed = max(old, allocated) + Decimal('10')
        except (KeyError, TypeError, ValueError, InvalidOperation):
            continue
        if proposed.is_finite() and Decimal('0') <= proposed <= Decimal('100000000'):
            return {'kind': 'stock', 'target': str(material), 'quantity': str(proposed)}
    raise AssertionError('No safe material stock override available in persisted snapshot')


def run():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(viewport={'width': 1440, 'height': 900})
        page = ctx.new_page()
        page.on('pageerror', lambda err: result['page_errors'].append(str(err)))
        page.on('requestfailed', lambda req: result['failed_requests'].append(req.url.split('?')[0]))
        try:
            response = page.goto(URL, wait_until='domcontentloaded', timeout=90000)
            page.locator('#vbConsole').wait_for(timeout=45000)
            check('candidate_http', response is not None and response.status == 200, response.status if response else 'NO_RESPONSE')
            check('brand_rc34', page.locator('.brand small').inner_text().strip().endswith('RC3.4'))

            page.locator('#vbConsole button[data-action="connect"]').first.click()
            page.locator('#vbConsole button[data-action="create"]:not([disabled])').first.wait_for(timeout=60000)
            check('session_connected', True)
            page.locator('#vbConsole button[data-action="create"]').first.click()
            page.wait_for_function(
                '() => /^MRP-[a-f0-9]+$/i.test(document.querySelector("#vbConsole input[data-bind=runInput]")?.value||"")',
                timeout=60000,
            )
            run_id = page.locator('#vbConsole input[data-bind="runInput"]').first.input_value()
            result['run_id'] = run_id
            check('mrp_created', run_id.startswith('MRP-'), run_id)
            screenshot(page, '01_mrp.png')

            page.reload(wait_until='domcontentloaded', timeout=90000)
            page.locator('#vbConsole').wait_for(timeout=45000)
            page.wait_for_function(
                '(id) => document.querySelector("#vbConsole input[data-bind=runInput]")?.value === id',
                arg=run_id, timeout=60000,
            )
            check('refresh_run_restored', True)
            page.locator('#vbConsole button[data-action="approve"]:not([disabled])').first.wait_for(timeout=45000)
            page.locator('#vbConsole button[data-action="approve"]').first.click()
            page.locator('#vbConsole button[data-action="dispatch"]:not([disabled])').first.wait_for(timeout=60000)
            check('approval_outbox_visible', True)
            screenshot(page, '02_approval.png')
            page.locator('#vbConsole button[data-action="dispatch"]').first.click()
            auth = page.evaluate(
                '() => { const x=JSON.parse(sessionStorage.getItem("v19b_rc35_tab_session")||"null"); return x?.token||null }'
            )
            check('session_token_available', bool(auth))
            # Never write auth token, session storage or HTTP auth headers to disk.
            deadline = time.monotonic() + 90
            overview = {}
            while time.monotonic() < deadline:
                code, overview = request(ctx, 'GET', '/review/overview/' + run_id, token=auth)
                if code != 200:
                    raise AssertionError('worker_overview_http=' + str(code))
                if (overview.get('command') or {}).get('status') == 'DONE':
                    break
                page.wait_for_timeout(1500)
            check('worker_persisted_done', (overview.get('command') or {}).get('status') == 'DONE',
                  (overview.get('command') or {}).get('status'))

            page.locator('#vbConsole button[data-action="refresh"]:not([disabled])').first.click()
            page.locator('#vbConsole button[data-action="receipt"]:not([disabled])').first.wait_for(timeout=60000)
            page.locator('#vbConsole button[data-action="receipt"]').first.click()
            screenshot(page, '03_receipt.png')
            page.locator('#vbConsole button[data-action="refresh"]:not([disabled])').first.click()
            page.locator('#vbConsole .vbc-business-timeline li').first.wait_for(timeout=60000)
            screenshot(page, '04_audit.png')
            check('audit_rendered', page.locator('#vbConsole .vbc-business-timeline li').count() >= 3,
                  page.locator('#vbConsole .vbc-business-timeline li').count())

            code, overview = request(ctx, 'GET', '/review/overview/' + run_id, token=auth)
            check('backend_overview', code == 200, code)
            check('backend_pg16_source', overview.get('source') == 'PERSISTED_POSTGRESQL')
            decision = overview.get('decision') or {}
            check('backend_approval', decision.get('type') == 'APPROVED')
            cmd = overview.get('command') or {}
            check('backend_worker_done', cmd.get('status') == 'DONE', cmd.get('status'))
            receipt = cmd.get('receipt')
            check('backend_receipt', isinstance(receipt, dict) and bool(receipt))
            check('backend_internal_only', receipt.get('execution_type') == 'INTERNAL_VALIDATION_ONLY'
                  and receipt.get('external_effect') == 'NONE' and overview.get('external_execution') is False)
            events = overview.get('events') or []
            actions = [e.get('action') for e in events]
            check('backend_audit_approval_and_execution', 'APPROVED' in actions and 'WORKER_EXECUTED_INTERNAL' in actions,
                  {'actions': actions[:30]})

            # Compare persisted record before and after What-if; do not claim this is
            # equivalent to the separate 12-table PG16 before/after evidence.
            code, run_before = request(ctx, 'GET', '/mrp/runs/' + run_id, token=auth)
            check('whatif_source_http', code == 200, code)
            change = choose_valid_stock_change(run_before.get('canonical_snapshot'))
            body = {'run_id': run_id, **change}
            result['whatif_input'] = change  # material + string quantity; no secrets
            before = (run_before.get('snapshot_hash'), overview.get('snapshot_hash'), overview.get('workflow'),
                      overview.get('decision'), cmd.get('status'), len(events))
            code, wf = request(ctx, 'POST', '/what-if', body=body, token=auth)
            # Preserve API validation detail for diagnosis; the API response contains no session token.
            check('whatif_http', code == 200, {'http': code, 'detail': wf.get('detail', '')})
            check('whatif_no_effect_contract', wf.get('side_effect') == 'NONE'
                  and wf.get('workflow_unchanged') is True and wf.get('external_execution') is False)
            check('whatif_snapshot_detached', wf.get('baseline_snapshot_sha256')
                  != wf.get('candidate_snapshot_sha256'))
            code, after_overview = request(ctx, 'GET', '/review/overview/' + run_id, token=auth)
            check('whatif_recheck_http', code == 200, code)
            code, run_after = request(ctx, 'GET', '/mrp/runs/' + run_id, token=auth)
            check('whatif_snapshot_recheck_http', code == 200, code)
            after_cmd = after_overview.get('command') or {}
            after = (run_after.get('snapshot_hash'), after_overview.get('snapshot_hash'),
                     after_overview.get('workflow'), after_overview.get('decision'), after_cmd.get('status'),
                     len(after_overview.get('events') or []))
            check('whatif_business_state_unchanged', before == after and run_before.get('canonical_snapshot')
                  == run_after.get('canonical_snapshot'))

            # Explicit native-A/native-B comparison after proving What-if has no state effect.
            # This may persist an intended reconciliation/audit record, so it must run afterwards.
            key = uuid.uuid4().hex
            code, reconciliation = request(ctx, 'POST', '/reconciliation/dynamic',
                                           body={'run_id': run_id, 'idempotency_key': key}, token=auth,
                                           timeout=60000)
            check('dynamic_native_a_b_http', code == 201,
                  {'http': code, 'detail': reconciliation.get('detail', '')})
            check('dynamic_a_b_independent',
                  reconciliation.get('source') == 'NATIVE_A_RC8_DYNAMIC_AND_B_PG16'
                  and reconciliation.get('independent_a_execution_this_request') is True
                  and reconciliation.get('b_source') == 'PERSISTED_POSTGRESQL'
                  and reconciliation.get('a_input_hash') == reconciliation.get('b_input_hash'))
            check('dynamic_a_b_explained',
                  reconciliation.get('status') == 'MATCH' and not reconciliation.get('differences'),
                  {'status': reconciliation.get('status'), 'differences': reconciliation.get('differences')})
            other = ctx.request.post(BASE + '/api/v1/version-b/preview/session', timeout=30000)
            check('other_guest_session', other.status == 200, other.status)
            other_token = other.json().get('access_token')
            check('other_guest_token', bool(other_token))
            code, _ = request(ctx, 'GET', '/mrp/runs/' + run_id, token=other_token)
            check('cross_tenant_404', code == 404, code)
            code, _ = request(ctx, 'GET', '/mrp/runs/' + run_id)
            check('unauthenticated_401', code == 401, code)
            check('page_errors_zero', not result['page_errors'], len(result['page_errors']))
            check('failed_requests_zero', not result['failed_requests'], len(result['failed_requests']))
            result['status'] = 'PASS'
        except Exception as exc:
            # Screenshot while Playwright event loop, browser and page are still alive.
            screenshot(page, 'FAIL_AT_STEP.png')
            result['status'] = 'FAIL'
            result['error'] = type(exc).__name__ + ': ' + str(exc)[:600]
            result['traceback_tail'] = traceback.format_exc()[-1200:]
        finally:
            record()
            ctx.close()
            browser.close()


if __name__ == '__main__':
    try:
        run()
    except Exception as exc:
        result['status'] = 'FAIL'
        result['error'] = type(exc).__name__ + ': ' + str(exc)[:600]
        result['traceback_tail'] = traceback.format_exc()[-1200:]
    finally:
        record()
        print('LIVE_BUSINESS=' + result['status'], flush=True)
        print('GATE_VERSION=' + result['gate_version'], flush=True)
        print('RUN_ID=' + str(result['run_id']), flush=True)
        print('EVIDENCE=' + str(OUT / 'RESULT.json'), flush=True)
        sys.exit(0 if result['status'] == 'PASS' else 2)
