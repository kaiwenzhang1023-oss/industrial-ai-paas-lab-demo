from contextlib import contextmanager
from unittest.mock import patch
from fastapi import HTTPException
from enterprise_workbench import rc4
from enterprise_workbench.rc2 import Identity

WHO=Identity(actor='viewer',tenant='tenant-a',role='viewer')
@contextmanager
def conn():yield object()

def test_time_bucket_endpoint_reads_only_persisted_snapshot():
    snapshot={'as_of':'2026-11-05','items':{'X':{'kind':'BUY','lead_days':20}},'orders':[]}
    persisted={'input_hash':'hash','lines':[{'material':'X','date':'2026-11-10','release':'2026-10-21','gross':'4','net':'4','planned':'4','receipts':'0','sources':[]}]}
    with patch.object(rc4,'pg',conn),patch.object(rc4,'_persisted_snapshot',return_value=(snapshot,persisted)) as fence:
        r=rc4.time_buckets('R-1','day',WHO)
    fence.assert_called_once()
    assert r['source']=='PERSISTED_POSTGRESQL'
    assert r['tenant']=='tenant-a' and r['rows'][0]['severity']=='BLOCK'
    assert r['semantics']['planned']=='UNCONFIRMED_PLANNED_RECEIPT'

def test_time_bucket_endpoint_denies_guest_before_pg():
    with patch.object(rc4,'pg') as mocked:
        try:rc4.time_buckets('R-1','week',Identity(actor='a',tenant='t',role='guest'))
        except HTTPException as e:assert e.status_code==403
        else:raise AssertionError('guest allowed')
        mocked.assert_not_called()
