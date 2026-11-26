import hashlib
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from tpc_service.errors import ServiceError
from tpc_service.sessions import model_exports as exports
from tpc_service.sessions.manager import SessionManager
from tpc_service.sessions.native import Runtime
from tpc_service.sessions.store import process_identity, read, write
from tpc_service.sessions.worker import _finish_failed_job


def test_export_uses_registered_project_and_returns_deduplicated_artifact(tmp_path, monkeypatch):
    manager = SessionManager(tmp_path)
    ref = manager.ensure('export-test', 'allocate')
    sid, credential = ref['session_id'], ref['credential']
    runtime = Runtime(tmp_path / sid, 'cst')
    path = tmp_path / 'saved.cst'
    path.write_bytes(b'project')
    state = runtime.state()
    project = dict(project_id='p', path=str(path), saved_digest=hashlib.sha256(b'project').hexdigest())
    state.update(status='ready', worker=process_identity(os.getpid()), projects={'p': project})
    write(runtime.folder / 'session.json', state)
    args = (sid, credential, 'capture', exports.VIEW, {'project_id': 'p'})
    with pytest.raises(ServiceError, match='compatible existing worker'):
        manager.submit(*args)
    state['worker_capabilities'] = [exports.CAPABILITY]
    write(runtime.folder / 'session.json', state)
    monkeypatch.setattr(manager, '_launch', lambda *a: pytest.fail('Export launched a worker'))
    job = manager.submit(*args)
    def borrow(rt, identity, filename):
        assert filename == str(path)
        handle = SimpleNamespace(activate=lambda: None, model3d=SimpleNamespace(is_solver_running=lambda timeout: False))
        app = SimpleNamespace(capture_model_view_png=lambda dest: Path(dest).write_bytes(b'checked-png'))
        return app, handle, {}
    monkeypatch.setattr(exports, 'borrow_open_project', borrow)
    receipt = runtime.execute(job)
    assert receipt['path'] == str(runtime.folder / 'exports' / job['job_id'] / 'model.png')
    assert receipt['sha256'] == hashlib.sha256(b'checked-png').hexdigest()
    assert manager.submit(*args)['job_id'] == job['job_id']
    assert read(runtime.folder / 'session.json')['projects']['p'] == project


@pytest.mark.parametrize('changes', [
    {'tree_path': 'Components'}, {'step': False}, {'step': float('inf')},
    {'tree_path': '2D/3D Results\\E\nbad'}, {'path': 'other.cst'},
])
def test_invalid_field_options_are_rejected_before_queue(tmp_path, changes):
    manager = SessionManager(tmp_path)
    ref = manager.ensure('export-test', 'allocate')
    params = {'project_id': 'p', 'tree_path': '2D/3D Results\\E-Field\\E', **changes}
    with pytest.raises(ServiceError) as exc:
        manager.submit(ref['session_id'], ref['credential'], 'field', exports.FIELD, params)
    assert exc.value.code == 'invalid_session_argument'
    assert not list((tmp_path / ref['session_id'] / 'jobs').glob('*.json'))


def test_missing_field_does_not_require_project_reconciliation():
    job = {'operation': exports.FIELD, 'params': {'project_id': 'p'}, 'job_id': 'job-demo'}
    state = {'status': 'ready'}
    _finish_failed_job(job, {'code': 'session_operation_failed', 'message': 'missing leaf'}, state)
    assert state['status'] == 'ready'
    assert job['status'] == 'failed'
