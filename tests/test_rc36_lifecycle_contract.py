from enterprise_workbench.rc36_lifecycle_contract import audit

RUN={'run_id':'R1','input_hash':'abc','lines':[{'material':'M1','gross':'5','net':'5','planned':'10','date':'2026-11-20','release':'2026-11-18'}]}
BASE={'run_id':'R1','snapshot_hash':'abc','workflow':{'state':'WAITING_REVIEW'},'decision':None,'command':None}

def test_pending_valid_evidence():
    assert audit(RUN,BASE,events=[])['status']=='PASS'

def test_snapshot_mismatch_holds():
    assert 'SNAPSHOT_LINK_UNVERIFIED' in audit(RUN,{**BASE,'snapshot_hash':'bad'},events=[])['issues']

def test_approved_command_and_receipt_link():
    d={'type':'APPROVED','actor':'guest','at':'2026-11-20T01:00:00','reason':'checked'}
    c={'command_id':'C1','run_id':'R1','status':'DONE','receipt':{'processed_at':'2026-11-20T02:00:00'}}
    assert audit(RUN,{**BASE,'decision':d,'command':c,'workflow':{'state':'EXECUTED_INTERNAL'}},events=[{'run_id':'R1'}])['status']=='PASS'

def test_reject_cannot_execute():
    d={'type':'REJECTED','actor':'guest','at':'today','reason':'invalid'}
    assert 'REJECTED_HAS_EXECUTION' in audit(RUN,{**BASE,'decision':d},command={'run_id':'R1'},events=[])['issues']

def test_done_without_receipt_holds():
    d={'type':'APPROVED','actor':'guest','at':'today','reason':'checked'}
    c={'run_id':'R1','status':'DONE'}
    assert 'DONE_WITHOUT_RECEIPT' in audit(RUN,{**BASE,'decision':d,'command':c},events=[])['issues']

def test_invalid_quantities_and_dates():
    run={**RUN,'lines':[{'gross':'1','net':'NaN','planned':'2','date':'2026-11-20'}]}
    assert 'INVALID_PLAN_LINE_0' in audit(run,BASE,events=[])['issues']

def test_no_audit_evidence_is_not_pass():
    assert 'AUDIT_EVENTS_NOT_PROVIDED' in audit(RUN,BASE)['issues']

def test_cross_run_event_rejected():
    assert 'CROSS_RUN_AUDIT_EVENT' in audit(RUN,BASE,events=[{'run_id':'OTHER'}])['issues']
