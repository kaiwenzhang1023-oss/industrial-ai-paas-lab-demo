"""RC3.5 audit query: tenant fence, role gate, cursor and run existence."""
from contextlib import contextmanager
from datetime import datetime, timezone
from unittest.mock import patch
from fastapi import HTTPException
from enterprise_workbench import rc4
from enterprise_workbench.rc2 import Identity

NOW = datetime(2026, 11, 5, tzinfo=timezone.utc)
WHO = Identity(actor="demo", tenant="tenant-a", role="viewer")

class Conn:
    def __init__(self, rows):
        self.rows=rows
        self.sql=""
        self.params=()
    def execute(self, sql, params):
        self.sql=sql
        self.params=params
        return self
    def fetchall(self):
        return self.rows

@contextmanager
def fake_pg(conn):
    yield conn

def test_audit_query_is_tenant_fenced_and_paginated():
    conn=Conn([(10,"APPROVED","approver","R1",{"run_id":"R1"},NOW),
               (9,"MRP_CREATED","planner","R1",{"run_id":"R1"},NOW)])
    with patch.object(rc4,"pg",lambda:fake_pg(conn)):
        result=rc4.audit_history(run_id=None,action=None,actor=None,before_id=None,limit=1,who=WHO)
    assert conn.params==("tenant-a",2)
    assert "tenant_id=%s" in conn.sql
    assert "ORDER BY id DESC LIMIT %s" in conn.sql
    assert result["has_more"] is True and result["next_before_id"]==10
    assert result["events"][0]["id"]==10
    assert result["scope"]=="AUTHORIZED_TENANT_ONLY"

def test_audit_filters_parameterized():
    conn=Conn([])
    with patch.object(rc4,"pg",lambda:fake_pg(conn)), patch.object(rc4,"check_run") as checked:
        result=rc4.audit_history(run_id="R1",action="APPROVED",actor="a",before_id=99,limit=30,who=WHO)
    checked.assert_called_once()
    assert conn.params==("tenant-a","R1","APPROVED","a",99,31)
    assert result["events"]==[] and result["next_before_id"] is None

def test_audit_forbidden_role():
    with patch.object(rc4,"pg") as mocked:
        try:
            rc4.audit_history(run_id=None,action=None,actor=None,before_id=None,limit=30,
                              who=Identity(actor="a",tenant="t",role="guest"))
        except HTTPException as exc:
            assert exc.status_code==403
        else:
            raise AssertionError("missing role denial")
        mocked.assert_not_called()

def test_audit_missing_run_is_404():
    conn=Conn([])
    def missing(*args):
        raise HTTPException(404,detail="RUN_NOT_FOUND")
    with patch.object(rc4,"pg",lambda:fake_pg(conn)),patch.object(rc4,"check_run",missing):
        try:
            rc4.audit_history(run_id="other-tenant",action=None,actor=None,before_id=None,limit=30,who=WHO)
        except HTTPException as exc:
            assert exc.status_code==404
        else:
            raise AssertionError("missing cross tenant 404")
