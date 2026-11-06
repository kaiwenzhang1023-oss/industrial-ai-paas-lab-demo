"""Live candidate-only business workflow evidence. Writes only to isolated guest tenant.
No fault injection, no frozen branch access, no external ERP/MES/SRM commands.
"""
import json, os, pathlib, sys, time, traceback, uuid, hashlib, datetime
from playwright.sync_api import sync_playwright
ROOT=pathlib.Path(__file__).resolve().parents[1]
OUT=ROOT/'release_evidence'/'live_business'
OUT.mkdir(parents=True,exist_ok=True)
URL=os.getenv('V19B_RC34_LIVE_URL','https://industrial-ai-paas-v19b-ux-rc31-candidate.onrender.com/workbench/')
BASE=URL.split('/workbench')[0]
API=BASE+'/api/v1/version-b/enterprise'
result={'target':URL,'scope':'isolated guest tenant, real Render/PG16, INTERNAL_VALIDATION_ONLY',
        'checks':{},'page_errors':[],'failed_requests':[],'run_id':None,'command_id':None,'status':'HOLD',
        'timestamp_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'source_manifest_sha256':hashlib.sha256((ROOT/'FINAL_SOURCE_SHA256.json').read_bytes()).hexdigest()}
def mark(name,ok,detail=None):
 result['checks'][name]={'status':'PASS' if ok else 'FAIL',**({'detail':str(detail)[:250]} if detail is not None else {})}
 if not ok: raise AssertionError(name+': '+str(detail))
def save():
 (OUT/'RESULT.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
def api(context,method,path,body=None,token=None):
 headers={'Authorization':'Bearer '+token} if token else {}
 r=context.request.fetch(API+path,method=method,headers=headers,data=body,timeout=60000)
 try: data=r.json()
 except: data={}
 return r.status,data
try:
 with sync_playwright() as p:
  opts={'headless':True}
  if os.getenv('V19B_CHROMIUM_EXECUTABLE'):opts['executable_path']=os.environ['V19B_CHROMIUM_EXECUTABLE']
  browser=p.chromium.launch(**opts)
  ctx=browser.new_context(viewport={'width':1440,'height':900})
  page=ctx.new_page()
  page.on('pageerror',lambda e:result['page_errors'].append(str(e)))
  page.on('requestfailed',lambda r:result['failed_requests'].append(r.url.split('?')[0]))
  response=page.goto(URL,wait_until='domcontentloaded',timeout=90000)
  page.wait_for_selector('#vbConsole',timeout=30000)
  mark('page_http',response is not None and response.status==200)
  mark('brand_rc34',page.locator('.brand small').inner_text().strip().endswith('RC3.4'),
       'Candidate must be deployed at exact updated commit; do not mark PASS against old RC3.4')
  page.locator('button[data-action="connect"]').click()
  page.wait_for_selector('button[data-action="create"]:not([disabled])',timeout=45000)
  mark('session_connected',True)
  page.locator('button[data-action="create"]').click()
  page.wait_for_selector('input[data-bind="runInput"]',timeout=45000)
  page.wait_for_function("() => {const x=document.querySelector('input[data-bind=runInput]');return x && /^MRP-[a-f0-9]+$/i.test(x.value)}",timeout=60000)
  run_id=page.locator('input[data-bind="runInput"]').input_value()
  result['run_id']=run_id
  mark('mrp_created',run_id.startswith('MRP-'))
  page.screenshot(path=str(OUT/'01_mrp.png'),full_page=True)
  page.reload(wait_until='domcontentloaded')
  page.wait_for_selector('#vbConsole',timeout=30000)
  page.wait_for_function("id => document.querySelector('input[data-bind=runInput]')?.value===id",arg=run_id,timeout=45000)
  mark('reload_run_restored',True)
  page.locator('button[data-action="nav"][data-view="approval"]').click()
  page.locator('button[data-action="approve"]').wait_for(state='visible')
  mark('approval_enabled',page.locator('button[data-action="approve"]').is_enabled())
  page.locator('button[data-action="approve"]').click()
  page.wait_for_selector('button[data-action="dispatch"]:not([disabled])',timeout=45000)
  mark('approved_outbox',True)
  page.screenshot(path=str(OUT/'02_approval.png'),full_page=True)
  page.locator('button[data-action="dispatch"]').click()
  page.wait_for_timeout(1500)
  page.locator('button[data-action="refresh"]').click()
  page.wait_for_timeout(1000)
  page.locator('button[data-action="nav"][data-view="receipt"]').click()
  page.screenshot(path=str(OUT/'03_receipt.png'),full_page=True)
  page.locator('button[data-action="nav"][data-view="audit"]').click()
  page.screenshot(path=str(OUT/'04_audit.png'),full_page=True)
  mark('audit_page_rendered',page.locator('#vbConsole').count()==1)
  # Independently check persisted backend state using the token held only in sessionStorage.
  auth=page.evaluate("""() => {
    const k=Object.keys(sessionStorage).find(k=>k.includes('v19b')&&k.includes('session'));
    return k?JSON.parse(sessionStorage.getItem(k)).token:null;
  }""")
  # If the key changes, prefer explicitly refusing to claim backend validation.
  mark('backend_token_retrieval',bool(auth),'Session key not identified; no token exported')
  if auth:
   code,overview=api(ctx,'GET','/review/overview/'+run_id,token=auth)
   mark('backend_overview_http',code==200,code)
   result['backend_workflow']=overview.get('workflow',{})
   result['backend_decision']=overview.get('decision',{})
   result['backend_command']=overview.get('command',{})
   mark('backend_approval',overview.get('decision',{}).get('type')=='APPROVED')
   cmd=overview.get('command') or {}
   mark('backend_worker_done',cmd.get('status')=='DONE',cmd.get('status'))
   mark('backend_receipt',isinstance(cmd.get('receipt'),dict))
   # Persisted state before/after a read-only What-if computation.
   before=(overview.get('snapshot_hash'),overview.get('workflow'),overview.get('decision'),cmd.get('status'),len(overview.get('events',[])))
   wf_status,wf=api(ctx,'POST','/what-if',body={'run_id':run_id,'kind':'stock','target':'BR-01','quantity':80},token=auth)
   mark('whatif_http',wf_status==200,wf_status)
   mark('whatif_contract',wf.get('side_effect')=='NONE' and wf.get('workflow_unchanged') is True)
   code,after=api(ctx,'GET','/review/overview/'+run_id,token=auth)
   mark('whatif_recheck_http',code==200,code)
   after_command=after.get('command') or {}
   after_values=(after.get('snapshot_hash'),after.get('workflow'),after.get('decision'),after_command.get('status'),len(after.get('events',[])))
   mark('whatif_persisted_state_unchanged',before==after_values)
   # This is persisted B versus an independently executed frozen native A engine.
   rc_status,comp=api(ctx,'POST','/reconciliation/dynamic',body={'run_id':run_id,'idempotency_key':uuid.uuid4().hex},token=auth)
   mark('dynamic_native_a_b_http',rc_status==201,rc_status)
   mark('dynamic_a_b_independent',comp.get('independent_a_execution_this_request') is True and comp.get('a_input_hash')==comp.get('b_input_hash'))
   mark('dynamic_a_b_explained',comp.get('status') in ('MATCH','DIFFERENT') and isinstance(comp.get('differences'),list) and all('reason' in x for x in comp['differences']))

   # Distinct guest tenant should not be able to access this run.
   other=ctx.request.post(BASE+'/api/v1/version-b/preview/session',timeout=30000)
   mark('second_guest_session',other.status==200)
   second=other.json().get('access_token','')
   mark('second_guest_token',bool(second))
   other_status,_=api(ctx,'GET','/mrp/runs/'+run_id,token=second)
   mark('cross_tenant_run_not_found',other_status==404,other_status)
   missing_status,_=api(ctx,'GET','/mrp/runs/'+run_id)
   mark('unauthenticated_run_401',missing_status==401,missing_status)
   # This gate does not perform destructive database fault injection or compare frozen A.
  mark('no_page_errors',not result['page_errors'],len(result['page_errors']))
  ctx.close();browser.close()
 result['status']='PASS' if all(c['status']=='PASS' for c in result['checks'].values()) else 'HOLD'
except Exception as exc:
 result['status']='FAIL'
 result['error']=type(exc).__name__+': '+str(exc)[:500]
 result['traceback_tail']=traceback.format_exc()[-1800:]
finally:
 save()
 print('LIVE_BUSINESS_GATE='+result['status'])
 for k,v in result['checks'].items():print(k+'='+v['status'])
 print('EVIDENCE='+str(OUT/'RESULT.json'))
 sys.exit(0 if result['status']=='PASS' else 2)
