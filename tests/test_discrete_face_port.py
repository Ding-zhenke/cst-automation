"""Face-port metadata, picked endpoints and fail-before-native regression tests."""
from types import SimpleNamespace
import hashlib
import json
import pytest
from cst_solver.simulation.ports import PortMixin
from tpc_service.errors import ServiceError
from tpc_service.sessions.model_api import dispatch


def test_face_creator_emits_explicit_picked_points_and_metadata():
    history = []
    app = PortMixin()
    app.cst_file = SimpleNamespace(model3d=SimpleNamespace(add_to_history=lambda *a: history.append(a)))
    dispatch(app, [{'method': 'create_discrete_face_port', 'args': [75, 3],
                    'kwargs': {'label': 'test "P3"', 'monitor': False,
                               'invert_direction': True, 'p1': [1, 2, 3], 'p2': [1, 2, 5]}}])
    code = history[0][1]
    for line in ['.PortNumber "3"', '.Impedance "75"', '.Label "test ""P3"""',
                 '.Monitor "False"', '.InvertDirection "True"', '.CenterEdge "True"',
                 '.SetP1 "True", "1", "2", "3"', '.SetP2 "True", "1", "2", "5"']:
        assert line in code
    assert '.Folder' not in code


def test_legacy_creator_default_picks_are_explicit():
    history = []
    app = PortMixin()
    app.cst_file = SimpleNamespace(model3d=SimpleNamespace(add_to_history=lambda *a: history.append(a)))
    app.discrete_port('Zref', '3', invertdrection=True)
    assert '.SetP1 "True", "0", "0", "0"' in history[0][1]
    assert '.SetP2 "True", "0", "0", "0"' in history[0][1]
    assert '.InvertDirection "True"' in history[0][1]


@pytest.mark.parametrize('bad', [{'monitor': 'False'}, {'invert_direction': 1},
    {'p1': [1, 2]}, {'p2': [0, 0, float('nan')]}, {'p1': ['0"\n.Start', 0, 0]},
    {'label': 'bad\nlabel'}, {'fold': 'unsupported'}, {'r0': 0}, {'id_val': True},
    {'p1': ['1e999', 0, 0]}])
def test_bad_face_arguments_prevent_earlier_batch_write(bad):
    kwargs = dict(r0=50, id_val=3)
    kwargs.update(bad)
    app = SimpleNamespace(new_component=lambda *a: pytest.fail('Earlier native write'))
    with pytest.raises(ServiceError):
        dispatch(app, [{'method': 'new_component', 'args': ['never']},
                       {'method': 'create_discrete_face_port', 'kwargs': kwargs}])


@pytest.mark.parametrize('keyword', [False, True])
def test_old_worker_refuses_face_creator_before_queue(tmp_path, monkeypatch, keyword):
    from tpc_service.sessions import manager as module
    from tpc_service.sessions.store import read, write
    manager = module.SessionManager(str(tmp_path), backend='fake')
    ref = manager.ensure('face', 'ensure')
    folder = tmp_path / ref['session_id']
    state = read(folder / 'session.json')
    state.update(status='ready', worker={'pid': 123}, worker_capabilities=[])
    write(folder / 'session.json', state)
    monkeypatch.setattr(module, 'alive', lambda *a: True)
    monkeypatch.setattr(manager, '_launch', lambda *a: pytest.fail('No launch'))
    call = {'method': 'create_discrete_face_port'}
    call.update({'kwargs': {'r0': 50, 'id_val': 3}} if keyword else {'args': [50, 3]})
    calls = [{'method': 'new_component', 'args': ['never']}, call]
    params = dict(project_id='p', stage_id='face', calls=calls,
                  preview_digest=hashlib.sha256(json.dumps(calls, sort_keys=True, ensure_ascii=False).encode()).hexdigest())
    with pytest.raises(ServiceError) as error:
        manager.submit(ref['session_id'], ref['credential'], 'r', 'model_api', params)
    assert error.value.code == 'workflow_worker_upgrade_required'
    assert not list((folder / 'jobs').glob('*.json'))


def test_execution_rechecks_face_capability_before_native_access(tmp_path):
    from tpc_service.sessions.operations import execute
    runtime = SimpleNamespace(folder=tmp_path, backend='cst', state=lambda: {'worker_capabilities': []},
                              project=lambda *a: pytest.fail('No native acquisition'))
    job = {'operation': 'model_api', 'params': {'project_id': 'p', 'calls': [
        {'method': 'create_discrete_face_port', 'args': [50, 3]}]}}
    with pytest.raises(ServiceError) as error:
        execute(runtime, job)
    assert error.value.code == 'workflow_worker_upgrade_required'
    assert job['workflow_preflight_rejected'] is True


@pytest.mark.parametrize('valid', [False, True])
def test_mcp_face_request_validates_before_launch(tmp_path, monkeypatch, valid):
    from cst_mcp import tools
    from cst_mcp.session_tools import register_session_tools
    from tpc_service.sessions import SessionManager
    for name in ('TOOL_SPECS', 'HANDLERS', 'READ_TOOLS', 'WRITE_TOOLS'):
        monkeypatch.setattr(tools, name, getattr(tools, name).copy())
    def launch(*args, **kwargs):
        if not valid:
            pytest.fail('Invalid request must not launch worker or CST')
    monkeypatch.setattr(SessionManager, '_launch', launch)
    register_session_tools(str(tmp_path.resolve()), backend='fake')
    ref = tools.dispatch('ensure_cst_session', {'binding': 'face', 'request_id': 'ensure'})['session']
    calls = [{'method': 'create_discrete_face_port', 'args': [50, 3],
              'kwargs': {'monitor': False if valid else 'False'}}]
    params = dict(project_id='p', stage_id='face', calls=calls,
                  preview_digest=hashlib.sha256(json.dumps(calls, sort_keys=True, ensure_ascii=False).encode()).hexdigest())
    result = tools.dispatch('submit_cst_session_operation', dict(session_id=ref['session_id'],
        credential=ref['credential'], request_id='r', operation='model_api', params=params))
    assert result['ok'] is valid
    if valid:
        assert result['job']['params']['calls'] == calls
    else:
        assert not list((tmp_path / ref['session_id'] / 'jobs').glob('*.json'))
