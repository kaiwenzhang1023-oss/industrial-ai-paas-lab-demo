"""RC3.5 proposal boundaries: permissions, tenant isolation and state guards."""
import uuid
from contextlib import contextmanager
from unittest.mock import patch
import pytest
from fastapi import HTTPException
from enterprise_workbench import rc4
from enterprise_workbench.rc2 import Identity

PLANNER=Identity(actor='planner',tenant='tenant-A',role='planner')
APPROVER=Identity(actor='approver',tenant='tenant-A',role='approver')
GUEST=Identity(actor='visitor',tenant='tenant-A',role='viewer')
PID=uuid.uuid4()

class Conn:
    def __init__(self,record=None):self.record=record;self.calls=[]
    def execute(self,sql,params):self.calls.append((sql,params));return self
    def fetchone(self):return self.record
    @contextmanager
    def transaction(self):yield
@contextmanager
def pg(c):yield c

def test_proposal_lookup_scoped_to_verified_tenant():
    c=Conn(None)
    with pytest.raises(HTTPException) as e:rc4._proposal(c,PLANNER,PID,lock=True)
    assert e.value.status_code==404
    assert c.calls[0][1]==('tenant-A',PID)
    assert 'FOR UPDATE' in c.calls[0][0]

def test_only_planner_can_save():
    body=rc4.ProposalSave(expected_candidate_hash='a'*64,run_id='R1',kind='stock',target='BR-01',quantity='20',idempotency_key='abcdefgh')
    with patch.object(rc4,'pg') as mocked:
        with pytest.raises(HTTPException) as e:rc4.save_proposal(body,who=GUEST)
    assert e.value.status_code==403
    mocked.assert_not_called()

def test_only_approver_can_review():
    body=rc4.ProposalAction(idempotency_key='abcdefgh',reason='审核通过',decision='APPROVED')
    with patch.object(rc4,'pg') as mocked:
        with pytest.raises(HTTPException) as e:rc4.review_proposal(PID,body,who=PLANNER)
    assert e.value.status_code==403
    mocked.assert_not_called()

def test_review_rejects_already_reviewed_without_outbox():
    c=Conn()
    proposal={'status':'APPROVED','run_id':'R1'}
    with patch.object(rc4,'pg',lambda:pg(c)),patch.object(rc4,'_proposal',lambda *a,**k:proposal):
        with pytest.raises(HTTPException) as e:
            rc4.review_proposal(PID,rc4.ProposalAction(idempotency_key='abcdefgh',reason='确认完成',decision='APPROVED'),who=APPROVER)
    assert e.value.status_code==409
    assert not any('INSERT INTO version_b_rc2.outbox' in sql for sql,_ in c.calls)

def test_compensation_is_not_external_rollback():
    c=Conn()
    proposal={'status':'APPROVED','run_id':'R1','command_id':uuid.uuid4()}
    with patch.object(rc4,'pg',lambda:pg(c)),patch.object(rc4,'_proposal',lambda *a,**k:proposal),patch.object(rc4,'_command',lambda *a:{'status':'DONE'}):
        result=rc4.request_compensation(PID,rc4.ProposalAction(idempotency_key='abcdefgh',reason='复核原执行结果'),who=APPROVER)
    assert result['effect']=='AUDIT_REQUEST_ONLY'
    assert result['external_execution'] is False
    assert any('COMPENSATION_REQUESTED' in sql for sql,_ in c.calls)
