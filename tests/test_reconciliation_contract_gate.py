from enterprise_workbench.reconciliation import numeric_diff

def test_equal_numeric_metrics():
 r=numeric_diff({'x':{'qty':100}},{'y':{'qty':'100.00'}},[{'name':'qty','a_path':'x.qty','b_path':'y.qty','unit':'pcs'}],same_snapshot=True)
 assert r['status']=='MATCH' and r['pass']

def test_mismatch_is_not_implicitly_comparable():
 r=numeric_diff({'x':1},{'x':1},[{'name':'x','a_path':'x','b_path':'x'}],same_snapshot=False)
 assert r['status']=='SNAPSHOT_MISMATCH' and not r['pass']

def test_missing_mapping_holds():
 r=numeric_diff({'x':1},{'x':1},[],same_snapshot=True)
 assert r['status']=='MAPPING_REQUIRED' and not r['pass']

def test_difference_explained():
 r=numeric_diff({'x':10},{'x':12},[{'name':'x','a_path':'x','b_path':'x','unit':'pcs'}],same_snapshot=True)
 assert r['status']=='DIFFERENCE_OR_UNCOMPARABLE' and r['items'][0]['delta_b_minus_a']=='2'

def test_nonfinite_rejected():
 r=numeric_diff({'x':'NaN'},{'x':1},[{'name':'x','a_path':'x','b_path':'x'}],same_snapshot=True)
 assert r['items'][0]['status']=='UNCOMPARABLE'
