from enterprise_workbench.pg16_validation import (
    recompute_snapshot_plan,
    reconcile_persisted_plan,
    reconcile_supply_caps,
)
from g4.core import _compare_order_pegging


def _fixture():
    snapshot = {
        'as_of': '2026-11-01',
        'orders': [{'order_id': 'SO-1', 'product': 'FG-1', 'qty': '2',
                    'due': '2026-11-10', 'priority': 5}],
        'items': {
            'FG-1': {'kind': 'MAKE', 'lead_days': 1, 'on_hand': '0', 'reserved': '0',
                     'blocked': '0', 'safety': '0', 'moq': '0', 'lot': '1',
                     'receipts': [], 'uom': 'PCS'},
            'RM-1': {'kind': 'BUY', 'lead_days': 2, 'on_hand': '1', 'reserved': '0',
                     'blocked': '0', 'safety': '0', 'moq': '5', 'lot': '4',
                     'receipts': [['2026-11-08', '1']], 'uom': 'PCS'},
        },
        'bom': [['FG-1', 'RM-1', '3']],
    }
    lines = [
        {'material': 'RM-1', 'date': '2026-11-08', 'gross': '0', 'net': '0',
         'planned': '0', 'closing': '2', 'uom': 'PCS'},
        {'material': 'RM-1', 'date': '2026-11-09', 'gross': '6', 'net': '4',
         'planned': '8', 'closing': '4', 'uom': 'PCS'},
    ]
    pegs = [{'material': 'RM-1', 'date': '2026-11-09', 'order_id': 'SO-1',
             'gross': '6', 'from_stock': '1', 'from_receipts': '1', 'from_planned': '4'}]
    return snapshot, lines, pegs


def test_snapshot_recompute_checks_bom_inventory_receipt_netting_and_batch_rounding():
    snapshot, lines, _ = _fixture()
    expected = recompute_snapshot_plan(snapshot)
    assert expected[('RM-1', '2026-11-09')]['gross'] == 6
    assert expected[('RM-1', '2026-11-09')]['net'] == 4
    assert expected[('RM-1', '2026-11-09')]['planned'] == 8
    assert expected[('RM-1', '2026-11-09')]['closing'] == 4
    assert reconcile_persisted_plan(snapshot, lines)['status'] == 'MATCH'


def test_snapshot_recompute_rejects_persisted_netting_drift():
    snapshot, lines, _ = _fixture()
    lines[1] = {**lines[1], 'net': '5'}
    result = reconcile_persisted_plan(snapshot, lines)
    assert result['status'] == 'DIFFERENT'
    assert any(x['field'] == 'net' and x['reason'] == 'INVENTORY_RECEIPT_OR_SAFETY_NETTING_MISMATCH'
               for x in result['differences'])


def test_pegging_source_caps_conserve_stock_receipts_and_planned_supply():
    snapshot, lines, pegs = _fixture()
    assert reconcile_supply_caps(snapshot, lines, pegs)['status'] == 'MATCH'
    over = [{**pegs[0], 'from_stock': '2', 'from_receipts': '1', 'from_planned': '3'}]
    result = reconcile_supply_caps(snapshot, lines, over)
    assert result['status'] == 'DIFFERENT'
    assert any(x['reason'] == 'STOCK_ALLOCATION_EXCEEDS_AVAILABLE' for x in result['differences'])


def test_native_a_and_pg16_order_level_pegging_must_match():
    a = [{'material_id': 'RM-1', 'date': '2026-11-09',
          'sources': [{'source': 'PLAN:FG-1@2026-11-10', 'origin': 'SO-1', 'qty': 6}]}]
    b = [{'material': 'RM-1', 'date': '2026-11-09', 'order_id': 'SO-1', 'gross': '6'}]
    assert _compare_order_pegging(a, b)['pegging_status'] == 'MATCH'
    assert _compare_order_pegging(a, [{**b[0], 'gross': '5'}])['pegging_status'] == 'DIFFERENT'


def test_native_a_aggregated_multi_order_pegging_is_not_falsely_passed():
    a = [{'material_id': 'RM-1', 'date': '2026-11-09',
          'sources': [{'source': 'PLAN:FG-1@2026-11-10', 'origin': 'MULTI_ORDER', 'qty': 6}]}]
    b = [{'material': 'RM-1', 'date': '2026-11-09', 'order_id': 'SO-1', 'gross': '3'},
         {'material': 'RM-1', 'date': '2026-11-09', 'order_id': 'SO-2', 'gross': '3'}]
    result = _compare_order_pegging(a, b)
    assert result['pegging_status'] == 'HOLD_ORDER_LEVEL_ATTRIBUTION'
    assert result['pegging_pass'] is False
