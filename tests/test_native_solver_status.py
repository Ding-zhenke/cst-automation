from pathlib import Path
from types import SimpleNamespace

import pytest

from tpc_service.errors import ServiceError


def test_status_fields_preserve_independent_native_values(tmp_path):
    from cst_solver.solver_status import read_native_solver_status
    path = tmp_path / 'model.cst'
    model = SimpleNamespace(get_active_solver_name=lambda **kw: 'HF Frequency Domain',
        is_solver_running=lambda **kw: False, get_solver_run_info=lambda **kw: {'state': 'SUCCESS'})
    app = SimpleNamespace(cst_file=SimpleNamespace(filename=lambda: str(path), model3d=model))
    result = read_native_solver_status(app, expected_project=path)
    fields = result['fields']
    assert fields['active_solver_name']['value'] == 'HF Frequency Domain'
    assert fields['solver_running']['value'] is False
    assert fields['solver_run_info']['raw'] == {'state': 'SUCCESS'}
    assert all(row['status'] == 'read' and row['observed_at'] and row['source'] for row in fields.values())
    assert result['direct_solver_verified'] is False and result['whole_sequence_idle'] == 'unknown'
    assert result['solver_verified'] is False


@pytest.mark.parametrize('raw,expected', [(None, 'empty'), ('', 'empty'), (0, 'invalid'), ('False', 'invalid')])
def test_invalid_running_value_is_not_silent_success(tmp_path, raw, expected):
    from cst_solver.solver_status import read_native_solver_status
    path = tmp_path / 'model.cst'
    model = SimpleNamespace(get_active_solver_name=lambda **kw: '', is_solver_running=lambda **kw: raw,
                            get_solver_run_info=lambda **kw: None)
    app = SimpleNamespace(cst_file=SimpleNamespace(filename=lambda: str(path), model3d=model))
    fields = read_native_solver_status(app, expected_project=path)['fields']
    assert fields['solver_running']['status'] == expected and fields['solver_running']['raw'] == raw
    assert fields['active_solver_name']['status'] == 'empty'
    assert fields['solver_run_info']['status'] == 'empty'


def test_missing_getter_and_exception_remain_distinct(tmp_path):
    from cst_solver.solver_status import read_native_solver_status
    def fail(**kwargs): raise TimeoutError('native timeout')
    model = SimpleNamespace(is_solver_running=fail, get_solver_run_info=lambda **kw: ['bad'])
    path = tmp_path / 'model.cst'
    app = SimpleNamespace(cst_file=SimpleNamespace(filename=lambda: str(path), model3d=model))
    fields = read_native_solver_status(app, expected_project=path)['fields']
    assert fields['active_solver_name']['status'] == 'unsupported'
    assert fields['solver_running']['status'] == 'error' and 'native timeout' in fields['solver_running']['error']
    assert fields['solver_run_info']['status'] == 'invalid' and fields['solver_run_info']['raw'] == ['bad']


def test_mismatched_project_refused_before_any_getter(tmp_path):
    from cst_solver.solver_status import read_native_solver_status
    def forbidden(**kwargs): pytest.fail('must not call native getters')
    app = SimpleNamespace(cst_file=SimpleNamespace(filename=lambda: str(tmp_path / 'other.cst'),
          model3d=SimpleNamespace(is_solver_running=forbidden)))
    with pytest.raises(ValueError, match='project'):
        read_native_solver_status(app, expected_project=tmp_path / 'expected.cst')


def test_changed_project_during_getters_refuses_observation(tmp_path):
    from cst_solver.solver_status import read_native_solver_status
    path = tmp_path / 'model.cst'
    identities = iter([str(path), str(tmp_path / 'other.cst')])
    model = SimpleNamespace(get_active_solver_name=lambda **kw: 'solver', is_solver_running=lambda **kw: False,
                            get_solver_run_info=lambda **kw: {'state': 'running'})
    app = SimpleNamespace(cst_file=SimpleNamespace(filename=lambda: next(identities), model3d=model))
    with pytest.raises(ValueError, match='changed'):
        read_native_solver_status(app, expected_project=path)


def test_inspect_status_requires_exact_read_review_and_no_launch(tmp_path, monkeypatch):
    from tpc_service.sessions.manager import SessionManager
    manager = SessionManager(tmp_path, backend='cst')
    ref = manager.ensure('status-bounded', 'one')
    monkeypatch.setattr(manager, '_launch', lambda *a, **k: pytest.fail('must not launch worker'))
    with pytest.raises(ServiceError):
        manager.submit(ref['session_id'], ref['credential'], 'request', 'inspect',
                       {'project_id': 'p', 'native_readback': True, 'native_solver_status': True})


@pytest.mark.parametrize('worker', [None, {'pid': 123}])
def test_valid_status_request_never_launches_old_or_absent_worker(tmp_path, monkeypatch, worker):
    from tpc_service.sessions.manager import SessionManager
    from tpc_service.sessions.store import read, write
    manager = SessionManager(tmp_path, backend='cst')
    ref = manager.ensure('status-old-worker', 'one')
    folder = tmp_path / ref['session_id']; state = read(folder / 'session.json')
    state.update(status='ready', worker=worker, worker_capabilities=[])
    write(folder / 'session.json', state)
    monkeypatch.setattr('tpc_service.sessions.manager.alive', lambda identity: True)
    monkeypatch.setattr(manager, '_launch', lambda *a, **k: pytest.fail('must not launch worker'))
    params = {'project_id': 'p', 'native_readback': True, 'native_solver_status': True,
              'read_only_review': True, 'confirm_idle': True, 'expected_digest': '0' * 64}
    with pytest.raises(ServiceError, match='compatible existing worker'):
        manager.submit(ref['session_id'], ref['credential'], 'request', 'inspect', params)


def test_status_review_refuses_missing_owned_handle_without_attach(tmp_path, monkeypatch):
    import hashlib
    from tpc_service.sessions.read_review import inspect_saved_geometry
    from cst_solver import dialogs, environment
    path = tmp_path / 'model.cst'; path.write_bytes(b'baseline')
    sha = hashlib.sha256(b'baseline').hexdigest()
    state = {'status': 'ready', 'uncertain_jobs': [], 'environment': {'pid': 5},
             'projects': {'p': {'project_id': 'p', 'path': str(path), 'saved': True, 'saved_digest': sha}}}
    runtime = SimpleNamespace(backend='cst', folder=tmp_path, app=SimpleNamespace(project=object()),
                              handles={}, state=lambda: state)
    params = {'project_id': 'p', 'native_readback': True, 'native_solver_status': True,
              'read_only_review': True, 'confirm_idle': True, 'expected_digest': sha}
    monkeypatch.setattr('tpc_service.sessions.store.alive', lambda identity: True)
    monkeypatch.setattr(dialogs, 'check_dialogs', lambda **kw: None)
    monkeypatch.setattr(environment, 'environment_pid', lambda project: 5)
    monkeypatch.setattr('tpc_service.sessions.read_review.borrow_open_project', lambda *a: pytest.fail('must not attach'))
    with pytest.raises(ServiceError, match='no attach'):
        inspect_saved_geometry(runtime, {'job_id': 'job', 'params': params})


def test_status_review_only_uses_owned_sdk_and_does_not_claim_whole_readback(tmp_path, monkeypatch):
    import hashlib
    from tpc_service.sessions.read_review import inspect_saved_geometry
    from cst_solver import dialogs, environment
    path = tmp_path / 'model.cst'; path.write_bytes(b'baseline')
    sha = hashlib.sha256(b'baseline').hexdigest()
    model = SimpleNamespace(get_active_solver_name=lambda **kw: 'HF Frequency Domain',
                            is_solver_running=lambda **kw: False,
                            get_solver_run_info=lambda **kw: {'state': 'SUCCESS'})
    handle = SimpleNamespace(filename=lambda: str(path), model3d=model)
    app = SimpleNamespace(project=object(), cst_file=handle)
    state = {'status': 'ready', 'uncertain_jobs': [], 'environment': {'pid': 5},
             'projects': {'p': {'project_id': 'p', 'path': str(path), 'saved': True, 'saved_digest': sha}}}
    runtime = SimpleNamespace(backend='cst', folder=tmp_path, app=app, handles={'p': handle}, state=lambda: state)
    params = {'project_id': 'p', 'native_readback': True, 'native_solver_status': True,
              'read_only_review': True, 'confirm_idle': True, 'expected_digest': sha}
    monkeypatch.setattr('tpc_service.sessions.store.alive', lambda identity: True)
    monkeypatch.setattr(dialogs, 'check_dialogs', lambda **kw: None)
    monkeypatch.setattr(environment, 'environment_pid', lambda project: 5)
    monkeypatch.setattr('tpc_service.sessions.read_review.borrow_open_project', lambda *a: pytest.fail('must not attach'))
    result = inspect_saved_geometry(runtime, {'job_id': 'job', 'params': params})
    assert result['readback_verified'] is False and result['idle_verified'] is False
    assert result['native_readback']['solver_status']['fields']['solver_running']['value'] is False
