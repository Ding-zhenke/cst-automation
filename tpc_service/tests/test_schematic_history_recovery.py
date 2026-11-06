from pathlib import Path
from types import SimpleNamespace

import pytest

from cst_solver import dialogs
from tpc_service.errors import ServiceError
from tpc_service.sessions import SessionManager
from tpc_service.sessions import store
from tpc_service.sessions.native import Runtime, file_digest
from tpc_service.sessions.worker import _finish_failed_job
from tpc_service.tests.test_session_project_discipline import fixture
from tpc_service.tests.test_session_schematic_history import payload


VBA_ERROR = ('An error occurred while trying to execute execute_vba_code:\n'
             'Error in VBA code:\nSub Main\nExample.Setter\nEnd Sub\n\n'
             '(&H8000ffff) Error in conversion when attempting to process the parameter value\n'
             '(Example.Setter)(Line:2)')


@pytest.fixture
def case(tmp_path, monkeypatch):
    manager, ref, runtime, record = fixture(tmp_path)
    runtime.backend = 'cst'
    path, neighbor = record['path'], str(tmp_path / 'other.cst')
    expected = file_digest(path)
    identity = {'pid': 424242, 'creation_time': '42'}
    failed = {'job_id': 'job-failed', 'session_id': ref['session_id'], 'sequence': 1,
              'operation': 'history', 'params': {'domain': 'schematic', 'project_id': 'main'}}
    error = {'code': 'session_operation_failed', 'details': {'diagnostics': {
        'stage': 'history.submit_schematic', 'operation': 'history', 'job_id': 'job-failed',
        'exception_type': 'RuntimeError', 'exception_module': 'builtins', 'message': VBA_ERROR}}}
    state = runtime.state()
    _finish_failed_job(failed, error, state)
    store.write(runtime.folder / 'session.json', state)
    runtime.update(environment=identity, uncertain_jobs=[])
    journal = runtime.folder / 'jobs/job-failed.json'
    store.write(journal, failed)
    events = []
    opened = [path, neighbor]

    def close():
        events.append('close-target')
        opened.remove(path)

    def reopen(actual):
        assert actual == path
        events.append('open-target')
        opened.append(path)
        return fresh

    handle = SimpleNamespace(filename=lambda: path, close=close, schematic=SimpleNamespace(
        GetNumberOfParameters=lambda: 1, GetParameterName=lambda _: 'shape',
        GetParameterSValue=lambda _: 'new value'))
    fresh = SimpleNamespace(filename=lambda: path)
    de = SimpleNamespace(pid=identity['pid'], list_open_projects=lambda: opened[:],
                         get_open_project=lambda target: handle if target == path else pytest.fail('foreign tab'),
                         open_project=reopen, close=lambda: pytest.fail('whole DE close'))
    runtime.app = SimpleNamespace(project=de, cst_file=handle)
    runtime.handles['main'] = handle
    runtime.project = lambda *_: pytest.fail('general project recovery')
    runtime.environment = lambda: pytest.fail('general DE recovery')
    runtime.save = lambda *_: pytest.fail('save partial changes')
    monkeypatch.setattr(store, 'alive', lambda observed: observed == identity)
    monkeypatch.setattr(dialogs, 'check_dialogs', lambda label, *, pid: None if pid == identity['pid']
                        else pytest.fail('unscoped dialog check'))
    job = {'job_id': 'job-recovery', 'session_id': ref['session_id'], 'sequence': 2,
           'operation': 'recover_schematic_history', 'params': {
               'project_id': 'main', 'failed_job_id': failed['job_id'], 'expected_digest': expected,
               'confirm_idle': True, 'action': 'inspect', 'parameter_names': ['shape', 'missing']}}
    return SimpleNamespace(runtime=runtime, job=job, failed=failed, journal=journal, path=path,
                           neighbor=neighbor, opened=opened, events=events, fresh=fresh, de=de)


def rollback(case):
    p = case.job['params']
    p.pop('parameter_names', None)
    p.update(action='rollback', confirm_discard=True, review_note='Discard the failed schematic stage')


def test_review_reads_dirty_schematic_without_mutating(case):
    before = case.journal.read_bytes()
    assert case.failed['completion_evidence']['schematic_call_state'] == 'returned_native_vba_error'
    out = case.runtime.execute(case.job)
    assert out['parameters'] == {'shape': 'new value', 'missing': None}
    assert out['native_readback_verified'] is True
    assert out['session_state'] == 'needs_reconcile'
    assert case.events == [] and case.journal.read_bytes() == before


def test_rollback_closes_only_owned_tab_and_reopens_saved_digest(case):
    rollback(case)
    before = case.journal.read_bytes()
    out = case.runtime.execute(case.job)
    assert case.events == ['close-target', 'open-target']
    assert set(case.opened) == {case.path, case.neighbor}
    assert case.runtime.handles['main'] is case.fresh
    assert out['reopened'] and out['saved_digest'] == file_digest(case.path)
    assert case.runtime.state()['status'] == 'needs_reconcile'
    assert case.journal.read_bytes() == before


@pytest.mark.parametrize('problem', ['foreign-job', 'unknown-job', 'disk', 'busy', 'transport',
                                     'monitor', 'other-fence', 'wrong-de', 'missing-tab', 'no-discard'])
def test_rollback_refuses_unsafe_or_unproven_state(case, problem):
    rollback(case)
    state = case.runtime.state()
    if problem == 'foreign-job':
        case.failed['session_id'] = 'foreign'
    elif problem == 'unknown-job':
        case.failed['status'] = 'needs_reconcile'
    elif problem == 'disk':
        Path(case.path).write_bytes(b'changed')
    elif problem == 'busy':
        store.write(case.runtime.folder / 'jobs/job-running.json', {'job_id': 'other', 'status': 'running'})
    elif problem == 'transport':
        case.failed['error']['details']['diagnostics']['message'] = 'Connection lost after submission'
        state['last_error'] = case.failed['error']
    elif problem == 'monitor':
        case.failed['error']['details']['session_monitor'] = {'failure_latched': True}
        state['last_error'] = case.failed['error']
    elif problem == 'other-fence':
        state['last_error'] = {'code': 'other_failure'}
    elif problem == 'wrong-de':
        case.de.pid += 1
    elif problem == 'missing-tab':
        case.opened.remove(case.path)
    else:
        case.job['params']['confirm_discard'] = False
    store.write(case.runtime.folder / 'session.json', state)
    store.write(case.journal, case.failed)
    with pytest.raises(ServiceError):
        case.runtime.execute(case.job)
    assert case.events == []


def test_close_failure_is_fenced_and_never_reopened(case):
    rollback(case)

    def fail_close():
        case.events.append('close-raised')
        raise RuntimeError('connection dropped')

    case.runtime.handles['main'].close = fail_close
    with pytest.raises(ServiceError) as exc:
        case.runtime.execute(case.job)
    assert exc.value.code == 'session_schematic_rollback_unverified'
    assert case.events == ['close-raised']
    state = case.runtime.state()
    _finish_failed_job(case.job, exc.value.to_dict(), state)
    assert state['status'] == 'needs_reconcile'
    assert state['last_error']['code'] == 'session_schematic_rollback_unverified'


def test_digest_change_after_close_stops_before_reopen(case):
    rollback(case)
    handle = case.runtime.handles['main']
    close = handle.close

    def close_with_disk_change():
        close()
        Path(case.path).write_bytes(b'changed during close')

    handle.close = close_with_disk_change
    with pytest.raises(ServiceError) as exc:
        case.runtime.execute(case.job)
    assert exc.value.code == 'session_schematic_rollback_unverified'
    assert exc.value.details['close_returned'] is True
    assert case.events == ['close-target']


def test_manager_queues_recovery_and_keeps_write_fence(tmp_path):
    manager = SessionManager(str(tmp_path.resolve()))
    ref = manager.ensure('recovery-test', 'allocate')
    Runtime(tmp_path / ref['session_id'], 'cst').update(status='needs_reconcile')
    manager._launch = lambda *_: None
    args = (ref['session_id'], ref['credential'])
    params = dict(project_id='p', failed_job_id='job-original', expected_digest='a' * 64,
                  action='inspect', confirm_idle=True, parameter_names=['shape'])
    original = manager.submit(*args, 'inspect-original', 'recover_schematic_history', params)
    assert original['status'] == 'queued'
    assert manager.submit(*args, 'inspect-original', 'recover_schematic_history', params) == original
    with pytest.raises(ServiceError) as exc:
        manager.submit(*args, 'write', 'set_parameters', {'project_id': 'p', 'values': {'shape': 1}})
    assert exc.value.code == 'session_needs_reconcile'


def test_sdk_boundary_marks_return_even_when_vba_echo_is_truncated(case):
    def fail(*args, **kwargs):
        raise RuntimeError(VBA_ERROR.replace('Sub Main\n', 'Sub Main\n' + ('Example.LongLine\n' * 300)))

    case.runtime.handles['main'].schematic.execute_vba_code = fail
    case.runtime.project = lambda _: (case.runtime.app, {})
    job = dict(operation='history', params=payload('schematic'), job_id='job-long')
    with pytest.raises(ServiceError) as exc:
        case.runtime.execute(job)
    assert exc.value.details['diagnostics']['message_truncated'] is True
    state = case.runtime.state()
    _finish_failed_job(job, exc.value.to_dict(), state)
    assert job['completion_evidence']['schematic_call_state'] == 'returned_native_vba_error'
    assert state['status'] == 'needs_reconcile'
