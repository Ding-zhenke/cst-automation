"""Explicit bounded getters for a geometry-review fence, without state recovery."""
from pathlib import Path
from tpc_service.errors import ServiceError
from .inspection import validate_options, inspect_native
from .project_lifecycle import path_key
from .store import read


def borrow_open_project(runtime, identity, path):
    """Borrow one already-open tab from the exact recorded environment."""
    from .store import alive
    from cst_solver.environment import environment_pid

    if not alive(identity):
        raise ServiceError('session_environment_mismatch', 'Recorded environment identity is not live')
    app = runtime.app
    if app is None:
        from cst_solver import setup
        app = setup.attach(pid=identity['pid'])
    if environment_pid(app.project) != identity['pid'] or not alive(identity):
        raise ServiceError('session_environment_mismatch', 'Exact environment identity mismatch')
    opened = {path_key(p): p for p in app.project.list_open_projects()}
    target = opened.get(path_key(path))
    if target is None:
        raise ServiceError('session_read_review_refused', 'Target is not already open; no restoration is permitted')
    handle = app.project.get_open_project(target)
    if path_key(handle.filename()) != path_key(path):
        raise ServiceError('session_environment_mismatch', 'Native project does not match registration')
    return app, handle, opened


def inspect_saved_geometry(runtime, job):
    from .store import alive
    from .native import file_digest
    params = job['params']
    validate_options(params)
    state = runtime.state()
    if (runtime.backend != 'cst' or state.get('status') not in ('ready', 'needs_reconcile')
            or state.get('launch_intent') or state.get('uncertain_jobs')
            or (state.get('runtime_diagnostics') or {}).get('state', 'clear') != 'clear'):
        raise ServiceError('session_read_review_refused', 'Unsafe environment or unknown work prevents native review')
    if state['status'] == 'needs_reconcile' and state.get('last_error', {}).get('code') != 'session_geometry_unverified':
        raise ServiceError('session_read_review_refused', 'This native review is scoped to a geometry-validation fence')
    record = state['projects'].get(params['project_id'])
    expected = params['expected_digest']
    if (not record or record.get('project_id') != params['project_id'] or record.get('tab_closed')
            or record.get('saved') is not True or record.get('saved_digest') != expected
            or not Path(record['path']).is_file() or file_digest(record['path']) != expected):
        raise ServiceError('session_digest_mismatch', 'Read-only review requires the exact registered saved baseline')
    for path in (runtime.folder / 'jobs').glob('*.json'):
        other = read(path)
        if other.get('job_id') != job['job_id'] and other.get('status') in ('running', 'queued', 'needs_reconcile'):
            raise ServiceError('session_busy', 'Other work prevents read-only review')
    identity = state.get('environment')
    app, handle, _ = borrow_open_project(runtime, identity, record['path'])
    app.cst_file = handle
    result = inspect_native(app, params)
    if not alive(identity) or file_digest(record['path']) != expected or path_key(handle.filename()) != path_key(record['path']):
        raise ServiceError('session_read_review_refused', 'Identity or saved baseline changed during read-only review')
    runtime.app = app
    runtime.handles[params['project_id']] = handle
    return dict(project=record, backend='cst', native_readback=result,
                readback_verified=not result['errors'], geometry_verified=False, solver_verified=False,
                message_read_status='not_read_preserve_queue', messages=[],
                session_state=state['status'], read_only_review=True,
                idle_asserted_by_caller=True, idle_verified=False)
