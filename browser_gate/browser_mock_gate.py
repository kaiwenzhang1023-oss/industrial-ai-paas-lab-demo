"""Real Chromium Workbench controls with deterministic mocked API (NOT PG16 E2E)."""
from pathlib import Path
import pytest
from playwright.sync_api import sync_playwright, expect

SITE=Path(__file__).resolve().parents[1]/'enterprise_workbench/site'

@pytest.fixture
def page():
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True, **({'executable_path':'/usr/bin/chromium','args':['--no-sandbox']} if __import__('sys').platform.startswith('linux') else {}))
        ctx=browser.new_context(accept_downloads=True)
        pg=ctx.new_page()
        def respond(route):
            from urllib.parse import urlsplit
            pathname=urlsplit(route.request.url).path
            path=pathname.removeprefix('/api/v1/version-b/enterprise') if pathname.startswith('/api/v1/version-b/enterprise/') else pathname
            if path=='/ready':body={'status':'ready','database':'postgresql'}
            elif path=='/api/v1/version-b/preview/session':body={'access_token':'test-token','tenant':'guest-'+'a'*32,'expires_in':3600}
            elif path=='/me':body={'tenant':'guest-'+'a'*32,'role':'guest'}
            elif path=='/mrp/runs' and route.request.method=='POST':body={'run_id':'MRP-TEST','source':'postgresql'}
            elif path.startswith('/mrp/runs/'):
                body={'source':'postgresql','run':{'lines':[{'material':f'M-{i:02d}','date':'2026-11-20','gross':i+1,'net':i+1,'planned':i+2} for i in range(19)],'pegs':[{'material':'M-00','date':'2026-11-20','order_id':'SO-1','gross':1,'from_stock':0}],'input_hash':'same-hash','snapshot':{'as_of':'2026-11-06'}},'canonical_snapshot':{'items':{},'orders':[]}}
            elif path.startswith('/review/overview/'):
                body={'source':'PERSISTED_POSTGRESQL','run_id':'MRP-TEST','workflow':{'state':'WAITING_REVIEW'},'snapshot_hash':'same-hash','command':None,'decision':None}
            elif path.startswith('/planning/time-buckets/'):
                body={'rows':[],'supply_explanations':[],'granularity':'week'}
            else:body={'detail':'MOCK_ROUTE_UNHANDLED:'+path}
            route.fulfill(status=200,content_type='application/json',body=__import__('json').dumps(body))
        def all_routes(route):
            from urllib.parse import urlsplit
            path=urlsplit(route.request.url).path
            if path.startswith('/api/') or path=='/ready':return respond(route)
            f=(SITE/path.lstrip('/')).resolve()
            if f.is_file() and f.is_relative_to(SITE):return route.fulfill(path=str(f))
            return route.fulfill(status=404)
        pg.route('**/*',all_routes)
        pg.goto('https://rc36.test/index.html')
        pg.evaluate("document.dispatchEvent(new Event('rc35:enterprise-mode'))")
        pg.locator('#vbConsole [data-action="connect"]').first.wait_for(state='visible')
        expect(pg.locator('#vbConsole [data-action="connect"]').first).to_be_enabled(timeout=8000)
        yield pg
        ctx.close();browser.close()

def connect_guest(page):
    """Wait for asynchronous /ready + render to settle; never force-click disabled UI."""
    button=page.locator('#vbConsole [data-action="connect"]').first
    try:
        expect(button).to_be_enabled(timeout=8000)
        button.click(timeout=5000)
        expect(page.locator('#vbConsole [data-action="logout"]').first).to_be_visible(timeout=8000)
    except Exception as exc:
        evidence={
            'connect_buttons':page.locator('#vbConsole [data-action="connect"]').count(),
            'status':page.locator('#vbConsole').inner_text()[:1000],
            'button_disabled':button.is_disabled() if button.count() else None,
        }
        raise AssertionError(f'GUEST_CONNECT_PRECONDITION_FAILED: {evidence}') from exc


def test_switch_modes_and_connect(page):
    assert page.locator('#vbConsole').is_visible()
    connect_guest(page)
    page.get_by_text('已连接独立演示租户').first.wait_for(timeout=10000)
    page.locator('#vbConsole [data-action="mode-local"]').click()
    assert page.locator('#vbConsole').is_hidden()
    page.evaluate("document.dispatchEvent(new Event('rc35:enterprise-mode'))")
    assert page.locator('#vbConsole').is_visible()

def test_table_search_sort_page_selection_export(page):
    connect_guest(page)
    page.locator('#vbConsole [data-action="create"]').first.click()
    page.locator('.vbc-material-explorer tr[data-line-index]').first.wait_for(timeout=10000)
    page.locator('.vbc-material-explorer [data-action="page-next"]').click()
    assert '第 2 / 2 页' in page.locator('.vbc-material-explorer').inner_text()
    page.locator('.vbc-material-explorer [data-action="line-sort"][data-value="material"]').click()
    assert '第 1 / 2 页' in page.locator('.vbc-material-explorer').inner_text()
    page.locator('.vbc-material-explorer tr[data-line-index]').first.click()
    assert '当前选中' in page.locator('.vbc-material-explorer').inner_text()
    page.locator('#vbSearch').fill('M-18')
    assert '筛选后 1 条' in page.locator('.vbc-material-explorer').inner_text()
    assert '当前选中' not in page.locator('.vbc-material-explorer').inner_text()
    with page.expect_download() as info:
        page.locator('.vbc-material-explorer details.vbc-more summary').click()
        page.locator('.vbc-material-explorer [data-action="line-export"]').click()
    assert info.value.suggested_filename

# Business journey uses a deterministic API double; passing it never certifies PostgreSQL.
def test_four_stage_approval_receipt_and_reload(page):
    """Validate the *rendered* business-first four-card workflow, not retired stepper selectors.

    The mocked backend has no review/worker mutation contract, so this is an
    entry-state and refresh gate, not evidence of completed approval/receipt.
    """
    connect_guest(page)
    page.locator('#vbConsole [data-action="create"]').first.click()
    expect(page.locator('.vbc-material-explorer tr[data-line-index]').first).to_be_visible(timeout=10000)
    cards=page.locator('#vbConsole .vbc-business-actions .vbc-business-card')
    expect(cards).to_have_count(4)
    for heading in ['01 · 计划单操作', '02 · 人工审批', '03 · 执行与回执', '04 · 审计查询']:
        expect(cards.filter(has_text=heading)).to_have_count(1)
    approval=cards.filter(has_text='02 · 人工审批')
    expect(approval.locator('[data-action="approve"]')).to_be_enabled()
    execution=cards.filter(has_text='03 · 执行与回执')
    expect(execution.locator('[data-action="dispatch"]')).to_be_disabled()
    expect(page.locator('#vbConsole .vbc-business-results').get_by_text('尚未生成回执')).to_be_visible()
    page.reload()
    page.evaluate("document.dispatchEvent(new Event('rc35:enterprise-mode'))")
    expect(page.locator('#vbConsole')).to_be_visible()
    # Session restoration must not be mistaken for a completed workflow.
    expect(page.locator('#vbConsole .vbc-business-actions .vbc-business-card')).to_have_count(4)


def test_table_numeric_sort_direction_and_zero_units(page):
    connect_guest(page)
    page.locator('#vbConsole [data-action="create"]').first.click()
    table=page.locator('.vbc-material-explorer')
    table.locator('[data-action="line-sort"][data-value="gross"]').click()
    assert '1' in table.locator('tbody tr').first.inner_text()
    table.locator('[data-action="line-sort"][data-value="gross"]').click()
    assert '19' in table.locator('tbody tr').first.inner_text()
    table.locator('tr[data-line-index]').first.click()
    assert '当前选中' in table.inner_text()
    table.locator('[data-action="line-kind"][data-value="pegging"]').click()
    assert '当前选中' not in table.inner_text()
