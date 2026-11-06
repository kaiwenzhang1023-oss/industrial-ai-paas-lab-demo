"""Local contract checks, not PG16 live assertions."""
from pathlib import Path
import importlib.util, json, os, sys
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'backend')]
from fastapi import FastAPI
from fastapi.testclient import TestClient
from enterprise_workbench.rc2 import router as rc2_router
from enterprise_workbench.rc4 import router as rc4_router


def test_private_role_matrix_over_actual_router_before_db(monkeypatch):
    identities=[{'actor':'v','tenant':'tenantA','role':'viewer','token':'viewer-tenantA-secure'},
                {'actor':'p','tenant':'tenantA','role':'planner','token':'planner-tenantA-secure'},
                {'actor':'a','tenant':'tenantA','role':'approver','token':'approver-tenantA-secure'},
                {'actor':'o','tenant':'tenantA','role':'operator','token':'operator-tenantA-secure'}]
    monkeypatch.setenv('VERSION_B_RC2_IDENTITIES_JSON',json.dumps(identities))
    app=FastAPI();app.include_router(rc2_router);app.include_router(rc4_router)
    c=TestClient(app);p='/api/v1/version-b/enterprise'
    def post(token,route,body):return c.post(p+route,headers={'Authorization':'Bearer '+token},json=body)
    decision={'run_id':'missing','decision':'APPROVED','reason':'test','idempotency_key':'a'*12}
    assert c.get(p+'/me').status_code==401
    assert post('viewer-tenantA-secure','/mrp/runs',{'scenario':'A'}).status_code==403
    assert post('approver-tenantA-secure','/mrp/runs',{'scenario':'A'}).status_code==403
    assert post('planner-tenantA-secure','/decisions',decision).status_code==403
    assert post('operator-tenantA-secure','/decisions',decision).status_code==403
    assert post('approver-tenantA-secure','/worker/dispatch',{}).status_code==403
    assert post('viewer-tenantA-secure','/what-if',{'run_id':'missing','kind':'stock','target':'BR-01','quantity':'80'}).status_code==403


def test_new_pg16_runner_fails_closed_without_url(monkeypatch):
    spec=importlib.util.spec_from_file_location('isolation_gate',ROOT/'tests/enterprise_pg16_gate.py')
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.delenv('V19B_RC34_ISOLATED_TEST_DATABASE_URL',raising=False)
    monkeypatch.delenv('V19B_RC34_ENABLE_ISOLATED_MUTATIONS',raising=False)
    assert module.fail_closed() is None
    assert module.result['checks']['isolated_pg16_connection']['status']=='HOLD'


def test_frontend_version_and_backend_internal_boundaries():
    html=(ROOT/'enterprise_workbench/site/index.html').read_text(encoding='utf-8')
    assert 'INDUSTRIAL PLANNING · RC3.5' in html
    js=(ROOT/'enterprise_workbench/site/enterprise-console.js').read_text(encoding='utf-8')
    assert "const SESSION_KEY='v19b_rc35_tab_session'" in js
    assert 'INTERNAL_VALIDATION_ONLY' in js
    worker=(ROOT/'enterprise_workbench/worker.py').read_text(encoding='utf-8')
    assert 'FOR UPDATE SKIP LOCKED' in worker
    assert 'fail_injection=False' in worker
    assert 'external_effect' in worker


def test_both_live_scripts_bind_to_final_source_manifest():
    for f in ('enterprise_pg16_gate.py','live_business_workflow_gate.py'):
        s=(ROOT/'tests'/f).read_text(encoding='utf-8')
        assert 'source_manifest_sha256' in s
        assert 'FINAL_SOURCE_SHA256.json' in s
