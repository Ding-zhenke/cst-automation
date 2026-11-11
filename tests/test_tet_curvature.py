"""Bounded modern HF Tet curvature request, validated before any native work."""
import hashlib
import json
from types import SimpleNamespace
import pytest
from cst_solver.mesh.mesh import MeshMixin
from tpc_service.errors import ServiceError
from tpc_service.sessions.model_api import dispatch


@pytest.mark.parametrize('order', [1, 2, 3])
def test_curvature_emits_only_modern_order_and_unverified_receipt(order):
    history = []
    app = SimpleNamespace(cst_file=SimpleNamespace(model3d=SimpleNamespace(
        add_to_history=lambda *a: history.append(a))))
    receipt = MeshMixin.configure_tetrahedral_mesh(app, {'curvature_order': order})
    assert history[0][1].splitlines() == ['MeshSettings.SetMeshType "Tet"',
        f'MeshSettings.Set "CurvatureOrder", "{order}"']
    assert receipt['history_caption'] == history[0][0]
    assert '[sha256:' in history[0][0]
    assert receipt['requested'] == {'curvature_order': order}
    assert receipt['readback_verified'] is receipt['mesh_verified'] is receipt['solver_verified'] is False


@pytest.mark.parametrize('field,value', [
    *[('curvature_order', v) for v in [0, 4, -1, True, 2.0, '2', None, [], {}]],
    *[('curvature_policy', v) for v in ['fixed', 'off', 'manual', 'FixedOrder', '', 0, True, None, [], {}]]])
def test_invalid_curvature_rejects_entire_batch(field, value):
    app = SimpleNamespace(new_component=lambda *a: pytest.fail('Earlier native mutation'))
    with pytest.raises(ServiceError):
        dispatch(app, [{'method': 'new_component', 'args': ['never']},
            {'method': 'configure_tetrahedral_mesh', 'kwargs': {'settings': {field: value}}}])


def make_calls(keyword=False, mixed=False, field='curvature_order'):
    setting = {field: 2 if field == 'curvature_order' else 'fixedorder'}
    call = {'method': 'configure_tetrahedral_mesh',
        **({'kwargs': {'settings': setting}} if keyword else {'args': [setting]})}
    return ([{'method': 'new_component', 'args': ['never']}] if mixed else []) + [call]


@pytest.mark.parametrize('keyword', [False, True])
@pytest.mark.parametrize('mixed', [False, True])
@pytest.mark.parametrize('field', ['curvature_order', 'curvature_policy'])
def test_old_worker_refused_before_enqueue_launch(tmp_path, monkeypatch, keyword, mixed, field):
    from tpc_service.sessions import manager as module
    from tpc_service.sessions.store import read, write
    manager = module.SessionManager(str(tmp_path), backend='fake')
    ref = manager.ensure('curvature', 'e'); folder = tmp_path / ref['session_id']
    state = read(folder / 'session.json')
    state.update(status='ready', worker={'pid': 123}, worker_capabilities=[
        'mesh-settings-no-rebuild-v1', 'content-bound-settings-history-v1', 'hf-tet-adaptation-controls-v1'])
    state['worker_capabilities'].append('hf-tet-curvature-policy-v1' if field == 'curvature_order' else 'hf-tet-curvature-order-v1')
    write(folder / 'session.json', state)
    monkeypatch.setattr(module, 'alive', lambda *a: True)
    monkeypatch.setattr(manager, '_launch', lambda *a: pytest.fail('Worker launch'))
    calls = make_calls(keyword, mixed, field)
    params = dict(project_id='p', stage_id='curvature', calls=calls,
        preview_digest=hashlib.sha256(json.dumps(calls, sort_keys=True, ensure_ascii=False).encode()).hexdigest())
    with pytest.raises(ServiceError) as error:
        manager.submit(ref['session_id'], ref['credential'], 'curvature', 'model_api', params)
    assert error.value.code == 'workflow_worker_upgrade_required'
    assert 'curvature' in str(error.value)
    assert not list((folder / 'jobs').glob('*.json'))


@pytest.mark.parametrize('keyword', [False, True])
@pytest.mark.parametrize('field', ['curvature_order', 'curvature_policy'])
def test_execution_rechecks_before_native_project(tmp_path, keyword, field):
    from tpc_service.sessions.operations import execute
    runtime = SimpleNamespace(folder=tmp_path, backend='cst', state=lambda: {
        'worker_capabilities': ['content-bound-settings-history-v1', 'mesh-settings-no-rebuild-v1',
            'hf-tet-curvature-policy-v1' if field == 'curvature_order' else 'hf-tet-curvature-order-v1']},
        project=lambda *a: pytest.fail('Native project access'))
    job = {'operation': 'model_api', 'params': {'project_id': 'p', 'calls': make_calls(keyword, True, field)}}
    with pytest.raises(ServiceError) as error:
        execute(runtime, job)
    assert error.value.code == 'workflow_worker_upgrade_required'
    assert 'curvature' in str(error.value)
    assert job['workflow_preflight_rejected'] is True


@pytest.mark.parametrize('valid', [False, True])
@pytest.mark.parametrize('field', ['curvature_order', 'curvature_policy'])
def test_mcp_validates_before_launch(tmp_path, monkeypatch, valid, field):
    from cst_mcp import tools
    from cst_mcp.session_tools import register_session_tools
    from tpc_service.sessions import SessionManager
    for name in ('TOOL_SPECS', 'HANDLERS', 'READ_TOOLS', 'WRITE_TOOLS'):
        monkeypatch.setattr(tools, name, getattr(tools, name).copy())
    def launch(*a, **k):
        if not valid: pytest.fail('Invalid request launched worker')
    monkeypatch.setattr(SessionManager, '_launch', launch)
    register_session_tools(str(tmp_path.resolve()), backend='fake')
    ref = tools.dispatch('ensure_cst_session', {'binding': 'curvature', 'request_id': 'e'})['session']
    calls = make_calls(True, field=field)
    if not valid: calls[0]['kwargs']['settings'][field] = 4 if field == 'curvature_order' else 'off'
    params = dict(project_id='p', stage_id='curvature', calls=calls,
        preview_digest=hashlib.sha256(json.dumps(calls, sort_keys=True, ensure_ascii=False).encode()).hexdigest())
    out = tools.dispatch('submit_cst_session_operation', dict(session_id=ref['session_id'],
        credential=ref['credential'], request_id='curvature', operation='model_api', params=params))
    assert out['ok'] is valid
    if valid: assert out['job']['params']['calls'] == calls
    else: assert not list((tmp_path / ref['session_id'] / 'jobs').glob('*.json'))


@pytest.mark.parametrize('policy', ['automatic', 'fixedorder'])
@pytest.mark.parametrize('include_order', [False, True])
def test_policy_sparse_and_combined_exact_commands(policy, include_order):
    history = []
    app = SimpleNamespace(cst_file=SimpleNamespace(model3d=SimpleNamespace(
        add_to_history=lambda *a: history.append(a))))
    settings = {'curvature_policy': policy}
    if include_order: settings['curvature_order'] = 2
    receipt = MeshMixin.configure_tetrahedral_mesh(app, settings)
    expected = ['MeshSettings.SetMeshType "Tet"']
    if include_order: expected.append('MeshSettings.Set "CurvatureOrder", "2"')
    expected.append(f'MeshSettings.Set "CurvatureOrderPolicy", "{policy}"')
    assert history[0][1].splitlines() == expected
    assert receipt['history_caption'] == history[0][0]
    assert receipt['readback_verified'] is False


@pytest.mark.parametrize('missing', ['order', 'policy'])
def test_combined_request_requires_both_capabilities(tmp_path, missing):
    from tpc_service.sessions.operations import execute
    capabilities = ['content-bound-settings-history-v1', 'mesh-settings-no-rebuild-v1',
                    'hf-tet-curvature-order-v1', 'hf-tet-curvature-policy-v1']
    capabilities.remove(f'hf-tet-curvature-{missing}-v1')
    runtime = SimpleNamespace(folder=tmp_path, backend='cst',
        state=lambda: {'worker_capabilities': capabilities},
        project=lambda *a: pytest.fail('Native project access'))
    job = {'operation': 'model_api', 'params': {'project_id': 'p', 'calls': [
        {'method': 'configure_tetrahedral_mesh', 'args': [
            {'curvature_order': 2, 'curvature_policy': 'fixedorder'}]}]}}
    with pytest.raises(ServiceError) as error:
        execute(runtime, job)
    assert error.value.code == 'workflow_worker_upgrade_required'
    assert f'curvature {missing}' in str(error.value)
