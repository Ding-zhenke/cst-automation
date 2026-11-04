"""Known returned/saved outcomes are distinct from uncertain side effects."""
import hashlib

import pytest

from tpc_service.sessions import worker


def receipt(tmp_path):
    path = tmp_path / 'project.cst'; path.write_bytes(b'synthetic saved project')
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    project = {'path': str(path), 'saved': True, 'saved_digest': digest}
    outcome = {'project': str(path), 'run_token': 'synthetic-run', 'submitted': True,
               'execution_returned': True, 'status': 'unverified', 'validation_passed': False}
    error = {'code': 'session_solve_unverified', 'message': 'Review warnings', 'details': {
        'outcome': outcome, 'project_id': 'p', 'saved': True, 'saved_digest': digest,
        'execution_returned': True}}
    job = {'job_id': 'j', 'operation': 'solve', 'params': {'project_id': 'p'}}
    state = {'status': 'ready', 'projects': {'p': project}, 'uncertain_jobs': [], 'launch_intent': False}
    return job, error, state


def test_known_saved_outcome_keeps_failed_job_but_not_uncertain_session(tmp_path):
    job, error, state = receipt(tmp_path)
    worker._finish_failed_job(job, error, state)
    assert job['status'] == 'failed'
    assert job['result']['saved'] is True
    assert job['result']['solver_outcome']['validation_passed'] is False
    assert job['result']['review_required'] is True
    assert state['status'] == 'ready'
    assert state['last_error'] == error


@pytest.mark.parametrize('change', ['return', 'digest', 'disk', 'foreign', 'uncertain', 'launch', 'prior_fence', 'dialog'])
def test_unknown_or_inconsistent_work_still_needs_reconcile(tmp_path, change):
    job, error, state = receipt(tmp_path); failure = None
    if change == 'return': error['details']['execution_returned'] = False
    if change == 'digest': error['details']['saved_digest'] = '0' * 64
    if change == 'disk':
        from pathlib import Path
        Path(state['projects']['p']['path']).write_bytes(b'changed after save')
    if change == 'foreign': error['details']['project_id'] = 'another'
    if change == 'uncertain': state['uncertain_jobs'] = ['old']
    if change == 'launch': state['launch_intent'] = True
    if change == 'prior_fence': state['status'] = 'needs_reconcile'
    if change == 'dialog': failure = {'state': 'blocked_by_dialog'}
    worker._finish_failed_job(job, error, state, monitor_failure=failure)
    assert state['status'] == 'needs_reconcile'
    assert job['status'] == 'failed'
    assert not job.get('result')


def test_missing_execution_receipt_is_never_released_by_an_existing_file(tmp_path):
    job, error, state = receipt(tmp_path)
    error['code'] = 'session_operation_failed'
    worker._finish_failed_job(job, error, state)
    assert state['status'] == 'needs_reconcile'


def test_native_solve_failure_carries_explicit_return_and_save_receipts(tmp_path):
    from types import SimpleNamespace
    from tpc_service.errors import ServiceError
    from tpc_service.sessions.operations import execute
    job, error, state = receipt(tmp_path)
    outcome = error['details']['outcome']; calls = []
    app = SimpleNamespace(run_checked=lambda **kw: outcome)
    class Runtime:
        backend = 'cst'
        def project(self, project_id): return app, state['projects'][project_id]
        def save(self, current, project_id):
            calls.append('save')
            return state['projects'][project_id]
    with pytest.raises(ServiceError) as caught:
        execute(Runtime(), job)
    assert calls == ['save']
    worker._finish_failed_job(job, caught.value.to_dict(), state)
    assert state['status'] == 'ready'
    assert job['result']['solver_outcome'] == outcome


def test_save_exception_never_becomes_a_known_saved_solve(tmp_path):
    from types import SimpleNamespace
    from tpc_service.sessions.operations import execute
    job, error, state = receipt(tmp_path)
    app = SimpleNamespace(run_checked=lambda **kw: error['details']['outcome'])
    class Runtime:
        backend = 'cst'
        def project(self, project_id): return app, state['projects'][project_id]
        def save(self, *args): raise OSError('save interrupted')
    with pytest.raises(OSError): execute(Runtime(), job)
