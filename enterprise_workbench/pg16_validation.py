"""Pure evidence validators for RC3.6 PostgreSQL integration runs.

These functions do not connect to a database. They independently recompute the
persisted daily MRP facts from the immutable run snapshot and verify that
order-level pegging never allocates more stock, confirmed receipts, or planned
supply than the snapshot contains.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation, ROUND_CEILING


def _d(value, code='INVALID_DECIMAL'):
    try:
        value = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError(code) from None
    if not value.is_finite():
        raise ValueError(code)
    return value


def _shift(day, days):
    try:
        return (date.fromisoformat(str(day)) - timedelta(days=int(days))).isoformat()
    except (TypeError, ValueError, OverflowError):
        raise ValueError('INVALID_PLAN_DATE_OR_LEAD_TIME') from None


def recompute_snapshot_plan(snapshot):
    """Recompute daily gross/net/planned/closing from a frozen source snapshot.

    Scope matches the implemented MRP contract: single-parent acyclic BOM,
    shared inventory by material, calendar-day lead times, confirmed dated
    receipts, no finite-capacity scheduling, and MAKE planned lots explode to
    their children on the calculated release date.
    """
    if not isinstance(snapshot, dict):
        raise ValueError('INVALID_SNAPSHOT')
    try:
        as_of = date.fromisoformat(str(snapshot['as_of'])).isoformat()
        orders = list(snapshot['orders'])
        items = dict(snapshot['items'])
        bom = list(snapshot['bom'])
    except (KeyError, TypeError, ValueError):
        raise ValueError('INVALID_SNAPSHOT_SHAPE') from None
    if len(orders) > 20000 or len(items) > 20000 or len(bom) > 20000:
        raise ValueError('SNAPSHOT_SIZE_LIMIT')

    children = defaultdict(list)
    parents = defaultdict(set)
    edge_seen = set()
    for edge in bom:
        if not isinstance(edge, (list, tuple)) or len(edge) != 3:
            raise ValueError('INVALID_BOM_EDGE')
        parent, child, raw_qty = str(edge[0]), str(edge[1]), edge[2]
        qty = _d(raw_qty, 'INVALID_BOM_QUANTITY')
        if qty <= 0 or child not in items:
            raise ValueError('INVALID_BOM_QUANTITY_OR_CHILD')
        if (parent, child) in edge_seen:
            raise ValueError('DUPLICATE_BOM_EDGE')
        edge_seen.add((parent, child))
        children[parent].append((child, qty))
        parents[child].add(parent)
    if any(len(value) > 1 for value in parents.values()):
        raise ValueError('MULTI_PARENT_BOM_UNSUPPORTED')

    roots = {}
    demand = defaultdict(lambda: defaultdict(list))
    for order in orders:
        try:
            order_id = str(order['order_id'])
            product = str(order['product'])
            qty = _d(order['qty'], 'INVALID_ORDER_QUANTITY')
            due = date.fromisoformat(str(order['due']))
            priority = int(order.get('priority', 0))
        except (KeyError, TypeError, ValueError):
            raise ValueError('INVALID_ORDER_SNAPSHOT') from None
        if order_id in roots or qty <= 0 or product not in items:
            raise ValueError('DUPLICATE_OR_INVALID_ORDER')
        roots[order_id] = (product, qty, due, priority)
        root_item = items[product]
        release = _shift(due.isoformat(), root_item.get('lead_days', 0))
        for child, per in children[product]:
            demand[child][release].append((order_id, qty * per))

    depth = {}
    active = set()

    def visit(code, level):
        if code in active:
            raise ValueError('CYCLIC_BOM')
        active.add(code)
        for child, _ in children[code]:
            if child in depth and depth[child] != level + 1:
                raise ValueError('AMBIGUOUS_BOM_DEPTH')
            depth[child] = level + 1
            visit(child, level + 1)
        active.remove(code)

    for product, _, _, _ in roots.values():
        visit(product, 0)

    expected = {}
    for material in sorted(depth, key=lambda code: (depth[code], code)):
        item = items[material]
        kind = str(item.get('kind') or '').upper()
        if kind not in {'MAKE', 'BUY'}:
            raise ValueError('INVALID_MAKE_BUY_POLICY')
        lead = int(item.get('lead_days', 0))
        if lead < 0:
            raise ValueError('NEGATIVE_LEAD_TIME')
        on_hand = _d(item.get('on_hand', 0))
        reserved = _d(item.get('reserved', 0))
        blocked = _d(item.get('blocked', 0))
        safety = _d(item.get('safety', item.get('safety_stock', 0)))
        moq = _d(item.get('moq', 0))
        lot = _d(item.get('lot', item.get('lot_multiple', 1)))
        if min(on_hand, reserved, blocked, safety, moq) < 0 or lot <= 0 or reserved + blocked > on_hand:
            raise ValueError('INVALID_INVENTORY_OR_BATCH_POLICY')
        opening = on_hand - reserved - blocked
        receipts = defaultdict(Decimal)
        for receipt in item.get('receipts', []):
            if not isinstance(receipt, (list, tuple)) or len(receipt) < 2:
                raise ValueError('INVALID_CONFIRMED_RECEIPT')
            day = date.fromisoformat(str(receipt[0])).isoformat()
            qty = _d(receipt[1], 'INVALID_CONFIRMED_RECEIPT')
            if day < as_of or qty < 0:
                raise ValueError('INVALID_CONFIRMED_RECEIPT')
            receipts[day] += qty
        dates = sorted(set(demand[material]) | set(receipts))
        for day in dates:
            gross = sum((qty for _, qty in demand[material].get(day, [])), Decimal(0))
            receipt_qty = receipts[day]
            net = max(Decimal(0), safety - (opening + receipt_qty - gross))
            if net > 0:
                minimum = max(net, moq)
                planned = (minimum / lot).to_integral_value(rounding=ROUND_CEILING) * lot
            else:
                planned = Decimal(0)
            closing = opening + receipt_qty + planned - gross
            release = _shift(day, lead)
            expected[(material, day)] = {
                'gross': gross, 'net': net, 'planned': planned,
                'closing': closing, 'opening': opening,
                'confirmed_receipts': receipt_qty, 'release': release,
                'uom': str(item.get('uom') or item.get('unit') or 'UNSPECIFIED').strip().upper(),
                'kind': kind,
            }
            if planned > 0 and kind == 'MAKE':
                for child, per in children[material]:
                    demand[child][release].append((f'PLAN:{material}@{day}', planned * per))
            opening = closing
    return expected


def reconcile_persisted_plan(snapshot, persisted_lines):
    """Compare persisted PG16 fact rows with independent snapshot recompute."""
    expected = recompute_snapshot_plan(snapshot)
    actual = {}
    differences = []
    for row in persisted_lines:
        key = (str(row.get('material')), str(row.get('date')))
        if key in actual:
            differences.append({'key': key, 'field': 'DUPLICATE_LINE', 'reason': 'DUPLICATE_MATERIAL_DATE'})
        actual[key] = row
    for key in sorted(set(expected) | set(actual)):
        if key not in expected or key not in actual:
            differences.append({'key': key, 'field': 'LINE_PRESENCE', 'reason': 'SNAPSHOT_PERSISTENCE_GAP',
                                'expected_present': key in expected, 'actual_present': key in actual})
            continue
        exp, got = expected[key], actual[key]
        for field in ('gross', 'net', 'planned', 'closing'):
            try:
                value = _d(got[field])
            except (KeyError, ValueError):
                differences.append({'key': key, 'field': field, 'reason': 'PERSISTED_NUMERIC_MISSING_OR_INVALID'})
                continue
            if value != exp[field]:
                differences.append({'key': key, 'field': field, 'expected': str(exp[field]),
                                    'actual': str(value), 'reason': {
                                        'gross': 'BOM_EXPLOSION_OR_DEMAND_DATE_MISMATCH',
                                        'net': 'INVENTORY_RECEIPT_OR_SAFETY_NETTING_MISMATCH',
                                        'planned': 'MOQ_OR_LOT_MULTIPLE_MISMATCH',
                                        'closing': 'STOCK_CONSERVATION_MISMATCH',
                                    }[field]})
        unit = str(got.get('uom') or '').strip().upper()
        if unit != exp['uom']:
            differences.append({'key': key, 'field': 'uom', 'expected': exp['uom'], 'actual': unit or None,
                                'reason': 'FROZEN_MATERIAL_UNIT_MISMATCH'})
    return {'status': 'MATCH' if not differences else 'DIFFERENT',
            'expected_line_count': len(expected), 'actual_line_count': len(actual),
            'differences': differences[:100], 'difference_count': len(differences)}


def reconcile_supply_caps(snapshot, persisted_lines, persisted_pegs):
    """Verify PG16 pegging conservation and source-capacity bounds over time."""
    items = snapshot.get('items') or {}
    lines_by_material = defaultdict(dict)
    for line in persisted_lines:
        key = (str(line.get('material')), str(line.get('date')))
        if key[1] in lines_by_material[key[0]]:
            return {'status': 'DIFFERENT', 'reason': 'DUPLICATE_MRP_LINE', 'differences': [{'key': key}]}
        lines_by_material[key[0]][key[1]] = line
    pegs_by_material_day = defaultdict(list)
    differences = []
    for peg in persisted_pegs:
        key = (str(peg.get('material')), str(peg.get('date')))
        try:
            gross = _d(peg['gross'])
            stock = _d(peg['from_stock'])
            receipts = _d(peg['from_receipts'])
            planned = _d(peg['from_planned'])
        except (KeyError, ValueError):
            differences.append({'key': key, 'reason': 'INVALID_PEG_NUMERIC'})
            continue
        if min(gross, stock, receipts, planned) < 0 or gross != stock + receipts + planned:
            differences.append({'key': key, 'reason': 'PEG_CONSERVATION_MISMATCH'})
        pegs_by_material_day[key].append((gross, stock, receipts, planned, str(peg.get('order_id') or '')))

    for material, item in items.items():
        stock_pool = _d(item.get('on_hand', 0)) - _d(item.get('reserved', 0)) - _d(item.get('blocked', 0))
        receipt_pool = Decimal(0)
        planned_pool = Decimal(0)
        receipt_by_day = defaultdict(Decimal)
        for receipt in item.get('receipts', []):
            receipt_by_day[str(receipt[0])] += _d(receipt[1])
        dates = sorted(set(lines_by_material.get(material, {})) | set(receipt_by_day) |
                       {day for mat, day in pegs_by_material_day if mat == material})
        for day in dates:
            receipt_pool += receipt_by_day[day]
            line = lines_by_material.get(material, {}).get(day)
            if line:
                planned_pool += _d(line.get('planned', 0))
            day_pegs = pegs_by_material_day.get((material, day), [])
            if line:
                peg_gross = sum((x[0] for x in day_pegs), Decimal(0))
                if peg_gross != _d(line.get('gross', 0)):
                    differences.append({'key': (material, day), 'reason': 'DAILY_PEG_GROSS_MISMATCH',
                                        'line_gross': str(line.get('gross')), 'peg_gross': str(peg_gross)})
            used_stock = sum((x[1] for x in day_pegs), Decimal(0))
            used_receipts = sum((x[2] for x in day_pegs), Decimal(0))
            used_planned = sum((x[3] for x in day_pegs), Decimal(0))
            if used_stock > stock_pool:
                differences.append({'key': (material, day), 'reason': 'STOCK_ALLOCATION_EXCEEDS_AVAILABLE',
                                    'available': str(stock_pool), 'allocated': str(used_stock)})
            if used_receipts > receipt_pool:
                differences.append({'key': (material, day), 'reason': 'RECEIPT_ALLOCATION_EXCEEDS_CONFIRMED',
                                    'available': str(receipt_pool), 'allocated': str(used_receipts)})
            if used_planned > planned_pool:
                differences.append({'key': (material, day), 'reason': 'PLANNED_ALLOCATION_EXCEEDS_PLAN',
                                    'available': str(planned_pool), 'allocated': str(used_planned)})
            stock_pool -= used_stock
            receipt_pool -= used_receipts
            planned_pool -= used_planned
    return {'status': 'MATCH' if not differences else 'DIFFERENT',
            'difference_count': len(differences), 'differences': differences[:100]}
