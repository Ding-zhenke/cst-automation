"""Review or discard an owned tab after a returned native schematic VBA error."""

from pathlib import Path
import re

from tpc_service.errors import ServiceError
from .diagnostics import exception_diagnostics, mark_stage
from .native import file_digest
from .project_lifecycle import path_key
from .store import assert_environment_unclaimed, identifier, lock, read


OPERATION = 'recover_schematic_history'
ROLLBACK_ERROR = 'session_schematic_rollback_unverified'
_VBA_RESPONSE = re.compile(
    r'\AAn error occurred while trying to execute execute_vba_code:\r?\nError in VBA code:\r?\n'
    r'.*?\r?\n\r?\n\(&H[0-9a-fA-F]{8}\) [^\r\n]+\r?\n[^\r\n]+\(Line:\d+\)\s*\Z',
    re.DOTALL)


def is_native_vba_response(message):
    return isinstance(message, str) and _VBA_RESPONSE.fullmatch(message) is not None


def returned_vba_error(job, error):
    """Recognize the native error envelope in both old and new worker receipts."""
    if (job.get('operation') != 'history' or job.get('params', {}).get('domain') != 'schematic'
            or error.get('code') != 'session_operation_failed'):
        return False
    details = error.get('details', {})
    data = details.get('diagnostics', {})
    return (data.get('stage') == 'history.submit_schematic' and data.get('operation') == 'history'
            and data.get('job_id') == job.get('job_id') and data.get('exception_type') == 'RuntimeError'
            and data.get('exception_module') == 'builtins'
            and (details.get('schematic_call_state') == 'returned_native_vba_error'
                 or (not data.get('message_truncated') and is_native_vba_response(data.get('message')))))


def validate_options(params):
    common = {'project_id', 'failed_job_id', 'expected_digest', 'confirm_idle', 'action'}
    action = params.get('action')
    if action not in ('inspect', 'rollback'):
        raise ServiceError('invalid_session_argument', 'Explicit inspect or rollback action required')
    allowed = common | ({'parameter_names', 'block_names'} if action == 'inspect' else {'confirm_discard', 'review_note'})
    if set(params) - allowed:
        raise ServiceError('invalid_session_argument', 'Unsupported schematic recovery option')
    identifier(params.get('project_id'))
    identifier(params.get('failed_job_id'))
    expected = params.get('expected_digest')
    if params.get('confirm_idle') is not True or not isinstance(expected, str) or not re.fullmatch('[0-9a-f]{64}', expected):
        raise ServiceError('invalid_session_argument', 'Caller-confirmed idle and exact expected_digest required')
    if action == 'rollback':
        note = params.get('review_note')
        if params.get('confirm_discard') is not True or not isinstance(note, str) or not 0 < len(note.strip()) <= 1000:
            raise ServiceError('invalid_session_argument', 'Rollback requires explicit discard confirmation and review note')
    for key in ('parameter_names', 'block_names'):
        names = params.get(key, [])
        if not isinstance(names, list) or len(names) > 1000 or not all(isinstance(n, str) and 0 < len(n) <= 512 for n in names):
            raise ServiceError('invalid_session_argument', f'{key} must be a bounded list of names')


def _check_baseline(path, expected):
    if not Path(path).is_file() or file_digest(path) != expected:
        raise ServiceError('session_digest_mismatch', 'Saved schematic baseline does not match the requested digest')


def _preflight(runtime, job):
    from .store import alive

    params = job['params']
    validate_options(params)
    state = runtime.state()
    if (runtime.backend != 'cst' or state.get('status') != 'needs_reconcile'
            or state.get('launch_intent') or state.get('uncertain_jobs') or state.get('close_requested')
            or (state.get('runtime_diagnostics') or {}).get('state', 'clear') != 'clear'):
        raise ServiceError('session_schematic_recovery_refused', 'Unsafe session state prevents schematic recovery')
    failed = read(runtime.folder / 'jobs' / (params['failed_job_id'] + '.json')) or {}
    error = failed.get('error') or {}
    monitor = error.get('details', {}).get('session_monitor') or {}
    if (failed.get('job_id') != params['failed_job_id'] or failed.get('session_id') != state['session_id']
            or failed.get('status') != 'failed' or not failed.get('finished_at')
            or failed.get('params', {}).get('project_id') != params['project_id']
            or state.get('last_error') != error or not returned_vba_error(failed, error)
            or monitor.get('failure_latched') or monitor.get('first_failure')):
        raise ServiceError('session_schematic_recovery_refused', 'Current fence requires a finished, matching native VBA error receipt')
    for journal in (runtime.folder / 'jobs').glob('*.json'):
        other = read(journal)
        if other.get('job_id') == job['job_id']:
            continue
        if other.get('status') in ('queued', 'running', 'needs_reconcile'):
            raise ServiceError('session_busy', 'Other work prevents schematic recovery')
        if (params['action'] == 'rollback' and other.get('status') == 'succeeded'
                and other.get('operation') == OPERATION and other.get('params', {}).get('action') == 'rollback'
                and other['params'].get('failed_job_id') == failed['job_id']):
            raise ServiceError('session_schematic_recovery_refused', 'This failure already has a successful rollback receipt')
    record = state['projects'].get(params['project_id'])
    if (not record or record.get('project_id') != params['project_id'] or record.get('tab_closed')
            or record.get('saved') is not True or record.get('saved_digest') != params['expected_digest']):
        raise ServiceError('session_digest_mismatch', 'Exact registered saved schematic baseline required')
    _check_baseline(record['path'], params['expected_digest'])
    identity = state.get('environment')
    if not alive(identity):
        raise ServiceError('session_environment_mismatch', 'Recorded environment identity is not live')
    with lock(runtime.folder.parent / 'registry.lock'):
        assert_environment_unclaimed(runtime.folder.parent, state['session_id'], identity)
    return record, identity


def _read_schematic(handle, params):
    schematic = handle.schematic
    parameters, blocks = {}, {}
    names = params.get('parameter_names', [])
    if names:
        count = int(schematic.GetNumberOfParameters())
        if not 0 <= count <= 10000:
            raise ServiceError('session_schematic_recovery_refused', 'Schematic parameter enumeration exceeds the review limit')
        index = {str(schematic.GetParameterName(i)): i for i in range(count)}
        parameters = {name: str(schematic.GetParameterSValue(index[name])) if name in index else None for name in names}
    for name in params.get('block_names', []):
        block = schematic.Block
        block.Reset()
        block.Name(name)
        blocks[name] = str(block.GetTypeName()) if block.DoesExist() else None
    return parameters, blocks


def recover(runtime, job):
    from cst_solver.dialogs import check_dialogs
    from .read_review import borrow_open_project
    from .store import alive

    params = job['params']
    mark_stage(runtime, 'schematic_recovery.preflight')
    record, identity = _preflight(runtime, job)
    path, expected = record['path'], params['expected_digest']
    pid = identity['pid']
    check_dialogs('schematic history recovery', pid=pid)
    app, handle, opened = borrow_open_project(runtime, identity, path)
    result = dict(project_id=params['project_id'], failed_job_id=params['failed_job_id'],
                  saved_digest=expected, original_call_state='returned_native_vba_error',
                  session_state='needs_reconcile', idle_asserted_by_caller=True,
                  geometry_verified=False, solver_verified=False)
    if params['action'] == 'inspect':
        mark_stage(runtime, 'schematic_recovery.read')
        parameters, blocks = _read_schematic(handle, params)
        _check_baseline(path, expected)
        if not alive(identity) or path_key(handle.filename()) != path_key(path):
            raise ServiceError('session_environment_mismatch', 'Target identity changed during schematic review')
        return dict(result, parameters=parameters, blocks=blocks,
                    native_readback_verified=bool(params.get('parameter_names') or params.get('block_names')))

    check_dialogs('before discarding schematic changes', pid=pid)
    _check_baseline(path, expected)
    target = path_key(path)
    if not alive(identity) or path_key(handle.filename()) != target:
        raise ServiceError('session_environment_mismatch', 'Target identity changed before discard')
    runtime.handles.pop(params['project_id'], None)
    closed = False
    try:
        mark_stage(runtime, 'schematic_recovery.close_without_save')
        handle.close()  # Documented Project.close(): close this project without saving.
        closed = True
        _check_baseline(path, expected)
        if not alive(identity) or {path_key(p) for p in app.project.list_open_projects()} != opened.keys() - {target}:
            raise ServiceError(ROLLBACK_ERROR, 'Owned tab closure or neighboring tab identity could not be verified')
        check_dialogs('before reopening saved schematic', pid=pid)
        _check_baseline(path, expected)
        if not alive(identity):
            raise ServiceError(ROLLBACK_ERROR, 'Recorded environment changed after closing the target tab')
        mark_stage(runtime, 'schematic_recovery.reopen_saved')
        fresh = app.project.open_project(path)
        _check_baseline(path, expected)
        if (not alive(identity) or path_key(fresh.filename()) != target
                or {path_key(p) for p in app.project.list_open_projects()} != opened.keys()):
            raise ServiceError(ROLLBACK_ERROR, 'Reopened target or neighboring tabs could not be verified')
    except Exception as exc:
        raise ServiceError(ROLLBACK_ERROR, 'Schematic rollback did not complete with a verified receipt',
                           project_id=params['project_id'], failed_job_id=params['failed_job_id'],
                           close_returned=closed, diagnostics=exception_diagnostics(exc, runtime, job)) from exc
    app.cst_file = fresh
    runtime.app = app
    runtime.handles[params['project_id']] = fresh
    return dict(result, reopened=True, discarded_unsaved_changes=True, saved=False, native_readback_verified=False)
