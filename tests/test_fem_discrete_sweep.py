from types import SimpleNamespace
from contextlib import nullcontext
import hashlib,json
import pytest
from cst_solver.simulation.solver import SolverMixin
from tpc_service.errors import ServiceError
from tpc_service.sessions.model_api import validate_calls,settings_only

@pytest.mark.parametrize('method',['General purpose','Discrete samples only'])
def test_fem_emits_requested_sweep_without_solve(method):
    cmds=[];app=SimpleNamespace(cst_file=SimpleNamespace(model3d=SimpleNamespace(add_to_history=lambda *args:cmds.append(args))))
    SolverMixin.configure_fem_solver(app,accuracy='1e-7',mesh_adaption=False,sweep_method=method)
    assert f'.SetMethod "Tetrahedral", "{method}"' in cmds[0][1]
    assert '.MeshAdaptionTet "False"' in cmds[0][1]
    assert 'Start' not in cmds[0][1] and 'Rebuild' not in cmds[0][1]
    assert settings_only([{'method':'configure_fem_solver','kwargs':{'sweep_method':method}}])

def test_default_fem_method_remains_general_purpose():
    cmds=[];app=SimpleNamespace(cst_file=SimpleNamespace(model3d=SimpleNamespace(add_to_history=lambda *args:cmds.append(args))))
    SolverMixin.configure_fem_solver(app)
    assert '.SetMethod "Tetrahedral", "General purpose"' in cmds[0][1]

@pytest.mark.parametrize('bad',['discrete samples only','bogus', 'Discrete samples only"\nSolver.Start',None])
def test_unknown_fem_sweep_rejected_in_preflight(bad):
    with pytest.raises(ServiceError):validate_calls([{'method':'configure_fem_solver','kwargs':{'sweep_method':bad}}])

def test_old_worker_rejects_discrete_fem_before_project(tmp_path):
    from tpc_service.sessions.operations import execute
    runtime=SimpleNamespace(folder=tmp_path,backend='cst',state=lambda:{'worker_capabilities':['fem-settings-no-rebuild-v1','solver-settings-no-rebuild-v1']},project=lambda *_:pytest.fail('project accessed'))
    job={'operation':'model_api','params':{'project_id':'p','calls':[{'method':'configure_fem_solver','args':['1e-7',False,'Discrete samples only']}]}}
    with pytest.raises(ServiceError) as e:execute(runtime,job)
    assert e.value.code=='workflow_worker_upgrade_required'

def test_worker_announces_discrete_capability_before_jobs(tmp_path,monkeypatch):
    from tpc_service.sessions import worker
    state={'projects':{}}
    monkeypatch.setattr(worker,'lock',lambda *a,**k:nullcontext())
    monkeypatch.setattr(worker,'read',lambda *_:state)
    monkeypatch.setattr(worker,'process_identity',lambda *_:{'pid':1})
    class Stop(Exception):pass
    monkeypatch.setattr(worker.JobIndex,'load',lambda *a,**k:(_ for _ in ()).throw(Stop()))
    with pytest.raises(Stop):worker.run(tmp_path)
    assert 'fem-discrete-sweep-v1' in state['worker_capabilities']

def test_manager_rejects_discrete_sweep_on_old_worker(tmp_path,monkeypatch):
    from tpc_service.sessions import manager as module
    from tpc_service.sessions.store import read,write
    m=module.SessionManager(str(tmp_path),backend='fake');ref=m.ensure('discrete','ensure');folder=tmp_path/ref['session_id']
    state=read(folder/'session.json');state.update(status='ready',worker={'pid':123},worker_capabilities=['fem-settings-no-rebuild-v1','solver-settings-no-rebuild-v1']);write(folder/'session.json',state)
    monkeypatch.setattr(module,'alive',lambda *a:True);monkeypatch.setattr(m,'_launch',lambda *_:pytest.fail('worker launch'))
    calls=[{'method':'configure_fem_solver','kwargs':{'sweep_method':'Discrete samples only'}}]
    params=dict(project_id='p',stage_id='d',calls=calls,preview_digest=hashlib.sha256(json.dumps(calls,sort_keys=True,ensure_ascii=False).encode()).hexdigest())
    with pytest.raises(ServiceError) as exc:m.submit(ref['session_id'],ref['credential'],'d','model_api',params)
    assert exc.value.code=='workflow_worker_upgrade_required'
    assert not list((folder/'jobs').glob('*.json'))

def test_discrete_fem_session_saves_without_rebuild(tmp_path):
    from cst_solver.validation import ValidationMixin
    from tpc_service.sessions.operations import _execute_operation
    class App(SolverMixin,ValidationMixin): pass
    app=App();history=[];saved=[]
    def forbidden(*a,**k):pytest.fail('rebuild/solve called')
    app.cst_file=SimpleNamespace(get_messages=lambda:[],model3d=SimpleNamespace(add_to_history=lambda *x:history.append(x),Rebuild=forbidden,full_history_rebuild=forbidden,run_solver=forbidden))
    record={'path':str(tmp_path/'model.cst'),'saved_digest':'saved'}
    runtime=SimpleNamespace(folder=tmp_path,backend='cst',project=lambda _:(app,record),save=lambda *a:saved.append(a) or record)
    job={'operation':'model_api','job_id':'j','operation_id':'o','fingerprint':'f','params':{'project_id':'p','calls':[{'method':'configure_fem_solver','kwargs':{'sweep_method':'Discrete samples only'}}]}}
    result=_execute_operation(runtime,job)
    assert result['settings_only'] is True and result['geometry_validation']['rebuild_performed'] is False
    assert len(saved)==1 and '.SetMethod "Tetrahedral", "Discrete samples only"' in history[0][1]
