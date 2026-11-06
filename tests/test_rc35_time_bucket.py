from enterprise_workbench.rc35_planning import analyze

S={'as_of':'2026-11-05','items':{'WIRE':{'lead_days':20,'kind':'BUY'},'BOLT':{'lead_days':2,'kind':'BUY'}},'orders':[{'order_id':'O1','due':'2026-11-30'}]}
L=[{'material':'WIRE','date':'2026-11-09','release':'2026-10-20','gross':'20','net':'12','planned':'12','receipts':'3','sources':[{'source':'O1','qty':'20'}]},
   {'material':'WIRE','date':'2026-11-10','release':'2026-10-21','gross':'10','net':'6','planned':'6','receipts':'0','sources':[{'source':'PLAN:X@2026-11-10','qty':'10'}]},
   {'material':'BOLT','date':'2026-11-09','release':'2026-11-07','gross':'10','net':'5','planned':'5','receipts':'2','sources':[{'source':'O1','qty':'10'}]}]

def test_weekly_aggregation_and_no_double_counting():
    a=analyze(S,L,'week')
    assert len(a['rows'])==2
    w=next(x for x in a['rows'] if x['material']=='WIRE')
    assert w['gross']=='30' and w['net_replenishment']=='18'
    assert w['planned_receipts_unconfirmed']=='18' and w['confirmed_receipts']=='3'
    assert w['severity']=='BLOCK' and w['lead_class']=='LONG'
    assert len(w['source_allocations'])==2
    assert a['semantics']['net']=='NET_REPLENISHMENT_NOT_SHORTAGE'

def test_daily_weekly_conservation():
    daily=analyze(S,L,'day')['rows'];weekly=analyze(S,L,'week')['rows']
    from decimal import Decimal
    for field in ['gross','net_replenishment','planned_receipts_unconfirmed','confirmed_receipts']:
        assert sum(Decimal(x[field]) for x in daily)==sum(Decimal(x[field]) for x in weekly)

def test_replenishment_not_block_when_release_feasible():
    a=analyze(S,[L[-1]],'day')['rows'][0]
    assert a['severity']=='REPLENISHMENT'
    assert a['source_allocations'][0]['order_id']=='O1'

def test_bad_bucket_and_nonfinite_rejected():
    import pytest
    with pytest.raises(ValueError):analyze(S,L,'month')
    broken=[dict(L[0],gross='NaN')]
    with pytest.raises(ValueError):analyze(S,broken)

def test_empty_and_zero_are_safe():
    assert analyze(S,[],'day')['rows']==[]
    x=dict(L[-1],net='0',planned='0')
    assert analyze(S,[x],'day')['rows'][0]['severity']=='COVERED'
