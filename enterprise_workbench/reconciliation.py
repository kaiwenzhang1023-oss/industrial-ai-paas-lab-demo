"""Deterministic same-snapshot numeric comparison; requires independently computed B result.

No implicit mapping between RC8 and backend field semantics. Caller must provide
explicit comparable metric paths and units, otherwise the gate remains HOLD.
"""
from decimal import Decimal, InvalidOperation
from typing import Any


def at_path(data: dict, path: str) -> Any:
    value = data
    for key in path.split('.'):
        if not isinstance(value, dict) or key not in value:
            raise KeyError(path)
        value = value[key]
    return value


def numeric_diff(a: dict, b: dict, mappings: list[dict], *, same_snapshot: bool) -> dict:
    if not same_snapshot:
        return {'status': 'SNAPSHOT_MISMATCH', 'items': [], 'pass': False}
    if not mappings:
        return {'status': 'MAPPING_REQUIRED', 'items': [], 'pass': False}
    items = []
    for mapping in mappings:
        name, ap, bp = mapping['name'], mapping['a_path'], mapping['b_path']
        unit = mapping.get('unit', '')
        try:
            av, bv = at_path(a, ap), at_path(b, bp)
            if isinstance(av, bool) or isinstance(bv, bool):
                raise InvalidOperation('Boolean is not a numeric metric')
            ad, bd = Decimal(str(av)), Decimal(str(bv))
            if not ad.is_finite() or not bd.is_finite():
                raise InvalidOperation('Nonfinite value')
            delta = bd - ad
            tolerance = Decimal(str(mapping.get('tolerance', '0')))
            if tolerance < 0:
                raise InvalidOperation('Negative tolerance')
            status = 'MATCH' if abs(delta) <= tolerance else 'DIFFERENT'
            items.append({'name': name, 'unit': unit, 'a_path': ap, 'b_path': bp,
                          'a': str(ad), 'b': str(bd), 'delta_b_minus_a': str(delta),
                          'tolerance': str(tolerance), 'status': status,
                          'explanation': ('Within declared tolerance' if status == 'MATCH'
                                          else 'Backend and RC8 results differ; investigate input, BOM, timing and rounding')})
        except (KeyError, InvalidOperation, TypeError, ValueError) as exc:
            items.append({'name': name, 'a_path': ap, 'b_path': bp,
                          'status': 'UNCOMPARABLE', 'explanation': str(exc)})
    passed = all(x['status'] == 'MATCH' for x in items)
    return {'status': 'MATCH' if passed else 'DIFFERENCE_OR_UNCOMPARABLE',
            'pass': passed, 'items': items}


def verified_snapshot_diff(a: dict, b: dict, mappings: list[dict]) -> dict:
    """Fail closed when either independent result lacks matching snapshot evidence.

    This checks provenance only; it does not claim the two engines were executed.
    """
    if not isinstance(a, dict) or not isinstance(b, dict):
        return {'status': 'INPUT_REQUIRED', 'items': [], 'pass': False}
    ah = a.get('snapshot_hash') or a.get('input_hash')
    bh = b.get('snapshot_hash') or b.get('input_hash')
    if not (isinstance(ah, str) and ah.strip() and isinstance(bh, str) and bh.strip()):
        return {'status': 'SNAPSHOT_EVIDENCE_MISSING', 'items': [], 'pass': False}
    if ah != bh:
        return {'status': 'SNAPSHOT_MISMATCH', 'items': [], 'pass': False}
    if a.get('run_id') is not None and b.get('run_id') is not None and a['run_id'] != b['run_id']:
        return {'status': 'RUN_MISMATCH', 'items': [], 'pass': False}
    return numeric_diff(a, b, mappings, same_snapshot=True)
