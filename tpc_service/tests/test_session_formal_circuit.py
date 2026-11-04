"""Borrowed circuit routing for one authorized formal file; no CST SDK."""
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from tpc_service.errors import ServiceError
from tpc_service.sessions.operations import circuit


def session(tmp_path):
    folder = tmp_path/'session'; folder.mkdir()
    project = tmp_path/'formal'/'ReviewedDevice.cst'; project.parent.mkdir(); project.write_bytes(b'synthetic')
    record = {'project_id': 'p', 'path': str(project), 'saved': True,
              'path_authorization': {'working_path': str(project), 'operation': 'adopt_project'}}
    state = {'projects': {'p': record}}
    runtime = SimpleNamespace(folder=folder, state=lambda: state, update=lambda **kw: state.update(kw))
    api = SimpleNamespace(inspect=Mock(return_value={'blocks': []}), run_checked=Mock(return_value={
        'status': 'succeeded', 'run_token': 'synthetic', 'saved': True,
        'task_name': 'HB', 'mode': 'network'}))
    app = SimpleNamespace(circuit=api, close=Mock())
    return runtime, app, record


@pytest.mark.parametrize('operation', ['inspect', 'run_task', 'read_results'])
def test_authorized_external_project_reaches_existing_circuit_handler(tmp_path, monkeypatch, operation):
    runtime, app, record = session(tmp_path)
    readers = []
    class Reader:
        def __init__(self, path): readers.append(path)
        def export_csv(self, tree_path, destination, *, run_id):
            assert destination == str(runtime.folder/'export.csv')
            assert run_id == 'Schematic:RunID:1'
            return {'metadata': {'run_id': run_id}, 'artifacts': []}
    import cst_solver.circuit.results as results
    monkeypatch.setattr(results, 'CircuitResult', Reader)
    settings = {'operation': operation}
    if operation == 'run_task':
        settings.update(task_name='HB', mode='network', expected_results=['actual-path'])
    if operation == 'read_results':
        settings.update(tree_path='Tasks\\HB\\actual-path', run_id='Schematic:RunID:1', destination='export.csv')
    result = circuit(runtime, app, record, {'project_id': 'p',
        'kind': 'solve' if operation == 'run_task' else 'build', 'settings': settings})
    assert result['ok'] is True
    if operation == 'inspect': app.circuit.inspect.assert_called_once()
    if operation == 'run_task': app.circuit.run_checked.assert_called_once()
    if operation == 'read_results': assert readers == [record['path']]
    app.close.assert_not_called()


@pytest.mark.parametrize('problem', ['missing_grant', 'foreign_grant', 'unregistered', 'path_changed'])
def test_external_scope_cannot_be_forged_or_reused_for_another_project(tmp_path, problem):
    runtime, app, record = session(tmp_path)
    if problem == 'missing_grant': record.pop('path_authorization')
    if problem == 'foreign_grant': record['path_authorization']['working_path'] = str(tmp_path/'other.cst')
    if problem == 'unregistered': runtime.state()['projects'].clear()
    if problem == 'path_changed': record = dict(record, path=str(tmp_path/'different.cst'))
    with pytest.raises(ServiceError):
        circuit(runtime, app, record, {'project_id': 'p', 'settings': {'operation': 'inspect'}})
    app.circuit.inspect.assert_not_called()
    app.circuit.run_checked.assert_not_called()


def test_formal_project_grant_does_not_authorize_external_export(tmp_path):
    runtime, app, record = session(tmp_path)
    destination = tmp_path/'formal'/'outside.csv'
    with pytest.raises(ServiceError) as caught:
        circuit(runtime, app, record, {'project_id': 'p', 'settings': {'operation': 'read_results',
            'tree_path': 'Tasks\\HB\\actual-path', 'run_id': 'Schematic:RunID:1', 'destination': str(destination)}})
    assert caught.value.code == 'session_circuit_failed'
    assert not destination.exists()


def test_default_circuit_service_still_rejects_external_project(tmp_path):
    from tpc_service.circuit import register_circuit_handlers
    runtime, app, record = session(tmp_path)
    handlers = {}; factory = Mock(return_value=app)
    service = SimpleNamespace(workdir=str(runtime.folder), register_workflow=lambda name, routes, **kw: handlers.update(routes))
    register_circuit_handlers(service, app_factory=factory)
    result = handlers['build'](project=record, params={'operation': 'inspect',
        'authorized_project_path': record['path']}, job={'kind': 'build'}, backend=None)
    assert result['ok'] is False
    factory.assert_not_called()


def test_trusted_host_grant_is_bound_to_one_exact_project(tmp_path):
    from tpc_service.circuit import register_circuit_handlers
    runtime, app, record = session(tmp_path)
    handlers = {}; factory = Mock(return_value=app)
    service = SimpleNamespace(workdir=str(runtime.folder), register_workflow=lambda name, routes, **kw: handlers.update(routes))
    register_circuit_handlers(service, app_factory=factory, authorized_project_path=record['path'])
    other = dict(record, path=str(tmp_path/'another.cst'))
    result = handlers['build'](project=other, params={'operation': 'inspect'}, job={'kind': 'build'}, backend=None)
    assert result['ok'] is False
    factory.assert_not_called()
