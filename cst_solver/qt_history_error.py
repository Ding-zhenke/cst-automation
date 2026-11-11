"""Explicit acknowledgement of a reviewed Qt History Error; never recovery."""
import copy
import math
import time

from .result_cache_dialog import _bridge, _identity, inspect

__all__ = ['inspect', 'acknowledge']
TITLES = ('History Error', 'CST MICROWAVE STUDIO - History Error')


def acknowledge(snapshot, *, authorization_note):
    """Invoke only OK on one exact fresh error; preserve the original job failure.

    Use inspect() for a fresh complete snapshot, not a cached list_dialogs row.
    This does not change job/session state or retry the failed native operation.
    """
    if not isinstance(snapshot, dict):
        raise ValueError('Explicit UIA snapshot required')
    observed = copy.deepcopy(snapshot)
    _identity(observed.get('pid'), observed.get('hwnd'), observed.get('creation_time'))
    stamp = observed.get('observed_at')
    if (not isinstance(authorization_note, str) or not 0 < len(authorization_note.strip()) <= 2048 or
            observed.get('title') not in TITLES or observed.get('complete') is not True or
            observed.get('unsupported_controls') or
            not isinstance(observed.get('body'), str) or not observed['body'].strip() or
            len(observed['body']) > 8192 or not observed.get('root_id') or
            type(stamp) not in (int, float) or not math.isfinite(stamp) or not 0 <= time.time()-stamp <= 30):
        raise ValueError('Fresh complete known History Error and explicit authorization required')
    controls = observed.get('controls')
    if (not isinstance(controls, list) or not 1 <= len(controls) <= 2 or
            any(not isinstance(c, dict) or c.get('kind') != 'ControlType.Button' or
                c.get('name') not in ('OK', 'Details >>') for c in controls)):
        raise ValueError('History Error must have only OK and optional Details >>')
    buttons = [c for c in controls if c['name'] == 'OK']
    if len(buttons) != 1 or buttons[0].get('enabled') is not True:
        raise ValueError('Unique enabled OK required')
    result = _bridge(dict(action='acknowledge_history_error', pid=observed['pid'], hwnd=observed['hwnd'],
                          creation_time=observed['creation_time'], snapshot=observed))
    return dict(result, authorization_note=authorization_note, before=observed,
                original_call_returned='unknown', recovery_verified=False,
                next_step='inspect_dialogs_and_original_job_without_replay')
