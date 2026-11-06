from enterprise_workbench.rc35_pegging import reconcile
from enterprise_workbench.rc4 import BatchReviewRequest, batch_review, ProposalAction
from enterprise_workbench.rc2 import Identity
from unittest.mock import patch
from uuid import uuid4
import pytest
from fastapi import HTTPException

def test_pegging_matches_order_allocations():
    lines=[{'material':'M1','date':'2026-11-05','gross':'8'}]
    pegs=[{'material':'M1','date':'2026-11-05','order_id':'O1','gross':'8','from_stock':'3','from_receipts':'2','from_planned':'3'}]
    result=reconcile(lines,pegs)
    assert result['status']=='PASS'
    assert result['orders'][0]['planned_unconfirmed']=='3'
    assert result['cross_level_chain_verified'] is False

def test_pegging_detects_missing_allocation():
    result=reconcile([{'material':'M1','date':'2026-11-05','gross':'8'}],[])
    assert result['status']=='MISMATCH'
    assert result['differences'][0]['difference']=='8'

def test_pegging_rejects_impossible_allocation():
    with pytest.raises(ValueError,match='INVALID_PEG_ALLOCATION'):
        reconcile([{'material':'M','date':'2026-11-05','gross':'2'}],
            [{'material':'M','date':'2026-11-05','order_id':'O','gross':'2','from_stock':'3','from_receipts':'0','from_planned':'0'}])

def test_batch_partial_success_and_distinct_keys():
    ids=[uuid4(),uuid4()]
    keys=[]
    def review(pid,body,who):
        keys.append(body.idempotency_key)
        if pid==ids[1]:raise HTTPException(409,'CONFLICT')
        return {'status':'APPROVED','command_id':'cmd'}
    with patch('enterprise_workbench.rc4.review_proposal',review):
        result=batch_review(BatchReviewRequest(proposal_ids=ids,decision='APPROVED',reason='审核通过',idempotency_key='batch-key-0001'),
            Identity(actor='reviewer',tenant='t',role='approver'))
    assert result['succeeded']==1 and result['failed']==1
    assert result['batch_mode']=='PER_ITEM_TRANSACTION'
    assert len(set(keys))==2

def test_batch_duplicate_is_rejected():
    pid=uuid4()
    with pytest.raises(HTTPException) as exc:
        batch_review(BatchReviewRequest(proposal_ids=[pid,pid],decision='APPROVED',reason='审核通过',idempotency_key='batch-key-0001'),
            Identity(actor='reviewer',tenant='t',role='approver'))
    assert exc.value.status_code==422
