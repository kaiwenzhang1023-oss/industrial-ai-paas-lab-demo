from enterprise_workbench.reconciliation import verified_snapshot_diff
M=[{'name':'net','a_path':'metrics.net','b_path':'metrics.net','unit':'PCS'}]
A={'snapshot_hash':'H1','run_id':'R1','metrics':{'net':'12.00'}}
B={'input_hash':'H1','run_id':'R1','metrics':{'net':12}}

def test_verified_same_snapshot_numeric_match():
    assert verified_snapshot_diff(A,B,M)['status']=='MATCH'

def test_missing_hash_cannot_claim_match():
    assert verified_snapshot_diff({'metrics':{'net':12}},B,M)['status']=='SNAPSHOT_EVIDENCE_MISSING'

def test_different_run_cannot_claim_match():
    assert verified_snapshot_diff(A,{**B,'run_id':'R2'},M)['status']=='RUN_MISMATCH'

def test_numeric_difference_not_masked():
    result=verified_snapshot_diff(A,{**B,'metrics':{'net':13}},M)
    assert result['status']=='DIFFERENCE_OR_UNCOMPARABLE' and not result['pass']
