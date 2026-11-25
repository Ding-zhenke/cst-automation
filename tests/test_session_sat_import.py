from types import SimpleNamespace
import pytest
from cst_solver.import_export.io import IOMixin
from tpc_service.errors import ServiceError
from tpc_service.sessions.model_api import dispatch, validate_calls


def test_import_sab_dispatches_real_sat_command(tmp_path):
    source = tmp_path / 'source.sab'
    source.write_bytes(b'fixture')
    history = []
    app = IOMixin()
    app.cst_file = SimpleNamespace(model3d=SimpleNamespace(add_to_history=lambda label, command: history.append(command)))
    dispatch(app, [{'method': 'import_sat', 'args': [str(source)]}])
    assert len(history) == 1
    assert f'.FileName "{source}"' in history[0]
    assert '.TypePECForNewMaterials "True"' in history[0]


@pytest.mark.parametrize('filename,tpn', [('', 'True'), ('relative.sab', 'True'), ('missing.sab', 'True'), ('any.sab', 'True"\n.Read'), ('any.sab', True)])
def test_import_sat_rejects_invalid_inputs_before_dispatch(tmp_path, filename, tpn):
    if filename.startswith('any'):
        filename = str(tmp_path / filename)
        (tmp_path / 'any.sab').touch()
    with pytest.raises(ServiceError):
        validate_calls([{'method': 'import_sat', 'args': [filename, tpn]}])


def test_import_outside_project_directory_is_rejected_before_mutation(tmp_path, monkeypatch):
    from tpc_service.sessions import operations
    project_dir = tmp_path / 'project'
    project_dir.mkdir()
    source = tmp_path / 'outside.sab'
    source.touch()
    app = SimpleNamespace(cst_file={})
    record = {'path': str(project_dir / 'model.cst')}
    runtime = SimpleNamespace(backend='fake', state=lambda: {'projects': {'p': record}},
                              project=lambda _: (app, record))
    monkeypatch.setattr(operations, 'mark_stage', lambda *_: None)
    job = {'operation': 'model_api', 'params': {'project_id': 'p', 'calls': [
        {'method': 'import_sat', 'kwargs': {'filename': str(source)}}]}}
    with pytest.raises(ServiceError) as error:
        operations._execute_operation(runtime, job)
    assert error.value.code == 'invalid_session_argument'
    assert app.cst_file == {}


def test_old_worker_refuses_sat_import_before_enqueue(tmp_path, monkeypatch):
    import hashlib, json
    from tpc_service.sessions import manager as module
    from tpc_service.sessions.store import read, write
    manager = module.SessionManager(str(tmp_path), backend='fake')
    ref = manager.ensure('sat', 'ensure')
    folder = tmp_path / ref['session_id']
    state = read(folder / 'session.json')
    state.update(status='ready', worker={'pid': 123}, worker_capabilities=[])
    write(folder / 'session.json', state)
    monkeypatch.setattr(module, 'alive', lambda *a: True)
    monkeypatch.setattr(manager, '_launch', lambda *a: pytest.fail('unexpected worker launch'))
    source = tmp_path / 'source.sab'; source.touch()
    calls = [{'method': 'import_sat', 'args': [str(source)]}]
    params = dict(project_id='p', stage_id='sat', calls=calls,
                  preview_digest=hashlib.sha256(json.dumps(calls, sort_keys=True, ensure_ascii=False).encode()).hexdigest())
    with pytest.raises(ServiceError) as error:
        manager.submit(ref['session_id'], ref['credential'], 'sat', 'model_api', params)
    assert error.value.code == 'workflow_worker_upgrade_required'
    assert not list((folder / 'jobs').glob('*.json'))


def test_worker_checks_sat_capability_before_project_access(tmp_path):
    from tpc_service.sessions.operations import execute
    source = tmp_path / 'source.sab'; source.touch()
    runtime = SimpleNamespace(folder=tmp_path, backend='cst', state=lambda: {'worker_capabilities': []},
                              project=lambda *a: pytest.fail('unexpected project access'))
    job = {'operation': 'model_api', 'params': {'project_id': 'p', 'calls': [
        {'method': 'import_sat', 'args': [str(source)]}]}}
    with pytest.raises(ServiceError) as error:
        execute(runtime, job)
    assert error.value.code == 'workflow_worker_upgrade_required'
    assert job['workflow_preflight_rejected'] is True
