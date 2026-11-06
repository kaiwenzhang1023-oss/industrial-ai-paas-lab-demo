"""Isolated Version B UX RC3.1 LIVE cloud acceptance.

Requires a separately deployed candidate (NOT the frozen Version B preview URL).
Python 3.14; stdlib only. No credential values are logged or written.
All mutations are limited to anonymous throwaway guest tenants on the specified candidate API.

Usage:
  python RUN_V19B_UX_RC31_LIVE_E2E.py --base-url https://YOUR-INDEPENDENT-CANDIDATE.onrender.com
"""
import argparse
import json
import ssl
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse, quote

ROOT=Path(__file__).resolve().parent
OUTPUT=ROOT/'UX_RC31_LIVE_E2E_EVIDENCE.json'
API='/api/v1/version-b/enterprise'
FROZEN_HOST='industrial-ai-paas-v19-version-b-preview.onrender.com'

class GateFailure(RuntimeError):pass

def request(host, path, method='GET', token=None, data=None, expected=(200,)):
    headers={'Accept':'application/json','User-Agent':'V19B-UX-RC31-IsolatedGate/1.0'}
    if token:headers['Authorization']='Bearer '+token
    if data is not None:headers['Content-Type']='application/json'
    body=json.dumps(data).encode() if data is not None else None
    req=urllib.request.Request(host+path,body,headers=headers,method=method)
    try:
        with urllib.request.urlopen(req,timeout=35,context=ssl.create_default_context()) as resp:
            status=resp.status
            payload=json.load(resp)
    except urllib.error.HTTPError as e:
        status=e.code
        payload=json.loads(e.read().decode('utf-8'))
    except Exception as e:
        raise GateFailure('NETWORK_OR_TIMEOUT: '+str(e)+'; if a POST timed out, inspect DB before any retry') from e
    if status not in expected:raise GateFailure(f'HTTP {status} not in {expected}: {path}: {str(payload)[:300]}')
    return payload

def check(x,desc):
    if not x:raise GateFailure(desc)

def run(host):
    report={'gate':'V19B_UX_RC31_LIVE_E2E','at_utc':datetime.now(timezone.utc).isoformat(),
            'candidate_host':host,'checks':[], 'external_writes':False,'status':'HOLD'}
    def done(name):report['checks'].append({'check':name,'status':'PASS'});print('PASS',name)
    def route(path):return API+path
    try:
        ready=request(host,'/ready');check(ready.get('status')=='ready' and ready.get('database')=='postgresql','READY_PG16_FAILED');done('READY_POSTGRESQL')
        cap=request(host,'/api/v1/version-b/capabilities');check(cap.get('production_ready') is False,'PRODUCTION_STATUS_GUARD');done('NON_PRODUCTION_CAPABILITIES')
        one=request(host,'/api/v1/version-b/preview/session',method='POST'); token=one.get('access_token');check(token and one.get('tenant'),'GUEST_SESSION_MISSING')
        who=request(host,route('/me'),token=token);check(who.get('tenant')==one['tenant'] and who.get('role')=='admin','TENANT_IDENTITY_MISMATCH');done('GUEST_SESSION_TENANT')
        created=request(host,route('/mrp/runs'),method='POST',token=token,expected=(201,));run_id=created.get('run_id')
        check(run_id and created.get('source')=='postgresql' and created.get('simulation') is False,'MRP_CREATE_CONTRACT')
        report['run_id']=run_id
        detail=request(host,route('/mrp/runs/'+quote(run_id,safe='')),token=token)
        check(detail.get('source')=='postgresql' and detail.get('run',{}).get('run_id')==run_id and isinstance(detail.get('run',{}).get('lines'),list),'MRP_PERSISTENCE_READ')
        before=request(host,route('/review/overview/'+quote(run_id,safe='')),token=token)
        check(before.get('workflow',{}).get('state')=='WAITING_REVIEW' and before.get('source')=='PERSISTED_POSTGRESQL','INITIAL_WORKFLOW')
        done('MRP_CREATE_READ_AND_WAITING_REVIEW')
        decision=request(host,route('/decisions'),method='POST',token=token,expected=(202,),data={
            'run_id':run_id,'decision':'APPROVED','reason':'UX RC3.1 candidate isolated live acceptance','idempotency_key':str(uuid.uuid4())})
        cmdid=decision.get('command_id');check(cmdid and decision.get('status')=='ACCEPTED' and decision.get('external_execution') is False,'APPROVAL_ACCEPTANCE')
        report['command_id']=cmdid
        queued=request(host,route('/review/overview/'+quote(run_id,safe='')),token=token)
        check(queued.get('workflow',{}).get('state')=='APPROVED_QUEUED' and queued.get('command',{}).get('command_id')==cmdid,'APPROVED_QUEUE_NOT_PERSISTED')
        done('APPROVAL_AND_OUTBOX_QUEUED')
        dispatched=request(host,route('/worker/dispatch'),method='POST',token=token)
        check(dispatched.get('external_execution') is False and dispatched.get('execution_type')=='INTERNAL_VALIDATION_ONLY','WORKER_CONTRACT')
        rec=request(host,route('/commands/'+quote(cmdid,safe='')),token=token)
        after=request(host,route('/review/overview/'+quote(run_id,safe='')),token=token)
        check(rec.get('run_id')==run_id and rec.get('command_id')==cmdid and rec.get('status')=='DONE' and rec.get('receipt'),'PERSISTENT_RECEIPT_MISSING')
        check(after.get('workflow',{}).get('state')=='EXECUTED_INTERNAL' and after.get('external_execution') is False,'WORKFLOW_NOT_INTERNAL_EXECUTED')
        check(any(e.get('action')=='APPROVED' for e in after.get('events',[])) and any(e.get('action')=='WORKER_EXECUTED_INTERNAL' for e in after.get('events',[])),'AUDIT_TRAIL_INCOMPLETE')
        done('WORKER_DONE_RECEIPT_AND_AUDIT')
        other=request(host,'/api/v1/version-b/preview/session',method='POST');other_token=other.get('access_token')
        check(other_token and other.get('tenant')!=one['tenant'],'TENANT_REUSED')
        request(host,route('/mrp/runs/'+quote(run_id,safe='')),token=other_token,expected=(404,))
        request(host,route('/commands/'+quote(cmdid,safe='')),token=other_token,expected=(404,))
        request(host,route('/mrp/runs/'+quote(run_id,safe='')),expected=(401,))
        done('TENANT_ISOLATION_AND_AUTH')
        request(host,route('/decisions'),method='POST',token=token,data={
            'run_id':run_id,'decision':'APPROVED','reason':'Should be rejected duplicate','idempotency_key':str(uuid.uuid4())},expected=(409,))
        done('DUPLICATE_DECISION_REJECTED')
        rejected_run=request(host,route('/mrp/runs'),method='POST',token=token,expected=(201,)).get('run_id')
        check(rejected_run,'REJECT_TEST_MRP_MISSING')
        request(host,route('/decisions'),method='POST',token=token,expected=(202,),data={
            'run_id':rejected_run,'decision':'REJECTED','reason':'RC3.1 rejection-path validation','idempotency_key':str(uuid.uuid4())})
        rr=request(host,route('/review/overview/'+quote(rejected_run,safe='')),token=token)
        check(rr.get('workflow',{}).get('state')=='REJECTED' and rr.get('decision',{}).get('type')=='REJECTED','REJECTION_NOT_PERSISTED')
        done('REJECTION_PATH')
        report['status']='PASS'
    except Exception as e:
        report['status']='HOLD'
        report['error']=str(e)
        print('HOLD',str(e))
    OUTPUT.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print('EVIDENCE',str(OUTPUT))
    print('UX_RC31_LIVE_GATE='+report['status'])
    return 0 if report['status']=='PASS' else 2

if __name__=='__main__':
    ap=argparse.ArgumentParser()
    ap.add_argument('--base-url',required=True)
    opts=ap.parse_args()
    host=opts.base_url.rstrip('/')
    u=urlparse(host)
    if u.scheme!='https' or not u.hostname or u.username or u.password or u.query or u.fragment or u.path not in ('','/') or not u.hostname.endswith('.onrender.com') or u.hostname==FROZEN_HOST:
        raise SystemExit('HOLD_USE_INDEPENDENT_HTTPS_RENDER_CANDIDATE_ONLY')
    raise SystemExit(run(host))
