"""RC3.5 read-only time-phased plan explanation and exception classification.

A positive MRP `net` is a replenishment requirement, not a stock-out.
Planned receipts are proposals, not confirmed receipts. This module never
claims finite-capacity feasibility or real supplier commitment.
"""
from __future__ import annotations
from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation, ROUND_CEILING


def dec(value):
    try:
        n = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        raise ValueError('INVALID_MRP_NUMBER') from None
    if not n.is_finite():
        raise ValueError('INVALID_MRP_NUMBER')
    return n


def bucket_date(iso, granularity):
    day = date.fromisoformat(iso)
    if granularity == 'day':
        return day.isoformat()
    if granularity == 'week':
        return (day - timedelta(days=day.weekday())).isoformat()
    raise ValueError('INVALID_BUCKET_GRANULARITY')


def explain_supply(row, item, as_of):
    """Evidence-only explanation of one persisted daily MRP suggestion.

    Report verified policy attribution only when the stored quantity is
    reproduced exactly. Never infer a rule from the size of the surplus.
    """
    net = dec(row.get('net', 0))
    planned = dec(row.get('planned', 0))
    if net < 0 or planned < 0:
        raise ValueError('NEGATIVE_PLANNING_QUANTITY')
    if (net == 0) != (planned == 0):
        return {'status':'UNVERIFIED', 'reason':'净需求与计划供应零值不一致，需核对快照与计算规则'}
    kind = str(item.get('kind') or row.get('kind') or '').upper()
    if kind not in ('MAKE', 'BUY'):
        kind = 'UNKNOWN'
    result = {'status':'UNVERIFIED', 'supply_kind':kind, 'net_requirement':str(net),
              'planned_supply':str(planned), 'surplus':str(planned-net),
              'need_date':str(row.get('date') or ''),
              'planned_receipt_date':str(row.get('date') or ''),
              'planned_release_date':str(row.get('release') or ''),
              'uom':str(item.get('uom') or item.get('unit') or 'UNSPECIFIED').strip().upper(),
              'external_commitment':'NOT_VERIFIED',
              'rule_source':'FROZEN_MATERIAL_MASTER' if item else 'MISSING_MASTER'}
    try:
        expected_release=(date.fromisoformat(str(row['date']))-timedelta(days=int(item['lead_days']))).isoformat()
        result['lead_days']=int(item['lead_days'])
        observed_release=str(row.get('release') or '').strip()
        result['planned_release_date']=observed_release or expected_release
        result['release_date_source']='PERSISTED_PLAN_LINE' if observed_release else 'DERIVED_FROM_FROZEN_SNAPSHOT'
        result['release_date_verified']=(observed_release == expected_release) if observed_release else True
    except (KeyError,TypeError,ValueError,OverflowError):
        result['release_date_verified']=False
    if not item or not all(k in item for k in ('moq', 'lot', 'lead_days')):
        result['reason']='物料主数据缺少 MOQ、批量或提前期；不得从差额推断规则'
        return result
    moq, lot = dec(item['moq']),dec(item['lot'])
    if moq < 0 or lot <= 0:
        raise ValueError('INVALID_BATCH_POLICY')
    minimum = max(net,moq) if net else Decimal(0)
    expected = (minimum/lot).to_integral_value(rounding=ROUND_CEILING)*lot if net else Decimal(0)
    result.update({'moq':str(moq),'lot_multiple':str(lot),
        'minimum_before_rounding':str(minimum), 'expected_supply':str(expected),
        'policy_calculation_matches':expected==planned})
    if expected!=planned:
        result['reason']='保存的计划供应与当前快照 MOQ/批量规则计算不一致；不归因到任一规则'
    elif not result['release_date_verified']:
        result['reason']='批量数量核对一致，但计划释放日不符合提前期；需复核时间'
    else:
        result['status']='VERIFIED'
        result['moq_applied']=net>0 and moq>net
        result['lot_rounding_applied']=expected>minimum
        result['reason']='MOQ 生效；批量向上取整' if result['moq_applied'] and result['lot_rounding_applied'] else (
            'MOQ 生效' if result['moq_applied'] else ('批量向上取整' if result['lot_rounding_applied'] else '净需求足额建议，无额外批量调整'))
    result['release_overdue']=bool(result['planned_release_date'] and as_of and result['planned_release_date'] < as_of and net>0)
    return result


def analyze(snapshot, lines, granularity='week', long_lead_days=14):
    """Derive day/week aggregates and order attribution from trusted PG snapshot.

    `sources` are source allocations, not a guaranteed end-to-end Pegging chain.
    Rows are netted globally and aggregated without adding opening balances.
    """
    if granularity not in ('day', 'week'):
        raise ValueError('INVALID_BUCKET_GRANULARITY')
    if not isinstance(snapshot, dict) or not isinstance(lines, list) or len(lines)>20000:
        raise ValueError('INVALID_MRP_INPUT')
    items = snapshot.get('items') or {}
    orders = {str(o['order_id']):o for o in snapshot.get('orders', [])}
    # RC3.6: resolve units at the frozen material-master boundary. Do not
    # silently sum quantities from incompatible units in one material bucket.
    material_units = {}
    groups = defaultdict(lambda: {'gross':Decimal(0),'net':Decimal(0),
       'planned':Decimal(0),'confirmed_receipts':Decimal(0), 'sources':defaultdict(Decimal),
       'unconfirmed_shortfall':Decimal(0), 'lead_days':0,'kind':'', 'release_before_as_of':False,
       'unit':None, 'source_dates':defaultdict(Decimal)})
    as_of = str(snapshot.get('as_of',''))
    for row in lines:
        material = str(row['material'])
        day = str(row['date'])
        key = (material,bucket_date(day,granularity))
        g = groups[key]
        item = items.get(material) or {}
        master_unit = str(item.get('uom') or item.get('unit') or '').strip().upper()
        row_unit = str(row.get('uom') or row.get('unit') or '').strip().upper()
        if master_unit and row_unit and master_unit != row_unit:
            raise ValueError('MRP_UNIT_MISMATCH')
        unit = master_unit or row_unit
        previous_unit = material_units.get(material)
        if previous_unit and unit and previous_unit != unit:
            raise ValueError('MRP_UNIT_MISMATCH')
        if unit:
            material_units[material] = unit
        if g['unit'] and unit and g['unit'] != unit:
            raise ValueError('MRP_UNIT_MISMATCH')
        g['unit'] = g['unit'] or unit or None
        g['lead_days'] = int(item.get('lead_days',0))
        g['kind'] = str(item.get('kind',row.get('kind','')))
        for field in ('gross','net','planned'):
            g[field] += dec(row.get(field,0))
        g['confirmed_receipts'] += dec(row.get('receipts',0))
        for source in row.get('sources',[]):
            qty = dec(source['qty'])
            if qty < 0:
                raise ValueError('NEGATIVE_SOURCE_ALLOCATION')
            source_id = str(source['source'])
            g['sources'][source_id] += qty
            # Date is evidence of when a source contributed to demand;
            # it is not a supplier commitment or physical receipt.
            g['source_dates'][(source_id, day)] += qty
        # This is a planning feasibility warning, NOT confirmed actual shortage.
        release_value=str(row.get('release') or '').strip()
        if not release_value and item.get('lead_days') is not None:
            release_value=(date.fromisoformat(day)-timedelta(days=int(item.get('lead_days',0)))).isoformat()
        if dec(row.get('net',0))>0 and release_value and release_value < as_of:
            g['release_before_as_of']=True
            g['unconfirmed_shortfall'] += dec(row['net'])
    result=[]
    explanations=[]
    for daily_row in lines:
        item=items.get(str(daily_row['material'])) or {}
        detail=explain_supply(daily_row,item,as_of)
        explanations.append({'material':str(daily_row['material']), 'date':str(daily_row['date']), **detail})
    for (material,day), g in sorted(groups.items()):
        related=[]
        for source,qty in sorted(g['sources'].items()):
            order=orders.get(source)
            related.append({'source':source,'qty':str(qty),
              'order_id':source if order else None,
              'order_due':str(order['due']) if order else None,
              'source_kind':'ORDER' if order else 'PLANNED_UPSTREAM',
              'demand_dates':[{'date':d,'qty':str(v)} for (sid,d),v in sorted(g['source_dates'].items()) if sid==source]})
        if g['release_before_as_of']:
            severity='BLOCK'
            explanation='补货建议的计划释放日早于快照日期，存在无法按标准提前期执行的风险'
        elif g['net']>0 and g['lead_days']>=long_lead_days:
            severity='RISK'
            explanation='长交期物料需要计划补充，尚无供应商确认到货证据'
        elif g['net']>0:
            severity='REPLENISHMENT'
            explanation='存在净需求；不能据此认定实际缺料或停工'
        else:
            severity='COVERED'
            explanation='该时间桶无需新增净需求；不代表产能或供应履约已确认'
        result.append({'material':material,'bucket':day,'granularity':granularity,
            'unit':g['unit'] or material_units.get(material),
            'gross':str(g['gross']),'net_replenishment':str(g['net']),
            'net_requirement':str(g['net']), # RC3.6 additive alias; preserve legacy consumer
            'planned_receipts_unconfirmed':str(g['planned']),
            'planned_supply':str(g['planned']), # suggested quantity, not supplier confirmation
            'confirmed_receipts':str(g['confirmed_receipts']),
            'lead_days':g['lead_days'],'lead_class':'LONG' if g['lead_days']>=long_lead_days else 'SHORT',
            'severity':severity,'reason':explanation,'source_allocations':related,
            'release_overdue_net':str(g['unconfirmed_shortfall'])})
    return {'granularity':granularity,'rows':result,'row_count':len(result),
      'supply_explanations':explanations,
      'semantics':{'net':'NET_REPLENISHMENT_NOT_SHORTAGE',
       'net_requirement':'NET_REQUIREMENT_NOT_PHYSICAL_SHORTAGE',
       'legacy_net_replenishment':'COMPATIBILITY_ALIAS_OF_NET_REQUIREMENT',
       'planned':'UNCONFIRMED_PLANNED_RECEIPT',
       'sources':'SOURCE_ALLOCATION_NOT_FULL_PEGGING',
       'capacity':'INFINITE_CAPACITY_NOT_MES_SCHEDULE',
       'unit':'MATERIAL_MASTER_UNIT_NO_IMPLICIT_CONVERSION',
       'demand_dates':'SOURCE_DEMAND_DATES_NOT_PHYSICAL_RECEIPTS',
       'supply_explanations':'DAILY_POLICY_VERIFIED_ONLY_NOT_EXTERNAL_ORDER'}}
