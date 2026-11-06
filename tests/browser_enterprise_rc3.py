"""Version B RC3 UI interaction regression with deterministic mocked HTTP contracts.
Real PostgreSQL/cloud acceptance is a separate gate, never asserted by this test.
"""
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1]
SITE=ROOT/'enterprise_workbench/site'
OUT=ROOT/'evidence'
OUT.mkdir(exist_ok=True)


import os
from pathlib import Path as _Path

def launch_chromium(playwright):
    explicit = os.environ.get('V19B_CHROMIUM_EXECUTABLE', '').strip()
    if explicit:
        if not _Path(explicit).is_file():
            raise FileNotFoundError('V19B_CHROMIUM_EXECUTABLE is not a file: ' + explicit)
        return playwright.chromium.launch(headless=True, executable_path=explicit, args=['--no-sandbox'])
    try:
        return playwright.chromium.launch(headless=True, args=['--no-sandbox'])
    except Exception as exc:
        # Linux-only fallback for environments with system Chromium but no Playwright browser cache.
        fallback = _Path('/usr/bin/chromium')
        if os.name != 'nt' and fallback.is_file():
            return playwright.chromium.launch(headless=True, executable_path=str(fallback), args=['--no-sandbox'])
        raise RuntimeError(
            'Playwright Chromium not installed. Run: python -m playwright install chromium '
            'or set V19B_CHROMIUM_EXECUTABLE to the full browser executable path.'
        ) from exc

with sync_playwright() as p:
    browser=launch_chromium(p)
    page=browser.new_page(viewport={'width':1450,'height':990},device_scale_factor=1)
    errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
    html=(SITE/'index.html').read_text(encoding='utf-8').replace('<script src="./','<script data-skip-src="./')
    html=html.replace('<link rel="stylesheet" href="./style.css">','').replace('<link rel="stylesheet" href="./enterprise-console.css">','')
    # about:blank is used because automated network navigation is restricted in this runtime.
    page.set_content(html)
    for name in ['style.css','enterprise-console.css']:
        page.add_style_tag(content=(SITE/name).read_text(encoding='utf-8'))
    manufacturing=(SITE/'data/manufacturing.json').read_text(encoding='utf-8')
    mock=r'''async data=>{
      const stats={calls:[],state:'WAITING_REVIEW',command:'',decision:null,worker:'PENDING',receipt:null,events:[],runId:'MRP-1234567890abcdef'};
      window.__httpMock=stats;
      window.fetch=async (url,opts={})=>{
        const path=String(url),method=opts.method||'GET'; stats.calls.push([method,path]);
        const payload=opts.body?JSON.parse(opts.body):{};
        const out=(v,s=200)=>new Response(JSON.stringify(v),{status:s,headers:{'content-type':'application/json'}});
        const auth=opts.headers?.Authorization||'';
        if(path.includes('manufacturing.json'))return out(JSON.parse(data));
        if(path==='/ready')return out({status:'ready',database:'postgresql',scope:'preview_only'});
        if(path==='/api/v1/version-b/preview/session')return out({access_token:'mock-session-token',tenant:'guest-test1',expires_in:7200,role:'admin'});
        if(path.includes('/enterprise/')&&auth!=='Bearer mock-session-token')return out({detail:'AUTH_REQUIRED'},401);
        if(path.endsWith('/enterprise/me'))return out({tenant:'guest-test1',role:'admin',actor:'visitor'});
        const run={run_id:stats.runId,input_hash:'e'.repeat(64),rule_version:'MRP-V0.3',status:'COMPLETED',
          snapshot:{as_of:'2026-10-29'},lines:[{material:'BR-01',date:'2026-11-29',gross:'200',net:'80',planned:'80',closing:'0'},
          {material:'EM-100',date:'2026-11-30',gross:'100',net:'100',planned:'100',closing:'0'}],
          pegs:[{material:'BR-01',date:'2026-11-29',order_id:'SO-2026-001',gross:'200',from_stock:'120',from_receipts:'0',from_planned:'80'}]};
        const comm=()=>stats.command?{command_id:stats.command,run_id:stats.runId,decision:'APPROVED',actor:'visitor',status:stats.worker,attempts:stats.worker==='DONE'?1:0,receipt:stats.receipt,last_error:null,external_execution:false}:null;
        const overview=()=>({run_id:stats.runId,tenant:'guest-test1',source:'PERSISTED_POSTGRESQL',snapshot_hash:'e'.repeat(64),workflow:{state:stats.state,version:stats.state==='WAITING_REVIEW'?0:stats.state==='APPROVED_QUEUED'?1:2},plan:{line_count:2,peg_count:1},decision:stats.decision,command:comm(),events:stats.events,external_execution:false});
        if(path.endsWith('/enterprise/mrp/runs')&&method==='POST')return out({run_id:stats.runId,source:'postgresql',lines:2,pegs:1,simulation:false},201);
        if(path.endsWith('/enterprise/mrp/runs/'+stats.runId))return out({tenant:'guest-test1',run,canonical_snapshot:{as_of:'2026-10-29'},snapshot_hash:'e'.repeat(64),source:'postgresql'});
        // A second run in the same guest tenant: no decision/outbox/receipt yet.
        if(path.endsWith('/enterprise/mrp/runs/MRP-another-run'))return out({tenant:'guest-test1',run:{...run,run_id:'MRP-another-run'},canonical_snapshot:{as_of:'2026-10-29'},snapshot_hash:'e'.repeat(64),source:'postgresql'});
        if(path.endsWith('/enterprise/review/overview/MRP-another-run'))return out({...overview(),run_id:'MRP-another-run',workflow:{state:'WAITING_REVIEW',version:0},decision:null,command:null,events:[]});
        if(path.endsWith('/enterprise/review/overview/'+stats.runId))return out(overview());
        if(path.endsWith('/enterprise/workflows/'+stats.runId))return out({run_id:stats.runId,state:stats.state,version:1,events:stats.events});
        if(path.endsWith('/enterprise/decisions')&&method==='POST'){
          if(stats.state!=='WAITING_REVIEW')return out({detail:'WORKFLOW_NOT_REVIEWABLE'},409);
          stats.decision={type:payload.decision,reason:payload.reason,actor:'visitor',at:'2026-11-04T14:15:00Z'};
          stats.command='00000000-0000-4000-8000-000000000001';stats.state=payload.decision==='APPROVED'?'APPROVED_QUEUED':'REJECTED';
          stats.events.push({action:payload.decision,actor:'visitor',at:'2026-11-04T14:15:00Z',reference:stats.command});
          return out({command_id:stats.command,status:'ACCEPTED',execution_status:'PENDING',external_execution:false},202);
        }
        if(path.endsWith('/enterprise/worker/dispatch')&&method==='POST'){
          stats.worker='DONE';stats.state='EXECUTED_INTERNAL';stats.receipt={status:'VALIDATED_INTERNAL',checked_at:'2026-11-04T14:16:00Z',external_execution:false};
          stats.events.unshift({action:'WORKER_DONE',actor:'visitor',at:'2026-11-04T14:16:00Z',reference:stats.command});
          return out({processed:1,external_execution:false,execution_type:'INTERNAL_VALIDATION_ONLY'});
        }
        if(path.endsWith('/enterprise/commands/'+stats.command))return out(comm());
        if(path.endsWith('/enterprise/what-if'))return out({side_effect:'NONE',workflow_unchanged:true,baseline_snapshot_sha256:'e'.repeat(64),proposed:{stock:80}});
        if(path.includes('/enterprise/reconciliation'))return out({status:'MATCH',differences:[],source:'NATIVE_A_RC8_DYNAMIC_AND_B_PG16'},201);
        if(path.endsWith('/enterprise/mcp/tools/call'))return out({read_only:true,tool:'mrp.get_run',result:{run}});
        if(path.endsWith('/enterprise/mcp/rpc'))return out({jsonrpc:'2.0',id:1,result:{tools:[{name:'mrp.get_run'}]}});
        return out({detail:'MOCK_ROUTE_NOT_FOUND',path},404);
      };
    }'''
    page.evaluate("Object.defineProperty(window.crypto, 'randomUUID', {value: () => '00000000-0000-4000-8000-000000000555', configurable: true});")
    page.evaluate(mock,manufacturing)
    for asset in ['engine.js','decision.js','decision-evidence.js','decision-reasoning.js','closure.js','portable.js','app.js','onboarding.js','enterprise-console.js']:
        page.add_script_tag(content=(SITE/asset).read_text(encoding='utf-8'))
    page.wait_for_selector('#vbConsoleNav',timeout=12000)
    page.locator('#vbConsoleNav').click()
    assert page.locator('#vbConsole').is_visible()
    assert not page.locator('#body').is_visible()
    assert page.locator('.vbc-step').count()==5
    assert page.get_by_text('从 MRP 到执行回执').count()>=1
    page.screenshot(path=str(OUT/'RC3_01_enterprise_before.png'),full_page=True)
    print('01_NAVIGATION_AND_5_STAGES=PASS')
    page.locator('[data-action="connect"]').click()
    page.wait_for_function('document.querySelector("#vbConsole").textContent.includes("guest-test1")')
    assert page.locator('[data-action="create"]').is_enabled()
    assert "localStorage.setItem" not in (SITE/"enterprise-console.js").read_text(encoding="utf-8")
    print('02_SESSION_AND_ISOLATION=PASS')
    page.locator('[data-action="create"]').click()
    page.wait_for_function('document.querySelector("#vbConsole").textContent.includes("MRP-1234567890abcdef")')
    page.wait_for_function('document.querySelector("#vbConsole").textContent.includes("物料需求行")')
    assert page.locator('.vbc-table tbody tr').count()==2
    page.screenshot(path=str(OUT/'RC3_02_mrp_details.png'),full_page=True)
    print('03_MRP_CREATE_AND_READ_PG_CONTRACT=PASS')
    page.locator('[data-action="line-kind"][data-value="pegging"]').click()
    assert page.get_by_text('SO-2026-001').count()>=1
    print('04_PEGGING_TABLE=PASS')
    page.locator('[data-view="approval"]').first.click()
    assert page.get_by_text('审批中心').count()>=1
    assert page.locator('[data-action="approve"]').is_enabled()
    page.screenshot(path=str(OUT/'RC3_03_approval_before.png'),full_page=True)
    page.locator('[data-action="approve"]').click()
    page.wait_for_function('document.querySelector("#vbConsole").textContent.includes("APPROVED_QUEUED")')
    assert page.locator('[data-action="dispatch"]').is_enabled()
    assert page.locator('[data-action="approve"]').count()==0 or page.locator('[data-action="approve"]').is_disabled()
    print('05_APPROVAL_PERSISTENCE_AND_STATE=PASS')
    page.screenshot(path=str(OUT/'RC3_04_execution_pending.png'),full_page=True)
    page.locator('[data-action="dispatch"]').click()
    page.wait_for_function('document.querySelector("#vbConsole").textContent.includes("EXECUTED_INTERNAL")')
    page.wait_for_function('document.querySelector("#vbConsole").textContent.includes("DONE")')
    page.screenshot(path=str(OUT/'RC3_05_execution_done.png'),full_page=True)
    print('06_WORKER_DONE_AND_STATE_REFRESH=PASS')
    page.locator('[data-view="receipt"]').first.click()
    page.wait_for_function('document.querySelector("#vbConsole").textContent.includes("VALIDATED_INTERNAL")')
    page.locator('[data-action="receipt"]').click()
    page.wait_for_function('document.querySelector("#vbConsole").textContent.includes("回执已")')
    page.screenshot(path=str(OUT/'RC3_06_receipt.png'),full_page=True)
    print('07_REAL_RECEIPT_CONTRACT=PASS')
    page.locator('[data-view="audit"]').first.click()
    assert page.locator('.vbc-event').count()==2
    assert page.get_by_text('WORKER_DONE').count()>=1
    page.screenshot(path=str(OUT/'RC3_07_audit.png'),full_page=True)
    print('08_AUDIT_TIMELINE=PASS')
    page.locator('[data-view="mrp"]').first.click()
    page.locator('#vbAdvanced summary').click()
    page.locator('[data-action="whatif"]').click()
    page.wait_for_function('document.querySelector("#vbConsole").textContent.includes("隔离 What-if 已计算")')
    print('09_ADVANCED_WHATIF_NO_SIDE_EFFECT=PASS')
    page.locator('[data-tab="orders"]').click()
    assert not page.locator('#vbConsole').is_visible()
    assert page.locator('#body').is_visible()
    print('10_STATIC_A_WORKBENCH_PRESERVED=PASS')
    # Responsive viewport, the 5-step track must fit by horizontal scrolling.
    page.set_viewport_size({'width':390,'height':844})
    page.locator('#sidebarToggle').click()
    page.locator('#vbConsoleNav').click()
    assert page.locator('#vbConsole').is_visible()
    assert page.locator('.vbc-stepper').evaluate('(e)=>e.scrollWidth>=e.clientWidth')
    page.screenshot(path=str(OUT/'RC3_08_mobile.png'),full_page=True)
    print('11_MOBILE_NAV_AND_STEP_SCROLL=PASS')
    assert not errors,errors
    print('12_PAGE_ERRORS_ZERO=PASS')
    # API requests to approval/worker/receipt and readiness are genuinely exercised through mock fetch.
    calls=page.evaluate('window.__httpMock.calls')
    paths=[v[1] for v in calls]
    assert any('/preview/session' in x for x in paths)
    assert any('/mrp/runs' in x for x in paths)
    assert any('/decisions' in x for x in paths)
    assert any('/worker/dispatch' in x for x in paths)
    assert any('/commands/' in x for x in paths)
    assert any('/review/overview/' in x for x in paths)
    print('13_ALL_RC2_ENDPOINTS_EXERCISED=PASS')
    # Follow-up regression: switching runs must not show a prior run's receipt.
    page.locator('[data-view="mrp"]').first.click()
    page.locator('[data-bind="runInput"]').fill('MRP-another-run')
    page.locator('[data-action="lookup"]').click()
    page.wait_for_function('document.querySelector("#vbConsole").textContent.includes("已从 PostgreSQL 载入")')
    page.locator('[data-view="execution"]').first.click()
    page.locator('[data-action="refresh"]').click()
    page.wait_for_function('document.querySelector("#vbConsole").textContent.includes("已从 PostgreSQL 更新")')
    assert page.locator('[data-action="dispatch"]').is_disabled()
    assert page.get_by_text('无命令').count()>=1
    page.locator('[data-view="receipt"]').first.click()
    assert page.get_by_text('当前没有执行命令').count()>=1
    assert page.locator('[data-action="receipt"]').count()==0
    print('14_SWITCH_RUN_DOES_NOT_LEAK_PREVIOUS_RECEIPT=PASS')
    (OUT/'RC3_BROWSER_MOCK_CALLS.json').write_text(json.dumps(page.evaluate('window.__httpMock.calls'),ensure_ascii=False,indent=2),encoding='utf-8')
    browser.close()

