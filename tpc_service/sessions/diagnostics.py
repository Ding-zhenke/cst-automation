"""Bounded exception evidence; no locals, source lines, SDK calls or retries."""
import traceback


def mark_stage(runtime, stage):
    """Mark entry into a boundary; does not certify its completion."""
    runtime._diagnostic_stage = stage


def _text(value):
    try:
        text = str(value)
    except Exception:
        text = '<text unavailable: ' + type(value).__name__ + '>'
    return (text[:4081] + '... [truncated]', True) if len(text) > 4096 else (text, False)


def exception_repr(exc):
    try:
        return _text(repr(exc))[0]
    except Exception:
        return '<repr unavailable: ' + type(exc).__name__ + '>'


def _describe(exc):
    message, truncated = _text(exc)
    frames = [{'file': _text(frame.f_code.co_filename)[0],
               'function': _text(frame.f_code.co_name)[0], 'line': line}
              for frame, line in traceback.walk_tb(exc.__traceback__)]
    result = {'exception_type': type(exc).__name__, 'exception_module': type(exc).__module__,
              'message': message, 'message_truncated': truncated,
              'traceback': frames[-12:], 'frames_omitted': max(0, len(frames) - 12)}
    if isinstance(exc, OSError):
        result.update(errno=exc.errno, winerror=getattr(exc, 'winerror', None),
                      filename=_text(exc.filename)[0] if exc.filename is not None else None,
                      filename2=_text(exc.filename2)[0] if exc.filename2 is not None else None)
    return result


def exception_diagnostics(exc, runtime, job):
    result = _describe(exc)
    result.update(stage=getattr(runtime, '_diagnostic_stage', 'worker.execute'),
                  operation=job.get('operation'), job_id=job.get('job_id'), causes=[])
    seen = {id(exc)}
    current = exc
    for _ in range(3):
        cause = current.__cause__ or (None if current.__suppress_context__ else current.__context__)
        if cause is None or id(cause) in seen:
            result['cause_chain_truncated'] = cause is not None
            break
        result['causes'].append(_describe(cause))
        seen.add(id(cause))
        current = cause
    else:
        result['cause_chain_truncated'] = bool(current.__cause__ or
            (None if current.__suppress_context__ else current.__context__))
    return result
