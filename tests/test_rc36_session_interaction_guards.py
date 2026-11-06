"""Source-level safety invariants; not a substitute for browser E2E."""
from pathlib import Path

SOURCE=(Path(__file__).resolve().parents[1]/'enterprise_workbench/site/enterprise-console.js').read_text(encoding='utf-8')


def test_session_epoch_invalidates_stale_responses():
    assert 'let sessionEpoch=0' in SOURCE
    assert 'sessionEpoch++;forgetTabSession()' in SOURCE
    assert 'requestEpoch!==sessionEpoch' in SOURCE
    assert "requestTenant!==(state.session?.tenant||null)" in SOURCE


def test_expired_session_is_not_restored():
    assert 'Number.isFinite(saved.expiresAt)&&saved.expiresAt>Date.now()' in SOURCE
    assert "who.tenant!==saved.tenant" in SOURCE
    assert "if(res.status===401){clearSession();}" in SOURCE


def test_line_sort_whitelists_backend_columns():
    assert "['material','date','order_id','gross','from_stock']" in SOURCE
    assert "['material','date','gross','net','planned']" in SOURCE
    assert 'if(!allowed.includes(el.dataset.value))return' in SOURCE


def test_page_bounds_and_selection_reset():
    assert 'Math.min(last,state.linePage+' in SOURCE
    assert 'state.linePage=1;state.lineSelected=null;' in SOURCE
    assert 'visibleRows().some(r=>r.__index===index)' in SOURCE


def test_busy_guard_prevents_repeated_button_actions():
    assert 'if(!btn||btn.disabled||state.busy)return' in SOURCE
    assert 'async function perform(action,handler){if(state.busy)return;' in SOURCE
