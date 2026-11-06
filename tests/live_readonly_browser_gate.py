"""Independent, non-mutating Chromium check against deployed RC3.4 Render candidate.
No login, POST, approval, or worker dispatch. Never claims full workflow PASS.
"""
import json, os, pathlib, sys, traceback
from playwright.sync_api import sync_playwright
ROOT=pathlib.Path(__file__).resolve().parents[1]
OUT=ROOT/'release_evidence'/'live_readonly'
OUT.mkdir(parents=True,exist_ok=True)
URL=os.environ.get('V19B_RC34_LIVE_URL','https://industrial-ai-paas-v19b-ux-rc31-candidate.onrender.com/workbench/')
result={'url':URL,'scope':'read-only public page, no login or business mutations','checks':{},'page_errors':[],'failed_requests':[]}
def write(): (OUT/'RESULT.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
try:
 with sync_playwright() as p:
  kw={'headless':True}
  if os.environ.get('V19B_CHROMIUM_EXECUTABLE'):kw['executable_path']=os.environ['V19B_CHROMIUM_EXECUTABLE']
  browser=p.chromium.launch(**kw)
  for label,viewport in [('desktop',{'width':1440,'height':900}),('mobile',{'width':390,'height':844})]:
   context=browser.new_context(viewport=viewport,device_scale_factor=1,ignore_https_errors=False)
   page=context.new_page()
   page.on('pageerror',lambda e:result['page_errors'].append(str(e)))
   page.on('requestfailed',lambda r:result['failed_requests'].append({'url':r.url.split('?')[0],'failure':r.failure}))
   response=page.goto(URL,wait_until='domcontentloaded',timeout=90000)
   page.wait_for_timeout(1600)
   result['checks'][label+'_http']={'status':'PASS' if response and response.status==200 else 'FAIL','code':response.status if response else None}
   for selector in ['#vbConsoleNav','#vbConsole']:
    result['checks'][label+'_'+selector]={'status':'PASS' if page.locator(selector).count()>0 else 'FAIL'}
   page.screenshot(path=str(OUT/(label+'.png')),full_page=True)
   result['checks'][label+'_screenshot']={'status':'PASS','file':label+'.png'}
   context.close()
  browser.close()
 result['checks']['page_errors']={'status':'PASS' if not result['page_errors'] else 'FAIL','count':len(result['page_errors'])}
 result['status']='PASS' if all(v['status']=='PASS' for v in result['checks'].values()) else 'FAIL'
except Exception as exc:
 result['status']='HOLD'
 result['reason']=type(exc).__name__+': '+str(exc)[:450]
 result['traceback_tail']=traceback.format_exc()[-900:]
write()
print('LIVE_READONLY_BROWSER='+result['status'])
for k,v in result['checks'].items():print(k+'='+v['status'])
sys.exit(0 if result['status']=='PASS' else 2)
