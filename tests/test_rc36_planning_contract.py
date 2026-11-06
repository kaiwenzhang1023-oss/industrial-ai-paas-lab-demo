"""RC3.6 regression: unit fences and dated allocation evidence."""
from copy import deepcopy
from decimal import Decimal
import pytest
from enterprise_workbench.rc35_planning import analyze

SNAPSHOT = {'as_of':'2026-11-05','items':{'M':{'uom':'EA','lead_days':3}},'orders':[{'order_id':'O1','due':'2026-11-15'}]}
ROWS = [
 {'material':'M','date':'2026-11-09','release':'2026-11-06','gross':'5','net':'3','planned':'3','receipts':'2','sources':[{'source':'O1','qty':'5'}]},
 {'material':'M','date':'2026-11-10','release':'2026-11-07','gross':'7','net':'7','planned':'7','receipts':'0','sources':[{'source':'O1','qty':'7'}]},
]

def test_source_date_evidence_is_not_collapsed_into_weekly_total():
    row=analyze(SNAPSHOT,ROWS,'week')['rows'][0]
    assert row['unit']=='EA'
    assert row['source_allocations'][0]['qty']=='12'
    assert row['source_allocations'][0]['demand_dates']==[{'date':'2026-11-09','qty':'5'},{'date':'2026-11-10','qty':'7'}]
    assert row['confirmed_receipts']=='2'
    assert row['planned_receipts_unconfirmed']=='10'

def test_unit_mismatch_rejected_even_when_same_material():
    rows=deepcopy(ROWS)
    rows[1]['unit']='KG'
    with pytest.raises(ValueError,match='MRP_UNIT_MISMATCH'):
        analyze(SNAPSHOT,rows,'week')

def test_no_master_mixed_unit_rejected():
    snapshot=deepcopy(SNAPSHOT)
    snapshot['items']['M'].pop('uom')
    rows=deepcopy(ROWS)
    rows[0]['unit']='EA';rows[1]['unit']='KG'
    with pytest.raises(ValueError,match='MRP_UNIT_MISMATCH'):
        analyze(snapshot,rows,'day')

def test_negative_source_rejected():
    rows=deepcopy(ROWS);rows[0]['sources'][0]['qty']='-1'
    with pytest.raises(ValueError,match='NEGATIVE_SOURCE_ALLOCATION'):
        analyze(SNAPSHOT,rows)

def test_day_week_conservation_and_decimal_precision():
    rows=deepcopy(ROWS)
    rows[0]['net']='0.1234567890123456789'
    d=analyze(SNAPSHOT,rows,'day')['rows']
    w=analyze(SNAPSHOT,rows,'week')['rows']
    assert sum(Decimal(x['net_replenishment']) for x in d)==Decimal(w[0]['net_replenishment'])
    assert w[0]['net_replenishment']=='7.1234567890123456789'
