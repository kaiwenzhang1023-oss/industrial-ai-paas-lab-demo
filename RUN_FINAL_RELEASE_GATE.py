#!/usr/bin/env python3
"""RC3.4 consolidated final gate. No database mutations or cloud deploys here.

Read credentials only through environment when the user separately opts into the
isolated PG16 gate. PASS means evidence exists for the exact packaged source
manifest; a source change invalidates existing certificates. Frozen RC2 requires
separate branch-side, read-only confirmation for *new* run IDs.
"""
from __future__ import annotations
import hashlib, json, os, pathlib, subprocess, sys, time, urllib.request
ROOT=pathlib.Path(__file__).resolve().parent
REPORT=ROOT/'release_evidence'
URL='https://industrial-ai-paas-v19b-ux-rc31-candidate.onrender.com'


def run_step(name,argv,timeout=180):
    started=time.time()
    try:
        r=subprocess.run(argv,cwd=ROOT,capture_output=True,text=True,timeout=timeout,
            env={**os.environ,'PYTHONPATH':str(ROOT)+os.pathsep+str(ROOT/'backend')})
        raw=(r.stdout+'\n'+r.stderr)[-50000:]
        (REPORT/(name+'.log')).write_text(raw,encoding='utf-8')
        return {'status':'PASS' if r.returncode==0 else 'FAIL','exit_code':r.returncode,
                'duration_seconds':round(time.time()-started,2),'log':name+'.log',
                'error_tail':raw[-1500:] if r.returncode else None}
    except Exception as e:
        (REPORT/(name+'.log')).write_text(type(e).__name__,encoding='utf-8')
        return {'status':'HOLD','error':type(e).__name__,'log':name+'.log'}


def http_read(path):
    try:
        with urllib.request.urlopen(urllib.request.Request(URL+path,headers={'User-Agent':'V19B-ReadOnly-ReleaseGate/1.1'}),timeout=25) as r:
            obj=json.loads(r.read(16000))
            return {'status':'PASS' if r.status==200 and obj.get('status') in ('ready','ok') else 'FAIL',
                    'http':r.status,'body':obj}
    except Exception as e:return {'status':'HOLD','reason':type(e).__name__}


def db_read():
    dsn=os.environ.get('V19B_RC34_ISOLATED_TEST_DATABASE_URL')
    if not dsn:return {'status':'HOLD','reason':'isolated PG16 DSN not supplied; no database accessed'}
    try:
        import psycopg
        from psycopg.conninfo import conninfo_to_dict
        d=conninfo_to_dict(dsn)
        if 'ep-twilight-violet-bb8pm1v6' not in d.get('host','').lower() or d.get('dbname')!='industrial_v19b_preview':
            return {'status':'FAIL','reason':'candidate isolated DB allowlist did not match'}
        with psycopg.connect(dsn,connect_timeout=10,options='-c default_transaction_read_only=on') as c:
            with c.cursor() as cur:
                cur.execute('SELECT current_setting(%s), current_database(), to_regclass(%s)',
                    ('server_version_num','version_b_rc2.workflow_states'))
                v,name,t=cur.fetchone()
        return {'status':'PASS' if str(v).startswith('16') and t is not None and name=='industrial_v19b_preview' else 'FAIL',
                'postgres_version_num':v,'database':name,'schema_present':bool(t),'mode':'read_only'}
    except Exception as e:
        return {'status':'HOLD','reason':type(e).__name__}


def hashes():
    try: manifest=json.loads((ROOT/'FINAL_SOURCE_SHA256.json').read_text(encoding='utf-8'))
    except Exception:return {'status':'FAIL','reason':'Missing or invalid final source manifest'}
    if not isinstance(manifest,dict):return {'status':'FAIL','reason':'Invalid manifest type'}
    mismatches=[]
    for name,expected in manifest.items():
        # Do not permit traversal or absolute manifest paths.
        p=ROOT/name
        if p.resolve().is_relative_to(ROOT.resolve()) and p.is_file():
            actual=hashlib.sha256(p.read_bytes()).hexdigest()
        else: actual='MISSING_OR_UNSAFE_PATH'
        if actual!=expected:mismatches.append({'file':name,'expected':expected,'actual':actual})
    return {'status':'PASS' if not mismatches else 'FAIL','checked':len(manifest),'mismatches':mismatches}


def certificate(relative, required, source_sha, *, cloud=False):
    f=REPORT/relative
    if not f.exists():return {'status':'HOLD','reason':'evidence not yet generated','evidence':relative}
    try: evidence=json.loads(f.read_text(encoding='utf-8'))
    except Exception:return {'status':'FAIL','reason':'evidence is not valid JSON','evidence':relative}
    if evidence.get('source_manifest_sha256')!=source_sha:
        return {'status':'HOLD','reason':'source package hash changed since evidence generation','evidence':relative}
    if cloud and evidence.get('target')!=URL+'/workbench/':
        return {'status':'HOLD','reason':'browser target is not the approved candidate service','evidence':relative}
    if not cloud and evidence.get('scope')!='ISOLATED_NEON_PG16_CANDIDATE_ONLY':
        return {'status':'HOLD','reason':'PG16 evidence not bound to isolated branch','evidence':relative}
    missing=[k for k in required if evidence.get('checks',{}).get(k,{}).get('status')!='PASS']
    if evidence.get('status')=='FAIL':return {'status':'FAIL','reason':'source-bound external gate failed','missing_or_failed':missing[:20],'evidence':relative}
    if evidence.get('status')!='PASS' or missing:
        return {'status':'HOLD','reason':'required live checks not all PASS','missing_or_failed':missing[:20],'evidence':relative}
    return {'status':'PASS','checks':len(required),'evidence':relative,
            'run_ids':evidence.get('run_ids',[]) if not cloud else [evidence.get('run_id')],
            'source_manifest_sha256':source_sha}


def frozen_branch_check(source_sha, pg_runs):
    f=REPORT/'frozen_rc2'/'RESULT.json'
    if not f.is_file():return {'status':'HOLD','reason':'Independent frozen RC2 branch-side read-only comparison not collected'}
    try:d=json.loads(f.read_text(encoding='utf-8'))
    except Exception:return {'status':'FAIL','reason':'Invalid frozen branch evidence JSON'}
    if (d.get('source_manifest_sha256')!=source_sha or d.get('branch_id')!='br-patient-surf-bb9nyu0h'
        or d.get('write_operations')!=0 or d.get('matched_runs')!=0
        or sorted(d.get('checked_run_ids',[]))!=sorted(pg_runs)):
        return {'status':'HOLD','reason':'Frozen RC2 branch evidence incomplete or not tied to new PG16 runs'}
    return {'status':'PASS','checked_runs':len(pg_runs),'source':'independent frozen branch read-only query'}


def main():
    REPORT.mkdir(exist_ok=True)
    result={'baseline':'RC3.4 enterprise candidate; Version A and RC2 immutable',
      'timestamp_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'checks':{}}
    result['checks']['source_manifest']=hashes()
    source_sha=hashlib.sha256((ROOT/'FINAL_SOURCE_SHA256.json').read_bytes()).hexdigest()
    result['checks']['python_pytest']=run_step('python_pytest',[sys.executable,'-m','pytest','-q','tests'])
    result['checks']['python_compile']=run_step('python_compile',[sys.executable,'-m','compileall','-q',
      'enterprise_workbench','preview_cloud','g3','g4','tests/enterprise_pg16_gate.py','tests/live_business_workflow_gate.py'])
    result['checks']['node_js_syntax']=run_step('node_js_syntax',['node','--check','enterprise_workbench/site/enterprise-console.js'])
    result['checks']['browser_mock']=run_step('browser_mock',[sys.executable,'tests/browser_enterprise_rc33.py'])
    result['checks']['cloud_ready']=http_read('/ready')
    result['checks']['cloud_health']=http_read('/health')
    result['checks']['isolated_pg16_readonly']=db_read()

    pg_required=['isolated_pg16_guard','pg16_and_schema','unauthenticated_401','invalid_token_401',
      'viewer_create_403','approver_create_403','planner_decision_403','operator_decision_403',
      'approver_worker_403','viewer_whatif_403','cross_tenant_run_404','cross_tenant_workflow_404',
      'cross_tenant_overview_404','cross_tenant_whatif_404','cross_tenant_command_404',
      'concurrent_decision_statuses','concurrent_approval_single_command','decision_replay_observed',
      'pg16_exactly_one_decision_and_outbox','worker_fault_observed','pg16_retry_without_premature_receipt',
      'worker_recovered_done','worker_pg16_retry_final_evidence','worker_internal_only_guard',
      'worker_error_and_success_audited','worker_duplicate_dispatch_no_reexecution',
      'pg16_skip_locked_single_claim','worker_parallel_one_receipt','operator_dispatch_authorized',
      'real_pg16_statement_timeout','new_pg16_connection_after_timeout',
      'whatif_http','whatif_pg16_all_run_tables_bytewise_stable',
      'a_b_live_independent_engine','a_b_snapshot_fingerprint_same','a_b_difference_explanations']
    for x in ['B','C','D']:
      pg_required+=['a_b_dynamic_scenario_'+x,'a_b_native_provenance_'+x,'a_b_policy_or_difference_'+x]
    pg=certificate('pg16_enterprise/RESULT.json',pg_required,source_sha)
    pg_evidence=json.loads((REPORT/'pg16_enterprise'/'RESULT.json').read_text(encoding='utf-8')) if pg['status']=='PASS' else {}
    for label,needed in {
      'tenant_auth_matrix':['unauthenticated_401','invalid_token_401','viewer_create_403','approver_create_403',
                            'planner_decision_403','operator_decision_403','approver_worker_403','viewer_whatif_403',
                            'cross_tenant_run_404','cross_tenant_workflow_404','cross_tenant_overview_404',
                            'cross_tenant_whatif_404','cross_tenant_command_404'],
      'idempotency_concurrency':['concurrent_decision_statuses','concurrent_approval_single_command',
                            'decision_replay_observed','pg16_exactly_one_decision_and_outbox',
                            'pg16_skip_locked_single_claim','worker_parallel_one_receipt'],
      'worker_fault_injection':['worker_fault_observed','pg16_retry_without_premature_receipt',
                            'worker_recovered_done','worker_pg16_retry_final_evidence',
                            'worker_error_and_success_audited','real_pg16_statement_timeout','new_pg16_connection_after_timeout'],
      'a_b_same_snapshot':['a_b_live_independent_engine','a_b_snapshot_fingerprint_same','a_b_difference_explanations']+
                           [y for x in ('B','C','D') for y in ('a_b_dynamic_scenario_'+x,'a_b_native_provenance_'+x,'a_b_policy_or_difference_'+x)],
      'what_if_side_effects':['whatif_http','whatif_pg16_all_run_tables_bytewise_stable','whatif_rejects_unknown_material'],
    }.items():
       result['checks'][label]=certificate('pg16_enterprise/RESULT.json',needed,source_sha)
    result['checks']['isolated_pg16_enterprise']=pg

    live_required=['page_http','brand_rc34','session_connected','mrp_created','reload_run_restored',
         'approval_enabled','approved_outbox','audit_page_rendered','backend_token_retrieval',
         'backend_overview_http','backend_approval','backend_worker_done','backend_receipt',
         'whatif_http','whatif_contract','whatif_recheck_http','whatif_persisted_state_unchanged',
         'dynamic_native_a_b_http','dynamic_a_b_independent','dynamic_a_b_explained',
         'second_guest_session','second_guest_token','cross_tenant_run_not_found',
         'unauthenticated_run_401','no_page_errors']
    result['checks']['live_incognito_browser']=certificate('live_business/RESULT.json',live_required,source_sha,cloud=True)
    result['checks']['frozen_rc2_protection']=frozen_branch_check(source_sha,pg_evidence.get('run_ids',[])) if pg['status']=='PASS' else {'status':'HOLD','reason':'New isolated PG16 Run IDs not yet available for frozen branch comparison'}
    statuses=[x['status'] for x in result['checks'].values()]
    result['final_release_gate']='PASS' if all(x=='PASS' for x in statuses) else 'FAIL' if 'FAIL' in statuses else 'HOLD'
    (REPORT/'FINAL_RELEASE_GATE_RESULT.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print('FINAL_RELEASE_GATE='+result['final_release_gate'])
    for name,v in result['checks'].items():print(name+'='+v['status'])
    print('EVIDENCE='+str(REPORT/'FINAL_RELEASE_GATE_RESULT.json'))
    return 0 if result['final_release_gate']=='PASS' else 2

if __name__=='__main__':raise SystemExit(main())
