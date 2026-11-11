"""LF settings remain sparse, strict and gated before native access."""
import hashlib
import json
from types import SimpleNamespace
import pytest
from cst_automation.fd_linear import linear_solver_code
from tpc_service.errors import ServiceError
from tpc_service.sessions.model_api import dispatch


@pytest.mark.parametrize('key, command', [
    ('low_frequency_stabilization', 'LowFrequencyStabilization'),
    ('allow_float_direct_solver', 'SetAllowFloatDirectSolver')])
@pytest.mark.parametrize('value', [False, True])
def test_sparse_bool_emits_only_requested_control(key, command, value):
    assert linear_solver_code({key: value}) == f'With FDSolver\n .{command} "{value}"\nEnd With'


@pytest.mark.parametrize('key', ['low_frequency_stabilization', 'allow_float_direct_solver'])
@pytest.mark.parametrize('value', [None, 0, 1, 'False', 'True', [], {}])
def test_invalid_lf_field_rejects_entire_batch_before_first_native_write(key, value):
    app = SimpleNamespace(new_component=lambda *a: pytest.fail('Earlier native write'))
    with pytest.raises(ServiceError):
        dispatch(app, [{'method': 'new_component', 'args': ['never']},
                       {'method': 'configure_fd_linear_solver', 'args': [{key: value}]}])


def calls_for(keyword=False, mixed=False):
    settings = {'low_frequency_stabilization': True, 'allow_float_direct_solver': False}
    call = {'method': 'configure_fd_linear_solver',
            **({'kwargs': {'settings': settings}} if keyword else {'args': [settings]})}
    return ([{'method': 'new_component', 'args': ['never']}] if mixed else []) + [call]


@pytest.mark.parametrize('keyword', [False, True])
@pytest.mark.parametrize('mixed', [False, True])
def test_old_worker_refuses_before_queue_and_launch(tmp_path, monkeypatch, keyword, mixed):
    from tpc_service.sessions import manager as module
    from tpc_service.sessions.store import read, write
    manager = module.SessionManager(str(tmp_path), backend='fake')
    ref = manager.ensure('lf', 'ensure'); folder = tmp_path / ref['session_id']
    state = read(folder / 'session.json')
    state.update(status='ready', worker={'pid': 123}, worker_capabilities=['solver-settings-no-rebuild-v1'])
    write(folder / 'session.json', state)
    monkeypatch.setattr(module, 'alive', lambda *a: True)
    monkeypatch.setattr(manager, '_launch', lambda *a: pytest.fail('No worker launch'))
    calls = calls_for(keyword, mixed)
    params = dict(project_id='p', stage_id='lf', calls=calls,
        preview_digest=hashlib.sha256(json.dumps(calls, sort_keys=True, ensure_ascii=False).encode()).hexdigest())
    with pytest.raises(ServiceError) as exc:
        manager.submit(ref['session_id'], ref['credential'], 'lf', 'model_api', params)
    assert exc.value.code == 'workflow_worker_upgrade_required'
    assert not list((folder / 'jobs').glob('*.json'))


@pytest.mark.parametrize('keyword', [False, True])
def test_execution_rechecks_capability_before_project_access(tmp_path, keyword):
    from tpc_service.sessions.operations import execute
    runtime = SimpleNamespace(folder=tmp_path, backend='cst', state=lambda: {'worker_capabilities': []},
        project=lambda *a: pytest.fail('No native project access'))
    job = {'operation': 'model_api', 'params': {'project_id': 'p', 'calls': calls_for(keyword)}}
    with pytest.raises(ServiceError) as exc:
        execute(runtime, job)
    assert exc.value.code == 'workflow_worker_upgrade_required'
    assert job['workflow_preflight_rejected'] is True


def test_omitted_lf_fields_preserve_previous_command():
    assert linear_solver_code({'solver_type': 'Direct', 'tet_order': 'Second'}) == (
        'With FDSolver\n .Type "Direct"\n .OrderTet "Second"\nEnd With')


@pytest.mark.parametrize('valid', [False, True])
def test_mcp_lf_validates_before_launch(tmp_path, monkeypatch, valid):
    from cst_mcp import tools
    from cst_mcp.session_tools import register_session_tools
    from tpc_service.sessions import SessionManager
    for name in ('TOOL_SPECS', 'HANDLERS', 'READ_TOOLS', 'WRITE_TOOLS'):
        monkeypatch.setattr(tools, name, getattr(tools, name).copy())
    def launch(*a, **kw):
        if not valid:
            pytest.fail('Invalid settings must not launch worker')
    monkeypatch.setattr(SessionManager, '_launch', launch)
    register_session_tools(str(tmp_path.resolve()), backend='fake')
    ref = tools.dispatch('ensure_cst_session', {'binding': 'lf', 'request_id': 'e'})['session']
    calls = calls_for(keyword=True)
    if not valid:
        calls[0]['kwargs']['settings']['low_frequency_stabilization'] = 'True'
    params = dict(project_id='p', stage_id='lf', calls=calls,
        preview_digest=hashlib.sha256(json.dumps(calls, sort_keys=True, ensure_ascii=False).encode()).hexdigest())
    out = tools.dispatch('submit_cst_session_operation', dict(session_id=ref['session_id'],
        credential=ref['credential'], request_id='lf', operation='model_api', params=params))
    assert out['ok'] is valid
    if valid:
        assert out['job']['params']['calls'] == calls
    else:
        assert not list((tmp_path / ref['session_id'] / 'jobs').glob('*.json'))
