"""RC3.6 supply-policy contract; static UI tests do not replace browser E2E."""
from pathlib import Path
from enterprise_workbench.rc35_planning import explain_supply, analyze

JS = (Path(__file__).resolve().parents[1]/'enterprise_workbench/site/enterprise-console.js')


def test_verified_buy_moq_and_lot_with_release_date():
    row={'material':'M','date':'2026-11-20','release':'2026-11-15','net':'11','planned':'20'}
    item={'kind':'BUY','moq':'15','lot':'10','lead_days':5}
    x=explain_supply(row,item,'2026-11-06')
    assert x['status']=='VERIFIED' and x['moq_applied'] and x['lot_rounding_applied']
    assert x['surplus']=='9' and x['planned_release_date']=='2026-11-15'
    assert x['external_commitment']=='NOT_VERIFIED'


def test_verified_make_batch_only():
    x=explain_supply({'date':'2026-11-20','release':'2026-11-18','net':'11','planned':'12'},
                     {'kind':'MAKE','moq':'0','lot':'6','lead_days':2},'2026-11-06')
    assert x['status']=='VERIFIED' and not x['moq_applied'] and x['lot_rounding_applied']


def test_rule_mismatch_never_attributes_surplus_to_moq():
    x=explain_supply({'date':'2026-11-20','release':'2026-11-18','net':'11','planned':'15'},
                     {'kind':'BUY','moq':'10','lot':'6','lead_days':2},'2026-11-06')
    assert x['status']=='UNVERIFIED' and not x['policy_calculation_matches']
    assert 'moq_applied' not in x


def test_release_date_mismatch_not_verified():
    x=explain_supply({'date':'2026-11-20','release':'2026-11-17','net':'11','planned':'12'},
                     {'kind':'MAKE','moq':'0','lot':'6','lead_days':2},'2026-11-06')
    assert x['status']=='UNVERIFIED' and not x['release_date_verified']


def test_daily_explanation_does_not_masquerade_as_weekly_total():
    snap={'as_of':'2026-11-06','items':{'M':{'kind':'BUY','uom':'PCS','moq':'10','lot':'5','lead_days':2}},'orders':[]}
    lines=[{'material':'M','date':'2026-11-16','release':'2026-11-14','net':'6','planned':'10'},
           {'material':'M','date':'2026-11-17','release':'2026-11-15','net':'6','planned':'10'}]
    result=analyze(snap,lines,'week')
    assert len(result['rows'])==1 and result['rows'][0]['planned_supply']=='20'
    assert len(result['supply_explanations'])==2
    assert all(x['status']=='VERIFIED' for x in result['supply_explanations'])


def test_workbench_supply_explanation_is_row_bound_and_evidence_only():
    js=JS.read_text(encoding='utf-8')
    assert 'function verifiedSupplyFor(row)' in js
    assert 'x.material===row.material&&x.date===row.date' in js
    assert 'supplyPolicyDetail(selected)' in js
    assert "x.status==='VERIFIED'" in js
    assert '当前不能根据数量差额猜测 MOQ' in js
    assert '外部采购/生产下达及实际到货均未验证' in js
