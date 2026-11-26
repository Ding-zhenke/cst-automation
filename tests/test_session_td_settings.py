from types import SimpleNamespace
import pytest
from cst_solver.simulation.solver import SolverMixin
from cst_solver.mesh.mesh import MeshMixin
from tpc_service.errors import ServiceError
from tpc_service.sessions.model_api import dispatch, validate_calls

class App(SolverMixin, MeshMixin):
    def __init__(self):
        self.history=[]
        self.cst_file=SimpleNamespace(model3d=SimpleNamespace(add_to_history=lambda name, code: self.history.append((name,code))))

def test_typed_time_settings_dispatch_commands():
    app=App()
    calls=[{'method':'configure_time_solver'}, {'method':'set_gpu_acceleration','args':[1,True]},
        {'method':'set_parallel_threads','args':[8,True]}, {'method':'set_mesh_adaption','args':[False]},
        {'method':'set_steady_state_limit','args':[-40]}, {'method':'set_mesh_auto','kwargs':{'lines_per_wavelength':12}}]
    dispatch(app,calls)
    assert len(app.history)==6
    assert '.Method "Hexahedral"' in app.history[0][1]
    assert '.MaximumNumberOfGPUs "1"' in app.history[1][1]
    assert '.MaximumNumberOfThreads "8"' in app.history[2][1]
    assert '.MeshAdaption "False"' in app.history[3][1]
    assert '.SteadyStateLimit "-40"' in app.history[4][1]
    assert '.LinesPerWavelength "12"' in app.history[5][1]
    assert '.SetMeshType "Hex"' in app.history[5][1]
    assert '.Set "StepsPerWaveNear", "12"' in app.history[5][1]

def test_fit_mesh_setters_preserve_expression_and_unrelated_settings():
    app = App()
    app.set_mesh_properties(lines_per_wavelength='mesh_density', mesh_type='PBA')
    app.set_mesh_auto(lines_per_wavelength='mesh_density', mesh_type='Hexahedral')
    for _, code in app.history:
        assert '.MeshType "HexahedralFIT"' in code
        assert '.Set "StepsPerWaveNear", "mesh_density"' in code
        assert '.Set "StepsPerWaveFar"' not in code
        assert '.Reset' not in code

def test_other_mesh_types_do_not_write_fit_settings():
    app = App()
    app.set_mesh_auto(mesh_type='HexahedralTLM')
    app.set_mesh_properties(mesh_type='Tetrahedral')
    assert all('StepsPerWaveNear' not in code for _, code in app.history)

def test_fit_capability_detects_defaults_and_positional_type():
    from tpc_service.sessions.model_api import uses_fit_mesh_density
    assert uses_fit_mesh_density([{'method': 'set_mesh_auto'}])
    assert uses_fit_mesh_density([{'method': 'set_mesh_auto', 'args': [25, 10, 'HexahedralFIT']}])
    assert not uses_fit_mesh_density([{'method': 'set_mesh_auto', 'kwargs': {'mesh_type': 'HexahedralTLM'}}])

def test_fit_density_rejects_previously_compatible_execution_worker(tmp_path):
    from tpc_service.sessions.operations import execute
    runtime = SimpleNamespace(folder=tmp_path, backend='cst',
        state=lambda: {'worker_capabilities': ['td-em-settings-v1', 'td-mesh-minimum-step-v1']},
        project=lambda *_: pytest.fail('project accessed'))
    job = {'operation': 'model_api', 'params': {'project_id': 'p',
           'calls': [{'method': 'set_mesh_auto', 'kwargs': {'lines_per_wavelength': 25}}]}}
    with pytest.raises(ServiceError) as exc:
        execute(runtime, job)
    assert exc.value.code == 'workflow_worker_upgrade_required'
    assert 'FIT mesh density' in str(exc.value)
    assert job['workflow_preflight_rejected'] is True

def test_fit_density_rejects_old_worker_before_enqueue(tmp_path, monkeypatch):
    import hashlib, json
    from tpc_service.sessions import manager as module
    from tpc_service.sessions.store import read, write
    manager = module.SessionManager(str(tmp_path), backend='fake')
    ref = manager.ensure('fit', 'ensure')
    folder = tmp_path / ref['session_id']
    state = read(folder / 'session.json')
    state.update(status='ready', worker={'pid': 123},
                 worker_capabilities=['td-em-settings-v1', 'td-mesh-minimum-step-v1'])
    write(folder / 'session.json', state)
    monkeypatch.setattr(module, 'alive', lambda *_: True)
    monkeypatch.setattr(manager, '_launch', lambda *_: pytest.fail('unexpected worker launch'))
    calls = [{'method': 'set_mesh_auto', 'kwargs': {'lines_per_wavelength': 25}}]
    digest = hashlib.sha256(json.dumps(calls, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    params = dict(project_id='p', stage_id='fit', calls=calls, preview_digest=digest)
    with pytest.raises(ServiceError) as exc:
        manager.submit(ref['session_id'], ref['credential'], 'fit', 'model_api', params)
    assert exc.value.code == 'workflow_worker_upgrade_required'
    assert 'FIT mesh density' in str(exc.value)
    assert not list((folder / 'jobs').glob('*.json'))

@pytest.mark.parametrize('call',[
    {'method':'set_gpu_acceleration','args':[0,True]},
    {'method':'set_gpu_acceleration','args':[1,'False']},
    {'method':'set_parallel_threads','args':[0]},
    {'method':'set_mesh_adaption','args':['False']},
    {'method':'set_steady_state_limit','args':['0"\nSolver.Start']},
    {'method':'set_mesh_auto','kwargs':{'mesh_type':'PBA"\nSolver.Start'}},
    {'method':'set_mesh_auto','kwargs':{'smallest_mesh_step':'-1'}},
])
def test_invalid_time_settings_rejected_before_batch_mutation(call):
    app=App()
    with pytest.raises(ServiceError): dispatch(app,[{'method':'configure_time_solver'},call])
    assert not app.history

def test_solver_reset_must_precede_other_solver_settings():
    with pytest.raises(ServiceError): validate_calls([{'method':'set_parallel_threads'}, {'method':'configure_time_solver'}])

def test_execution_worker_must_advertise_time_settings(tmp_path):
    from tpc_service.sessions.operations import execute
    runtime=SimpleNamespace(folder=tmp_path,backend='cst',state=lambda:{'worker_capabilities':[]},project=lambda *_:pytest.fail('project accessed'))
    job={'operation':'model_api','params':{'project_id':'p','calls':[{'method':'configure_time_solver'}]}}
    with pytest.raises(ServiceError) as exc: execute(runtime,job)
    assert exc.value.code=='workflow_worker_upgrade_required'
    assert job['workflow_preflight_rejected'] is True
