"""JSON-safe queue observations; never infer severity from text or legacy repr."""
import json


def observe_messages(messages):
    raw, summary = [], dict(info=0, warning=0, error=0, unknown=0)
    for message in messages:
        try:
            value = json.loads(json.dumps(message, ensure_ascii=False, allow_nan=False))
        except (TypeError, ValueError) as exc:
            value = {'raw_repr': repr(message), 'serialization_error': str(exc)}
        severity = value.get('type') if isinstance(value, dict) else None
        key = severity.lower() if isinstance(severity, str) else 'unknown'
        if key not in ('info', 'warning', 'error'):
            key = 'unknown'
        summary[key] += 1
        raw.append(value)
    return raw, summary
