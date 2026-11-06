import pytest
from enterprise_workbench.rc35_pegging import reconcile, trace_bom_lineage

BASE={'orders':[{'order_id':'SO-01','product':'EM-100','qty':'2','due':'2026-11-20'}],
      'bom':[['EM-100','MOTOR-ROTOR','1'],['MOTOR-ROTOR','LAMI','8'],['EM-100','ENAMEL','2']]}

def sample(material,amount='4'):
    return {'material':material,'date':'2026-11-07','order_id':'SO-01','gross':amount,'from_stock':amount,'from_receipts':'0','from_planned':'0'}

def test_three_level_order_to_material_chain():
    l=trace_bom_lineage(BASE,[sample('LAMI')]);assert l['status']=='PASS'
    assert l['paths'][0]['path']==['EM-100','MOTOR-ROTOR','LAMI']
    assert l['physical_supply_trace_verified'] is False

def test_unknown_or_unrelated_order_rejected():
    l=trace_bom_lineage(BASE,[{**sample('LAMI'),'order_id':'FOREIGN'}]);assert l['status']=='MISMATCH'
    assert l['differences'][0]['reason']=='MISSING_ORDER_BOM_PATH'

def test_reconciliation_fails_if_bom_lineage_mismatch_even_when_numbers_match():
    p=sample('LAMI');p['order_id']='SO-OTHER'
    r=reconcile([{'material':'LAMI','date':'2026-11-07','gross':'4'}],[p],BASE)
    assert r['status']=='MISMATCH'
    assert r['differences']==[] and r['bom_lineage']['status']=='MISMATCH'

def test_bom_cycle_fails_closed():
    s={**BASE,'bom':BASE['bom']+[['LAMI','EM-100','1']]}
    with pytest.raises(ValueError,match='CYCLIC_BOM'):trace_bom_lineage(s,[sample('LAMI')])

def test_bom_multiple_parents_fails_closed():
    s={**BASE,'bom':BASE['bom']+[['ENAMEL','LAMI','1']]}
    with pytest.raises(ValueError,match='MULTI_PARENT_BOM_UNSUPPORTED'):trace_bom_lineage(s,[sample('LAMI')])

def test_order_with_no_peg_is_not_invented():
    result=trace_bom_lineage(BASE,[])
    assert result['paths']==[] and result['physical_supply_trace_verified'] is False
