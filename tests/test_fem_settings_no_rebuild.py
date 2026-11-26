from types import SimpleNamespace
import hashlib,json
import pytest
from cst_solver.simulation.solver import SolverMixin
from cst_solver.validation import ValidationMixin
from tpc_service.errors import ServiceError
from tpc_service.sessions.model_api import settings_only

@pytest.mark.parametrize('messages',[[],[{'type':'WARNING','text':'configuration warning'}]])
def test_fem_settings_use_history_and_save_without_rebuild(tmp_path,messages):
    from tpc_service.sessions.operations import _execute_operation
    class App(SolverMixin,ValidationMixin): pass
    app=App();commands=[];saves=[]
    def forbidden(*a,**k): pytest.fail('rebuild or solve called')
    app.cst_file=SimpleNamespace(get_messages=lambda:messages,model3d=SimpleNamespace(add_to_history=lambda *a:commands.append(a),full_history_rebuild=forbidden,Rebuild=forbidden,run_solver=forbidden))
    record={'path':str(tmp_path/'model.cst'),'saved_digest':'saved'}
    runtime=SimpleNamespace(folder=tmp_path,backend='cst',project=lambda _:(app,record),save=lambda *a:saves.append(a) or record)
    calls=[{'method':'configure_fem_solver','kwargs':{'accuracy':'1e-7','mesh_adaption':True}}]
    job={'operation':'model_api','job_id':'j','operation_id':'o','fingerprint':'f','params':{'project_id':'p','calls':calls}}
    if messages:
        with pytest.raises(ServiceError) as e: _execute_operation(runtime,job)
        assert e.value.code=='session_geometry_unverified'
    else:
        result=_execute_operation(runtime,job)
        assert result['settings_only'] is True
        assert result['geometry_validation']['rebuild_performed'] is False
        assert result['geometry_validation']['geometry_verified'] is False
    assert len(commands)==len(saves)==1
    assert 'ChangeSolverType "HF Frequency Domain"' in commands[0][1]
    assert '.AccuracyTet "1e-7"' in commands[0][1]

def test_fem_with_geometry_still_requires_rebuild():
    assert not settings_only([{'method':'configure_fem_solver'},{'method':'create_brick'}])

def test_old_worker_rejects_fem_settings_before_enqueue(tmp_path,monkeypatch):
    from tpc_service.sessions import manager as module
    from tpc_service.sessions.store import read,write
    m=module.SessionManager(str(tmp_path),backend='fake');ref=m.ensure('fem','ensure');folder=tmp_path/ref['session_id']
    state=read(folder/'session.json');state.update(status='ready',worker={'pid':123},worker_capabilities=['solver-settings-no-rebuild-v1']);write(folder/'session.json',state)
    monkeypatch.setattr(module,'alive',lambda *a:True);monkeypatch.setattr(m,'_launch',lambda *a:pytest.fail('unexpected launch'))
    calls=[{'method':'configure_fem_solver'}]
    params=dict(project_id='p',stage_id='fem',calls=calls,preview_digest=hashlib.sha256(json.dumps(calls,sort_keys=True,ensure_ascii=False).encode()).hexdigest())
    with pytest.raises(ServiceError) as e:m.submit(ref['session_id'],ref['credential'],'fem','model_api',params)
    assert e.value.code=='workflow_worker_upgrade_required'
    assert not list((folder/'jobs').glob('*.json'))

def test_execution_rechecks_fem_capability_before_project(tmp_path):
    from tpc_service.sessions.operations import execute
    runtime=SimpleNamespace(folder=tmp_path,backend='cst',state=lambda:{'worker_capabilities':['solver-settings-no-rebuild-v1']},project=lambda *a:pytest.fail('project accessed'))
    job={'operation':'model_api','params':{'project_id':'p','calls':[{'method':'configure_fem_solver'}]}}
    with pytest.raises(ServiceError) as e:execute(runtime,job)
    assert e.value.code=='workflow_worker_upgrade_required'
    assert job['workflow_preflight_rejected'] is True

def test_worker_startup_announces_fem_capability_before_accepting_jobs(tmp_path, monkeypatch):
    from contextlib import nullcontext
    from tpc_service.sessions import worker
    state={'projects':{}}
    monkeypatch.setattr(worker,'lock',lambda *a,**k:nullcontext())
    monkeypatch.setattr(worker,'read',lambda *_:state)
    monkeypatch.setattr(worker,'process_identity',lambda *_:{'pid':1})
    class StopAfterCapabilities(Exception): pass
    monkeypatch.setattr(worker.JobIndex,'load',lambda *a,**k:(_ for _ in ()).throw(StopAfterCapabilities()))
    with pytest.raises(StopAfterCapabilities): worker.run(tmp_path)
    assert 'fem-settings-no-rebuild-v1' in state['worker_capabilities']
