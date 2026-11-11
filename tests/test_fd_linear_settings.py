import hashlib
import json
from types import SimpleNamespace

import pytest

from cst_automation.fd_linear import linear_solver_code
from cst_solver.simulation.solver import SolverMixin
from cst_solver.validation import ValidationMixin
from cst_solver.mesh.mesh import MeshMixin
from tpc_service.errors import ServiceError
from tpc_service.sessions.model_api import validate_calls, settings_only


@pytest.mark.parametrize('settings', [{}, {'solver_type': 'auto'}, {'solver_type': 'Direct"\n.Start'},
    {'limit_iterations': 1}, {'limit_iterations': True}, {'max_iterations': 10},
    {'limit_iterations': True, 'max_iterations': True}, {'limit_iterations': True, 'max_iterations': 0},
    {'solver_type': 'Direct', 'unknown': 1}])
def test_invalid_linear_request_rejected_offline(settings):
    with pytest.raises(ValueError):
        linear_solver_code(settings)
    with pytest.raises(ServiceError):
        validate_calls([{'method': 'configure_fd_linear_solver', 'args': [settings]}])


@pytest.mark.parametrize('kind', ['Auto', 'Iterative', 'Direct'])
def test_typed_linear_controls_do_not_imply_fallback(kind):
    calls = []
    app = SimpleNamespace(cst_file=SimpleNamespace(model3d=SimpleNamespace(add_to_history=lambda *a: calls.append(a))))
    result = SolverMixin.configure_fd_linear_solver(app, {'solver_type': kind,
        'limit_iterations': True, 'max_iterations': 17})
    code = calls[0][1]
    assert f'.Type "{kind}"' in code
    assert '.MaxIterations "17"' in code and '.LimitIterations "True"' in code
    assert all(word not in code for word in ('Reset', 'Start', 'Rebuild', 'ChangeSolverType'))
    assert result['direct_fallback_verified'] is result['readback_verified'] is False


def test_disable_limit_preserves_other_settings():
    assert linear_solver_code({'limit_iterations': False}) == 'With FDSolver\n .LimitIterations "False"\nEnd With'


@pytest.mark.parametrize('messages', [[], [{'type': 'WARNING', 'text': 'configuration warning'}]])
@pytest.mark.parametrize('method,settings', [
    ('configure_fd_linear_solver', {'solver_type': 'Direct'}),
    ('configure_fd_linear_solver', {'solver_type': 'Direct', 'tet_order': 'Second', 'mixed_order': True}),
    ('configure_tetrahedral_mesh', {'adaptation': {'singular_edge_refinement': 3,
        'refinement_type': 'automatic', 'snap_to_geometry': True}}),
    ('configure_tetrahedral_mesh', {'local_solids': [{'solid': 'component:contact', 'max_step': 0.01}],
                                  'adaptation': {'max_passes': 3}})])
def test_settings_only_dispatch_saves_without_rebuild_or_solve(tmp_path, messages, method, settings):
    from tpc_service.sessions.operations import _execute_operation
    class App(SolverMixin, ValidationMixin, MeshMixin):
        pass
    app = App()
    from cst_solver._guards import get_guard_state
    get_guard_state(app).param_dirty = True
    commands, saves = [], []
    def forbidden(*a, **k):
        pytest.fail('Settings-only route must not rebuild or solve')
    app.cst_file = SimpleNamespace(get_messages=lambda: messages, model3d=SimpleNamespace(
        add_to_history=lambda *a: commands.append(a), Rebuild=forbidden,
        full_history_rebuild=forbidden, run_solver=forbidden))
    record = {'path': str(tmp_path/'model.cst'), 'saved_digest': 'saved'}
    runtime = SimpleNamespace(folder=tmp_path, backend='cst', project=lambda pid: (app, record),
        save=lambda *a: saves.append(a) or record)
    job = {'operation': 'model_api', 'job_id': 'j', 'operation_id': 'o', 'fingerprint': 'f',
           'params': {'project_id': 'p', 'calls': [{'method': method, 'args': [settings]}]}}
    if messages:
        with pytest.raises(ServiceError) as caught:
            _execute_operation(runtime, job)
        assert caught.value.code == 'session_geometry_unverified'
        assert len(commands) == len(saves) == 1
        assert get_guard_state(app).param_dirty is True
        return
    result = _execute_operation(runtime, job)
    assert len(commands) == len(saves) == 1
    assert result['settings_only'] is True
    assert result['geometry_validation']['rebuild_performed'] is False
    assert result['geometry_validation']['geometry_verified'] is False
    assert result['configuration_receipts'][0]['method'] == method
    assert get_guard_state(app).param_dirty is True


def test_mixed_batch_not_classified_as_settings_only():
    assert not settings_only([{'method': 'configure_fd_linear_solver'}, {'method': 'create_brick'}])


def test_model_band_setting_saves_without_rebuild_or_solver(tmp_path):
    from cst_solver.parameters import ParametersMixin
    from tpc_service.sessions.operations import _execute_operation
    from tpc_service.sessions.model_api import settings_capability
    class App(ParametersMixin, ValidationMixin):
        pass
    app = App()
    commands, saves = [], []
    def forbidden(*a, **k):
        pytest.fail('Model band settings must not rebuild or solve')
    app.cst_file = SimpleNamespace(get_messages=lambda: [], model3d=SimpleNamespace(
        add_to_history=lambda *a: commands.append(a), Rebuild=forbidden,
        full_history_rebuild=forbidden, run_solver=forbidden))
    record = {'path': str(tmp_path/'model.cst'), 'saved_digest': 'saved'}
    runtime = SimpleNamespace(folder=tmp_path, backend='cst', project=lambda pid: (app, record),
                              save=lambda *a: saves.append(a) or record)
    calls = [{'method': 'set_frequency_range', 'args': ['fmin', 'fmax']}]
    job = {'operation':'model_api','job_id':'j','operation_id':'o','fingerprint':'f',
           'params':{'project_id':'p','calls':calls}}
    assert settings_only(calls)
    assert settings_capability(calls) == 'model-band-no-rebuild-v1'
    result = _execute_operation(runtime, job)
    assert result['settings_only'] is True and not result['geometry_validation']['rebuild_performed']
    assert 'Solver.FrequencyRange "fmin", "fmax"' in commands[0][1]
    assert len(saves) == 1


def test_old_worker_rejects_model_band_before_queue(tmp_path, monkeypatch):
    from tpc_service.sessions import manager as module
    from tpc_service.sessions.store import read, write
    manager = module.SessionManager(str(tmp_path), backend='fake')
    ref = manager.ensure('band', 'band')
    folder = tmp_path/ref['session_id']; state = read(folder/'session.json')
    state.update(status='ready', worker={'pid':123}, worker_capabilities=['solver-settings-no-rebuild-v1'])
    write(folder/'session.json', state)
    monkeypatch.setattr(module, 'alive', lambda *a: True)
    monkeypatch.setattr(manager, '_launch', lambda *a: pytest.fail('No launch'))
    calls = [{'method':'set_frequency_range','args':['fmin','fmax']}]
    params = {'project_id':'p','stage_id':'band','calls':calls,
              'preview_digest':hashlib.sha256(json.dumps(calls,sort_keys=True,ensure_ascii=False).encode()).hexdigest()}
    with pytest.raises(ServiceError) as caught:
        manager.submit(ref['session_id'],ref['credential'],'request','model_api',params)
    assert caught.value.code == 'workflow_worker_upgrade_required'
    assert not list((folder/'jobs').glob('*.json'))


@pytest.mark.parametrize('method,settings', [
    ('configure_fd_linear_solver', {'solver_type': 'Direct'}),
    ('configure_tetrahedral_mesh', {'adaptation': {'max_passes': 3}})])
def test_old_worker_refused_before_queue_or_launch(tmp_path, monkeypatch, method, settings):
    from tpc_service.sessions import manager as module
    from tpc_service.sessions.store import read, write
    manager = module.SessionManager(str(tmp_path), backend='fake')
    ref = manager.ensure('test', 'test')
    folder = tmp_path/ref['session_id']
    state = read(folder/'session.json')
    capabilities = ['parameter-em-hb-v1']
    if method == 'configure_tetrahedral_mesh':
        capabilities.append('solver-settings-no-rebuild-v1')
    state.update(status='ready', worker={'pid': 123}, worker_capabilities=capabilities)
    write(folder/'session.json', state)
    monkeypatch.setattr(module, 'alive', lambda *a: True)
    monkeypatch.setattr(manager, '_launch', lambda *a: pytest.fail('No launch'))
    calls = [{'method': method, 'args': [settings]}]
    params = {'project_id': 'p', 'stage_id': 'linear', 'calls': calls,
              'preview_digest': hashlib.sha256(json.dumps(calls, sort_keys=True, ensure_ascii=False).encode()).hexdigest()}
    with pytest.raises(ServiceError) as caught:
        manager.submit(ref['session_id'], ref['credential'], 'request', 'model_api', params)
    assert caught.value.code == 'workflow_worker_upgrade_required'
    assert not list((folder/'jobs').glob('*.json'))
