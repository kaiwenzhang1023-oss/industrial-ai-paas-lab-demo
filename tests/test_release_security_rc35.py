"""Security contract tests: local unit coverage, not live multi-tenant PG16 evidence."""
import json
import pytest
from fastapi import HTTPException
from enterprise_workbench.rc2 import identity, require, Identity, fingerprint

def test_auth_fails_closed_without_identity_configuration(monkeypatch):
    monkeypatch.delenv('VERSION_B_RC2_IDENTITIES_JSON',raising=False)
    with pytest.raises(HTTPException) as e:identity('Bearer random-token')
    assert e.value.status_code==503

def test_invalid_and_tenant_scoped_identity(monkeypatch):
    monkeypatch.setenv('VERSION_B_RC2_IDENTITIES_JSON',json.dumps([
        {'token':'tenantA-secure-token','actor':'a','tenant':'tenant-A','role':'viewer'},
        {'token':'tenantB-secure-token','actor':'b','tenant':'tenant-B','role':'planner'}]))
    with pytest.raises(HTTPException) as e:identity('Bearer not-the-token')
    assert e.value.status_code==401
    a=identity('Bearer tenantA-secure-token')
    b=identity('Bearer tenantB-secure-token')
    assert a.tenant!=b.tenant
    assert a.role=='viewer'
    with pytest.raises(HTTPException) as e:require(a,{'planner','admin'})
    assert e.value.status_code==403
    require(b,{'planner','admin'})

def test_snapshot_hash_is_key_order_independent():
    assert fingerprint({'a':1,'b':2})==fingerprint({'b':2,'a':1})

def test_browser_tab_session_does_not_persist_in_localstorage():
    from pathlib import Path
    src=(Path(__file__).parents[1]/'enterprise_workbench/site/enterprise-console.js').read_text(encoding='utf-8')
    assert "sessionStorage.setItem(SESSION_KEY" in src
    assert "sessionStorage.removeItem(SESSION_KEY" in src
    assert "await request('/me')" in src
    assert "localStorage.setItem('v19b_token'" not in src
    assert "state.session=who" in src
