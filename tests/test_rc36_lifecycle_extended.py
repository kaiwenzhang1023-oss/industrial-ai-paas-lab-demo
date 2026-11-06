from enterprise_workbench.rc36_lifecycle_contract import audit

RUN = {'run_id':'R1','input_hash':'H1','lines':[{'gross':'12','net':'10','planned':'12','date':'2026-11-20','release':'2026-11-18','run_id':'R1','snapshot_hash':'H1','unit':'PCS'}]}
DEC = {'type':'APPROVED','actor':'reviewer','reason':'ok','at':'2026-11-18T09:00:00Z','run_id':'R1','snapshot_hash':'H1'}
CMD = {'command_id':'C1','run_id':'R1','snapshot_hash':'H1','status':'DONE','created_at':'2026-11-18T09:01:00Z','receipt':{'command_id':'C1','run_id':'R1','snapshot_hash':'H1','processed_at':'2026-11-18T09:02:00Z'}}
OV = {'run_id':'R1','snapshot_hash':'H1','workflow':{'state':'EXECUTED_INTERNAL'},'decision':DEC,'command':CMD}

def issues(run=RUN, overview=OV, events=None):
    return audit(run,overview,events=[] if events is None else events)['issues']

def test_complete_evidence_passes():
    assert audit(RUN,OV,events=[{'run_id':'R1','command_id':'C1','snapshot_hash':'H1'}])['status']=='PASS'

def test_line_snapshot_and_run_mismatch():
    assert 'LINE_RUN_MISMATCH_0' in issues({**RUN,'lines':[{**RUN['lines'][0],'run_id':'R2'}]})
    assert 'LINE_SNAPSHOT_MISMATCH_0' in issues({**RUN,'lines':[{**RUN['lines'][0],'snapshot_hash':'H2'}]})

def test_quantity_and_date_fail_closed():
    for field,value,code in [('net','13','NET_EXCEEDS_GROSS_0'),('planned','8','PLAN_SHORTAGE_0'),('release','2026-11-21','RELEASE_AFTER_DEMAND_0')]:
        assert code in issues({**RUN,'lines':[{**RUN['lines'][0],field:value}]})

def test_decision_and_command_snapshot_mismatch():
    assert 'DECISION_SNAPSHOT_MISMATCH' in issues(overview={**OV,'decision':{**DEC,'snapshot_hash':'H2'}})
    assert 'COMMAND_SNAPSHOT_MISMATCH' in issues(overview={**OV,'command':{**CMD,'snapshot_hash':'H2'}})

def test_receipt_link_and_time_mismatch():
    for field,value,code in [('command_id','C2','RECEIPT_COMMAND_MISMATCH'),('run_id','R2','RECEIPT_RUN_MISMATCH'),('processed_at','2026-11-18T08:00:00Z','RECEIPT_BEFORE_COMMAND')]:
        assert code in issues(overview={**OV,'command':{**CMD,'receipt':{**CMD['receipt'],field:value}}})

def test_reject_state_and_approval_order():
    rejected={**DEC,'type':'REJECTED'}
    assert 'REJECTED_EXECUTION_STATE' in issues(overview={**OV,'decision':rejected,'command':None})
    assert 'COMMAND_BEFORE_APPROVAL' in issues(overview={**OV,'command':{**CMD,'created_at':'2026-11-18T08:00:00Z'}})

def test_audit_snapshot_command_and_bad_record():
    assert 'CROSS_SNAPSHOT_AUDIT_EVENT' in issues(events=[{'snapshot_hash':'OTHER'}])
    assert 'CROSS_COMMAND_AUDIT_EVENT' in issues(events=[{'command_id':'OTHER'}])
    assert 'INVALID_AUDIT_EVENT_0' in issues(events=[None])

def test_boolean_quantity_rejected():
    assert 'INVALID_PLAN_LINE_0' in issues({**RUN,'lines':[{**RUN['lines'][0],'net':True}]})
