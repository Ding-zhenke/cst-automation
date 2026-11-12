"""Pure case inventory; callers must independently verify actual artifacts."""
import re


def missing_cases(expected, receipts, basis):
    if (not isinstance(expected, list) or not expected or
            any(not isinstance(x, str) or not x.strip() for x in expected) or
            len(set(expected)) != len(expected)):
        raise ValueError('Unique explicit case IDs required')
    if not isinstance(receipts, dict) or not isinstance(basis, str) or not basis.strip():
        raise ValueError('Receipt mapping and nonempty input identity required')
    missing = []
    for case in expected:
        item = receipts.get(case)
        if (not isinstance(item, dict) or item.get('basis') != basis or
                item.get('status') != 'complete' or not isinstance(item.get('artifact_sha256'), str) or
                not re.fullmatch('[0-9a-f]{64}', item['artifact_sha256'])):
            missing.append(case)
    return missing
