"""Read-only RC3.6 four-stage evidence audit. Never creates business evidence."""
from datetime import datetime, date
from decimal import Decimal, InvalidOperation


def _qty(value):
    if isinstance(value, bool):
        raise ValueError('INVALID_QUANTITY')
    try:
        result = Decimal(str(value))
        if not result.is_finite() or result < 0:
            raise ValueError('INVALID_QUANTITY')
        return result
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError('INVALID_QUANTITY') from None


def _date(value):
    try:
        return date.fromisoformat(str(value))
    except (ValueError, TypeError):
        raise ValueError('INVALID_DATE') from None


def _instant(value):
    try:
        parsed = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
        if parsed.tzinfo is None:
            raise ValueError('TIMEZONE_REQUIRED')
        return parsed
    except (ValueError, TypeError):
        raise ValueError('INVALID_TIMESTAMP') from None


def audit(run, overview, command=None, events=None):
    """Return PASS only for evidence supplied; no implicit approval or fulfillment.

    Optional fields are validated when present, to preserve existing RC3.5 wire shape.
    No physical receipt, supplier order, or external MES command is inferred.
    """
    issues = []
    def check(ok, code):
        if not ok:
            issues.append(code)
    if not isinstance(run, dict) or not isinstance(overview, dict):
        return {'status': 'HOLD', 'issues': ['MISSING_PERSISTED_EVIDENCE']}
    run_id = run.get('run_id') or run.get('id')
    check(bool(run_id), 'RUN_ID_MISSING')
    check(overview.get('run_id') == run_id, 'OVERVIEW_RUN_MISMATCH')
    rh = run.get('input_hash') or run.get('snapshot_hash')
    oh = overview.get('snapshot_hash')
    check(bool(rh and oh and rh == oh), 'SNAPSHOT_LINK_UNVERIFIED')
    lines = run.get('lines')
    if not isinstance(lines, list):
        issues.append('PLAN_LINES_MISSING')
    else:
        for i, line in enumerate(lines):
            if not isinstance(line, dict):
                issues.append(f'INVALID_PLAN_LINE_{i}')
                continue
            try:
                gross, net, planned = (_qty(line[k]) for k in ('gross', 'net', 'planned'))
                if net > gross and not line.get('allow_net_over_gross'):
                    issues.append(f'NET_EXCEEDS_GROSS_{i}')
                if net > 0 and planned == 0:
                    issues.append(f'PLAN_UNCOVERED_{i}')
                if planned > 0 and planned < net:
                    issues.append(f'PLAN_SHORTAGE_{i}')
                demand_date = _date(line['date'])
                if planned > 0:
                    release_date = _date(line['release'])
                    if release_date > demand_date:
                        issues.append(f'RELEASE_AFTER_DEMAND_{i}')
                if line.get('snapshot_hash') is not None and line['snapshot_hash'] != rh:
                    issues.append(f'LINE_SNAPSHOT_MISMATCH_{i}')
                if line.get('run_id') is not None and line['run_id'] != run_id:
                    issues.append(f'LINE_RUN_MISMATCH_{i}')
                if line.get('unit') is not None and not str(line['unit']).strip():
                    issues.append(f'LINE_UNIT_INVALID_{i}')
            except (KeyError, ValueError):
                issues.append(f'INVALID_PLAN_LINE_{i}')
    decision = overview.get('decision')
    workflow = overview.get('workflow') or {}
    state = workflow.get('state') if isinstance(workflow, dict) else None
    cmd = command if command is not None else overview.get('command')
    if decision is not None:
        if not isinstance(decision, dict):
            issues.append('DECISION_INVALID')
        else:
            kind = decision.get('type')
            check(kind in ('APPROVED', 'REJECTED'), 'DECISION_TYPE_INVALID')
            check(bool(decision.get('actor') and decision.get('at') and decision.get('reason')), 'DECISION_AUDIT_FIELDS_MISSING')
            if decision.get('run_id') is not None:
                check(decision['run_id'] == run_id, 'DECISION_RUN_MISMATCH')
            if decision.get('snapshot_hash') is not None:
                check(decision['snapshot_hash'] == rh, 'DECISION_SNAPSHOT_MISMATCH')
            if kind == 'REJECTED':
                check(cmd is None, 'REJECTED_HAS_EXECUTION')
                check(state not in ('EXECUTING', 'EXECUTED_INTERNAL'), 'REJECTED_EXECUTION_STATE')
            if kind == 'APPROVED':
                check(cmd is not None, 'APPROVED_COMMAND_MISSING')
            if cmd and decision.get('at') and cmd.get('created_at'):
                try:
                    check(_instant(cmd['created_at']) >= _instant(decision['at']), 'COMMAND_BEFORE_APPROVAL')
                except ValueError:
                    issues.append('APPROVAL_COMMAND_TIME_INVALID')
    elif state not in ('WAITING_REVIEW', 'NO_RUN'):
        issues.append('DECISION_MISSING_FOR_STATE')
    if cmd is not None:
        if not isinstance(cmd, dict):
            issues.append('COMMAND_INVALID')
        else:
            check(cmd.get('run_id') == run_id, 'COMMAND_RUN_MISMATCH')
            if not isinstance(decision, dict) or decision.get('type') != 'APPROVED':
                issues.append('UNAPPROVED_COMMAND')
            if cmd.get('snapshot_hash') is not None:
                check(cmd['snapshot_hash'] == rh, 'COMMAND_SNAPSHOT_MISMATCH')
            if cmd.get('status') == 'DONE':
                receipt = cmd.get('receipt')
                check(isinstance(receipt, dict) and bool(receipt), 'DONE_WITHOUT_RECEIPT')
                if isinstance(receipt, dict):
                    check(bool(receipt.get('processed_at') or receipt.get('at')), 'RECEIPT_TIME_MISSING')
                    if receipt.get('run_id') is not None:
                        check(receipt['run_id'] == run_id, 'RECEIPT_RUN_MISMATCH')
                    if receipt.get('command_id') is not None:
                        check(receipt['command_id'] == cmd.get('command_id'), 'RECEIPT_COMMAND_MISMATCH')
                    if receipt.get('snapshot_hash') is not None:
                        check(receipt['snapshot_hash'] == rh, 'RECEIPT_SNAPSHOT_MISMATCH')
                    if receipt.get('processed_at') and cmd.get('created_at'):
                        try:
                            check(_instant(receipt['processed_at']) >= _instant(cmd['created_at']), 'RECEIPT_BEFORE_COMMAND')
                        except ValueError:
                            issues.append('RECEIPT_COMMAND_TIME_INVALID')
            if cmd.get('external_execution') is True:
                issues.append('EXTERNAL_EXECUTION_NOT_AUTHORIZED')
    if events is None:
        issues.append('AUDIT_EVENTS_NOT_PROVIDED')
    elif not isinstance(events, list):
        issues.append('INVALID_AUDIT_EVENTS')
    else:
        for i, event in enumerate(events):
            if not isinstance(event, dict):
                issues.append(f'INVALID_AUDIT_EVENT_{i}')
                continue
            if event.get('run_id') not in (run_id, None):
                issues.append('CROSS_RUN_AUDIT_EVENT')
            if event.get('snapshot_hash') is not None and event['snapshot_hash'] != rh:
                issues.append('CROSS_SNAPSHOT_AUDIT_EVENT')
            if event.get('command_id') is not None and (not isinstance(cmd, dict) or event['command_id'] != cmd.get('command_id')):
                issues.append('CROSS_COMMAND_AUDIT_EVENT')
    return {'status': 'PASS' if not issues else 'HOLD', 'issues': issues,
            'semantics': {'planned_supply': 'UNCONFIRMED_PROPOSAL', 'worker': 'INTERNAL_ONLY',
                          'external_fulfillment': 'NOT_VERIFIED'}}
