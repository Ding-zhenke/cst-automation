"""Contract tests at the native boundary, without starting CST."""
from types import SimpleNamespace

from tpc_service.sessions import SessionManager
from tpc_service.sessions.native import Runtime


def test_native_parameter_stage_uses_existing_parameter_and_validation_api(tmp_path):
    m = SessionManager(str(tmp_path.resolve()), backend='fake')
    b = m.ensure('a', 'a')
    runtime = Runtime(tmp_path / b['session_id'], 'fake')
    record = {'path': str(tmp_path / b['session_id'] / 'p.cst')}
    calls = []
    app = SimpleNamespace(para=lambda name, value: calls.append(('para', name, value)),
                          validate_model=lambda: {'status': 'success', 'messages': [], 'rebuild_ok': True})
    runtime.backend = 'cst'
    runtime.project = lambda project_id: (app, record)
    runtime.save = lambda app, project_id: dict(record, saved_digest='saved')
    result = runtime.execute({'job_id': 'j', 'operation_id': 'stage', 'fingerprint': 'fingerprint',
                              'operation': 'set_parameters', 'params': {'project_id': 'p', 'values': {'a': 3}}})
    assert calls == [('para', 'a', 3)]
    assert result['saved'] is True


def test_native_save_overwrites_only_its_registered_path(tmp_path):
    m = SessionManager(str(tmp_path.resolve()), backend='fake')
    b = m.ensure('a', 'a')
    runtime = Runtime(tmp_path / b['session_id'], 'fake')
    path = tmp_path / b['session_id'] / 'p.cst'
    path.write_bytes(b'old')
    runtime.update(projects={'p': {'path': str(path)}})
    def save(target, *, allow_overwrite=False):
        assert allow_overwrite is True
        assert target == str(path)
        path.write_bytes(b'new')
    runtime.save(SimpleNamespace(save=save), 'p')
