"""Reproducible offline replay of the RC3.6 isolated branch seed snapshot.

This does not connect to PostgreSQL. The real PG16 gate reloads the live
snapshot and reruns the same validators against persisted rows.
"""
from __future__ import annotations
import json
import sys
from copy import deepcopy
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'backend'))
from app.domain.timephased import Item, Order, as_json
from app.domain.pegging import allocate
from enterprise_workbench.pg16_validation import reconcile_persisted_plan, reconcile_supply_caps
from g4.core import dynamic_comparison

SNAPSHOT = ROOT / 'release_evidence' / 'rc36' / 'PG16_BRANCH_SEED_SNAPSHOT.json'
OUT = ROOT / 'release_evidence' / 'rc36' / 'PG16_OFFLINE_SEED_REPLAY.json'


def build_persisted(snapshot):
    orders = [Order(x['order_id'], x['product'], Decimal(str(x['qty'])), x['due'], int(x.get('priority', 0)))
              for x in snapshot['orders']]
    items = {}
    for code, item in snapshot['items'].items():
        receipts = tuple((str(d), Decimal(str(q))) for d, q in item.get('receipts', []))
        items[code] = Item(code, item['kind'], int(item['lead_days']), Decimal(str(item['on_hand'])),
                           Decimal(str(item['reserved'])), Decimal(str(item['blocked'])),
                           Decimal(str(item['safety'])), Decimal(str(item['moq'])),
                           Decimal(str(item['lot'])), receipts, item['uom'])
    bom = [(p, c, Decimal(str(q))) for p, c, q in snapshot['bom']]
    lines, pegs = allocate(orders, items, bom, snapshot['as_of'])
    persisted_lines = [{**row, 'uom': snapshot['items'][row['material']]['uom']} for row in as_json(lines)]
    persisted_pegs = [{'material': p.material, 'date': p.need_date, 'order_id': p.order_id,
                       'gross': str(p.gross), 'from_stock': str(p.from_stock),
                       'from_receipts': str(p.from_receipts), 'from_planned': str(p.from_planned)}
                      for p in pegs]
    return {'lines': persisted_lines, 'pegs': persisted_pegs}


def scenario_snapshot(base, scenario):
    snap = deepcopy(base)
    if scenario == 'B':
        # Same perturbation as the PG16 gate: first eligible BUY direct component loses on-hand and receipts.
        snap['items']['BR-01']['on_hand'] = '0'
        snap['items']['BR-01']['receipts'] = []
    elif scenario == 'C':
        for order in snap['orders']:
            order['due'] = (date.fromisoformat(order['due']) + timedelta(days=7)).isoformat()
    elif scenario == 'D':
        snap['bom'][0][2] = str(Decimal(snap['bom'][0][2]) * Decimal(2))
    return snap


def main():
    base = json.loads(SNAPSHOT.read_text(encoding='utf-8'))
    rows = []
    for scenario in 'ABCD':
        snapshot = scenario_snapshot(base, scenario)
        persisted = build_persisted(snapshot)
        plan = reconcile_persisted_plan(snapshot, persisted['lines'])
        caps = reconcile_supply_caps(snapshot, persisted['lines'], persisted['pegs'])
        ab = dynamic_comparison(snapshot, persisted)
        rows.append({
            'scenario': scenario,
            'line_count': len(persisted['lines']),
            'peg_count': len(persisted['pegs']),
            'snapshot_plan_recompute': plan['status'],
            'supply_source_caps': caps['status'],
            'native_a_b_numeric': ab['status'],
            'native_a_b_order_level_pegging': ab['pegging_status'],
            'a_input_hash_equals_b_input_hash': ab['a_input_hash'] == ab['b_input_hash'],
            'difference_counts': {
                'plan': plan['difference_count'],
                'supply_caps': caps['difference_count'],
                'numeric': len(ab.get('differences', [])),
                'pegging': len(ab.get('pegging_differences', [])),
            },
        })
    passed = all(r['snapshot_plan_recompute'] == 'MATCH' and r['supply_source_caps'] == 'MATCH'
                 and r['native_a_b_numeric'] == 'MATCH' and r['native_a_b_order_level_pegging'] == 'MATCH'
                 and r['a_input_hash_equals_b_input_hash'] for r in rows)
    report = {
        'gate': 'RC36_OFFLINE_SEED_REPLAY',
        'status': 'PASS_OFFLINE_ONLY' if passed else 'FAIL_OFFLINE',
        'database_connected': False,
        'pg16_business_gate_pass': False,
        'source_snapshot': str(SNAPSHOT.relative_to(ROOT)),
        'scenarios': rows,
        'note': 'Offline algorithm replay from a SELECT-captured Neon child-branch seed snapshot. It does not create or read PG16 MRP runs and cannot replace the live PG16 business gate.'
    }
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print('RC36_OFFLINE_SEED_REPLAY=' + report['status'])
    for row in rows:
        print(row['scenario'] + ': plan=' + row['snapshot_plan_recompute'] +
              ' caps=' + row['supply_source_caps'] + ' A/B=' + row['native_a_b_numeric'] +
              ' Pegging=' + row['native_a_b_order_level_pegging'])
    print('EVIDENCE=' + str(OUT))
    return 0 if passed else 2


if __name__ == '__main__':
    raise SystemExit(main())
