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


def test_session_run_parameter_query_is_bound_and_does_not_save_or_close(tmp_path, monkeypatch):
    runtime, app, record = session(tmp_path)
    app.cst_file = object()
    from cst_solver.circuit import native
    from tpc_service.sessions.operations import execute
    from tpc_service.sessions import store
    runtime.backend = 'cst'; runtime.app = app; runtime.handles = {'p': app.cst_file}
    runtime.check_saved = Mock(); runtime.project = Mock()
    monkeypatch.setattr(store, 'alive', lambda identity: True)
    reader = Mock(return_value={'parameters': {'tone': 2.5},
                               'artifact_path': str(runtime.folder/'receipt.txt'), 'native_bridge_verified': False})
    monkeypatch.setattr(native, 'read_project_run_parameters', reader)
    result = execute(runtime, {'operation': 'circuit', 'params': {'project_id': 'p', 'kind': 'build',
        'settings': {'operation': 'read_run_parameters', 'result_id': 'Schematic:RunID:3', 'confirm_idle': True}}})
    assert result['ok'] is True and result['saved'] is False
    assert result['result_summary']['run_parameters']['native_bridge_verified'] is False
    reader.assert_called_once_with(app.cst_file, 'Schematic:RunID:3', expected_project_path=record['path'],
        receipt_root=runtime.folder/'run_parameter_queries', confirm_idle=True)
    app.close.assert_not_called()
    runtime.project.assert_not_called()
    runtime.check_saved.assert_called_once_with(record)


def test_sp_query_reuses_owned_cached_project_without_save(tmp_path, monkeypatch):
    from cst_solver.circuit import native
    from tpc_service.sessions.operations import execute
    from tpc_service.sessions import store
    runtime, app, record = session(tmp_path)
    runtime.state()['worker_capabilities'] = ['sp-impedance-read-v1']
    runtime.backend = 'cst'; runtime.app = app; app.cst_file = object()
    runtime.handles = {'p': app.cst_file}; runtime.check_saved = Mock(); runtime.project = Mock()
    monkeypatch.setattr(store, 'alive', lambda identity: True)
    reader = Mock(return_value={'artifact_path': str(runtime.folder/'receipt.txt'), 'native_bridge_verified': False})
    monkeypatch.setattr(native, 'read_project_sp_impedances', reader)
    result = execute(runtime, {'operation': 'circuit', 'params': {'project_id': 'p', 'kind': 'build',
        'settings': {'operation': 'read_sp_impedances', 'task_name': 'SP', 'ports': ['P1', 'P2'], 'confirm_idle': True}}})
    assert result['ok'] and not result['saved']
    assert result['result_summary']['sp_impedances']['native_bridge_verified'] is False
    runtime.project.assert_not_called(); app.close.assert_not_called()
    reader.assert_called_once_with(app.cst_file, 'SP', ['P1', 'P2'], expected_project_path=record['path'],
        receipt_root=runtime.folder/'sp_impedance_queries', confirm_idle=True)


def test_sp_query_rejects_missing_worker_capability_before_acquisition(tmp_path):
    from tpc_service.sessions.operations import execute
    runtime, app, record = session(tmp_path)
    runtime.project = Mock()
    with pytest.raises(ServiceError) as exc:
        execute(runtime, {'operation': 'circuit', 'params': {'project_id': 'p', 'kind': 'build',
            'settings': {'operation': 'read_sp_impedances', 'task_name': 'SP', 'ports': ['P1'], 'confirm_idle': True}}})
    assert exc.value.code == 'workflow_worker_upgrade_required'
    runtime.project.assert_not_called()


def test_sp_query_never_launches_missing_worker(tmp_path, monkeypatch):
    from tpc_service.sessions import manager as module
    manager = module.SessionManager(str(tmp_path), backend='fake')
    ref = manager.ensure('sp-read', 'ensure')
    monkeypatch.setattr(manager, '_launch', lambda *a: pytest.fail('No worker launch'))
    with pytest.raises(ServiceError) as exc:
        manager.submit(ref['session_id'], ref['credential'], 'r', 'circuit',
            {'project_id': 'p', 'kind': 'build', 'settings': {'operation': 'read_sp_impedances',
             'task_name': 'SP', 'ports': ['P1'], 'confirm_idle': True}})
    assert exc.value.code == 'session_query_requires_open_project'


def test_parameter_query_requires_idle_assertion_before_opening_project(tmp_path):
    from tpc_service.circuit import register_circuit_handlers
    runtime, app, record = session(tmp_path)
    handlers = {}; factory = Mock(return_value=app)
    service = SimpleNamespace(workdir=str(runtime.folder), register_workflow=lambda name, routes, **kw: handlers.update(routes))
    register_circuit_handlers(service, app_factory=factory, authorized_project_path=record['path'], borrowed_project=True)
    out = handlers['build'](project=record, params={'operation': 'read_run_parameters',
        'result_id': 'Schematic:RunID:3'}, job={'kind': 'build'}, backend=None)
    assert out['ok'] is False
    factory.assert_not_called()


def test_generic_parameter_query_cannot_open_or_close_a_project(tmp_path):
    from tpc_service.circuit import register_circuit_handlers
    runtime, app, record = session(tmp_path)
    handlers = {}; factory = Mock(return_value=app)
    service = SimpleNamespace(workdir=str(runtime.folder), register_workflow=lambda name, routes, **kw: handlers.update(routes))
    register_circuit_handlers(service, app_factory=factory, authorized_project_path=record['path'])
    out = handlers['build'](project=record, params={'operation': 'read_run_parameters',
        'result_id': 'Schematic:RunID:3', 'confirm_idle': True, 'borrowed_project': True}, job={'kind': 'build'}, backend=None)
    assert out['ok'] is False
    factory.assert_not_called(); app.close.assert_not_called()


@pytest.mark.parametrize('issue', ['no_app', 'no_handle', 'closed', 'dead'])
def test_query_does_not_restore_open_or_connect_a_missing_cached_project(tmp_path, monkeypatch, issue):
    from tpc_service.sessions.operations import execute
    from tpc_service.sessions import store
    runtime, app, record = session(tmp_path)
    runtime.backend = 'cst'; runtime.app = app; runtime.handles = {'p': object()}
    runtime.project = Mock()
    if issue == 'no_app': runtime.app = None
    if issue == 'no_handle': runtime.handles.clear()
    if issue == 'closed': record['tab_closed'] = True
    monkeypatch.setattr(store, 'alive', lambda identity: issue != 'dead')
    with pytest.raises(ServiceError):
        execute(runtime, {'operation': 'circuit', 'params': {'project_id': 'p', 'kind': 'build',
            'settings': {'operation': 'read_run_parameters', 'result_id': 'Schematic:RunID:3', 'confirm_idle': True}}})
    runtime.project.assert_not_called()

def test_position_owned_session_routes_to_borrowed_app(tmp_path):
    runtime, app, record = session(tmp_path)
    app.circuit.set_position = Mock(return_value={'readback':[51000,52000]})
    app.save = Mock()
    result = circuit(runtime, app, record, {'project_id':'p', 'kind':'build',
        'settings':{'operation':'set_position','kind':'Block','name':'D1','position':[51000,52000]}})
    assert result['ok']
    app.circuit.set_position.assert_called_once_with('Block','D1',[51000,52000])
    app.save.assert_called_once()
    app.close.assert_not_called()

def test_old_worker_position_is_rejected_before_access():
    from tpc_service.sessions.operations import execute
    runtime=SimpleNamespace(state=lambda: {'worker_capabilities': []})
    with pytest.raises(ServiceError) as caught:
        execute(runtime, {'operation':'circuit','params':{'settings':{'operation':'set_position'}}})
    assert caught.value.code == 'workflow_worker_upgrade_required'
