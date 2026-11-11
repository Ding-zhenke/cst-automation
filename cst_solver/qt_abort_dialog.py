"""Explicit Yes on the exact CST 2026 abort question, never a stop/idle API."""
import copy
import math
import re
import time

from .result_cache_dialog import _bridge, _identity

__all__ = ['inspect', 'confirm_yes']
TITLE = 'CST MICROWAVE STUDIO 2026'
BODY = 'Do you really want to abort this calculation?'
CLASS = 'Qt683QWindow'


def _validate(snapshot):
    if not isinstance(snapshot, dict):
        raise ValueError('Explicit complete UIA snapshot required')
    _identity(snapshot.get('pid'), snapshot.get('hwnd'), snapshot.get('creation_time'))
    stamp = snapshot.get('observed_at')
    if (snapshot.get('title') != TITLE or snapshot.get('body') != BODY or
            snapshot.get('class_name') != CLASS or snapshot.get('complete') is not True or
            snapshot.get('unsupported_controls') != [] or
            type(snapshot.get('owner_hwnd')) is not int or snapshot['owner_hwnd'] <= 0 or
            snapshot['owner_hwnd'] == snapshot['hwnd'] or snapshot.get('owner_pid') != snapshot['pid'] or
            type(stamp) not in (int, float) or not math.isfinite(stamp) or not 0 <= time.time()-stamp <= 30):
        raise ValueError('Fresh complete exact owned CST abort question required')
    def runtime_id(value):
        return isinstance(value, str) and 0 < len(value) <= 512 and re.fullmatch(r'-?\d+(,-?\d+)+', value, flags=re.ASCII)
    if not runtime_id(snapshot.get('root_id')):
        raise ValueError('Root runtime identity required')
    controls = snapshot.get('controls')
    if (not isinstance(controls, list) or len(controls) != 3 or
            any(not isinstance(c, dict) or c.get('kind') != 'ControlType.Button' or
                c.get('enabled') is not True or c.get('selected') is not None or
                not runtime_id(c.get('id')) for c in controls) or
            {c.get('name') for c in controls} != {'Yes', 'No', 'Cancel'} or
            len({c['id'] for c in controls} | {snapshot['root_id']}) != 4):
        raise ValueError('Exactly three distinct enabled Yes/No/Cancel buttons required')


def inspect(*, pid, hwnd, expected_creation_time):
    """Read one exact known prompt, without confirming or invoking CST."""
    _identity(pid, hwnd, expected_creation_time)
    result = _bridge(dict(action='inspect_abort', pid=pid, hwnd=hwnd, creation_time=expected_creation_time))
    observed = dict(result, observed_at=time.time())
    _validate(observed)
    return observed


def confirm_yes(snapshot, *, authorization_note, confirm_stop=False, source_job_id):
    """Confirm an already authorized stop; all final lifecycle checks are separate."""
    observed = copy.deepcopy(snapshot)
    _validate(observed)
    if (confirm_stop is not True or not isinstance(authorization_note, str) or
            not 0 < len(authorization_note.strip()) <= 2048 or
            not isinstance(source_job_id, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,128}', source_job_id)):
        raise ValueError('Explicit stop authorization and original job ID required')
    result = _bridge(dict(action='confirm_abort', pid=observed['pid'], hwnd=observed['hwnd'],
                          creation_time=observed['creation_time'], snapshot=observed,
                          confirm_stop=True, authorization_note=authorization_note))
    return dict(result, before=observed, authorization_note=authorization_note, source_job_id=source_job_id,
                original_call_returned='unknown', solver_stopped_verified=False, ds_idle_verified=False,
                native_job_binding_verified=False, next_step='inspect_original_stop_request_job_and_dialogs_without_replay')
