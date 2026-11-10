"""Saved EM qualification does not launch CST or rewrite failed jobs."""
import copy
from datetime import datetime,timezone
from types import SimpleNamespace
import pytest
from test_workflow_enforcement import setup,bind,submit,runtime_for
from tpc_service.sessions.store import read,write
from tpc_service.errors import ServiceError
from cst_automation.em_qualification import log_proof


def params():
    return dict(project_id='p',em_job_id='failed-em',expected_digest='0'*64,run_id=2,port_ids=[1,2],
        fmin_hz=1e6,fmax_hz=3e9,required_frequencies_hz=[1e6,3e9],frequency_atol_hz=1,
        delta_s_limit=.02,consecutive_passes=2,max_residual=1e-6)


def native_log():
    return """2026-01-01 08:00:01   Solver started at: 2026-01-01 08:00:01 +0800
2026-01-01 08:00:02   All S-Parameters : 0.01
2026-01-01 08:00:03   All S-Parameters : 0.009
2026-01-01 08:00:04   Mesh adaptation terminated because the desired accuracy limit is reached.
2026-01-01 08:00:04   Calculation 2 (Frequency: 0.001 GHz)
                      Stimulation port : 1
                      Accuracy : 1e-8
                      Iterations : 2
                      Stimulation port : 2
                      Accuracy : 1e-8
                      Iterations : 2
2026-01-01 08:00:04   Calculation 3 (Frequency: 3 GHz)
                      Stimulation port : 1
                      Accuracy : 1e-8
                      Iterations : 2
                      Stimulation port : 2
                      Accuracy : 1e-8
                      Iterations : 2
2026-01-01 08:00:05   Finished the general purpose interpolative broadband frequency sweep:
                      All broadband sweep convergence criteria have been satisfied after
                      calculating 8 frequency samples:
2026-01-01 08:00:06   Post-processing finished.
2026-01-01 08:00:07   Creating parametric 1D results for Run ID 2
"""


def eligible(setup):
    bind(setup);runtime=runtime_for(setup)
    state=runtime.state();project=state['projects']['p'];w=project['workflow']
    p=params();p['expected_digest']=project['saved_digest']
    start=datetime(2026,1,1,tzinfo=timezone.utc).timestamp()
    original={'job_id':'failed-em','sequence':1,'request_id':'em','operation_id':'em','status':'resolved','operation':'solve','params':{'project_id':'p'},
        'workflow_guard':{'revision':w['revision'],'em_generation':0,'hb_generation':0},
        'started_at':start,'finished_at':start+10,
        'completion_evidence':{'monitor_failure_seen':False,'launch_intent':False,'uncertain_job_count':0},
        'error':{'code':'session_solve_unverified','details':{'saved':True,'saved_digest':p['expected_digest'],
          'outcome':{'errors':[{'code':'run_exception','details':{'error':'RuntimeError: An error occurred while trying to execute run_solver:\nAborted by user'}}]}}}}
    write(setup[2]/'jobs'/'failed-em.json',original)
    w.update(em_generation=1,hb_generation=1)
    state['last_resolution']={'human_reviewed':True,'at':start+11,'project_digests':{'p':p['expected_digest']}}
    runtime.update(projects=state['projects'],last_resolution=state['last_resolution'])
    folder=setup[3].with_suffix('')/'Result';folder.mkdir(parents=True)
    (folder/'Model.log').write_text(native_log());(folder/'output.txt').write_text('native completed');(folder/'Storage.sdb').write_bytes(b'native saved data')
    return runtime,p,original


@pytest.mark.parametrize('failure',['abort','later_run','missing_finish','mesh_fail','window','wrong_id','bad_residual','missing_port'])
def test_native_terminal_checks(failure):
    p=params();start=datetime(2026,1,1,tzinfo=timezone.utc).timestamp()
    job={'started_at':start,'finished_at':start+10};log=native_log()
    if failure=='abort':log+='2026-01-01 08:00:08   Aborted by user\n'
    if failure=='later_run':log+=log
    if failure=='missing_finish':log=log.replace('Post-processing finished.','Other message')
    if failure=='mesh_fail':log=log.replace('0.009','0.9')
    if failure=='window':job['finished_at']=start+6
    if failure=='wrong_id':p['run_id']=3
    if failure=='bad_residual':log=log.replace('Accuracy : 1e-8','Accuracy : 0.1')
    if failure=='missing_port':log=log.replace('Stimulation port : 2','Stimulation port : 3')
    with pytest.raises(ValueError):log_proof(log,job,p)


def test_native_mesh_terminated_success_is_not_abort():
    start=datetime(2026,1,1,tzinfo=timezone.utc).timestamp()
    assert log_proof(native_log(),{'started_at':start,'finished_at':start+10},params())['mesh_deltas']==[.01,.009]


@pytest.mark.parametrize('failure',['generation','revision','digest','monitor','unresolved','no_review'])
def test_rejected_qualification_never_launches(setup,failure):
    runtime,p,original=eligible(setup);state=runtime.state()
    if failure=='generation':state['projects']['p']['workflow']['em_generation']+=1
    if failure=='revision':state['projects']['p']['workflow']['revision']='other'
    if failure=='digest':p['expected_digest']='f'*64
    if failure=='monitor':
        original['completion_evidence']['monitor_failure_seen']=True;write(setup[2]/'jobs'/'failed-em.json',original)
    if failure=='unresolved':state['status']='needs_reconcile'
    if failure=='no_review':state['last_resolution']={}
    write(setup[2]/'session.json',state);setup[-1].clear()
    with pytest.raises(ServiceError):submit(setup,'qualify_saved_em',{k:v for k,v in p.items() if k!='project_id'},'qualify')
    assert not setup[-1]


def test_qualified_route_preserves_error_and_never_acquires_project(setup,monkeypatch):
    from tpc_service.sessions import em_qualification as q
    from tpc_service.sessions.operations import execute
    from tpc_service.sessions.workflow import evidence_report
    runtime,p,original=eligible(setup)
    before=(setup[2]/'jobs'/'failed-em.json').read_bytes()
    runtime.project=lambda *a:pytest.fail('Qualification must not acquire CST project')
    monkeypatch.setattr(q,'saved_curves',lambda *a:{'matrix_sha256':'data','run_id':2})
    job=submit(setup,'qualify_saved_em',{k:v for k,v in p.items() if k!='project_id'},'qualify')
    proof=execute(runtime,job)
    job.update(status='succeeded',result=proof);write(setup[2]/'jobs'/(job['job_id']+'.json'),job)
    assert (setup[2]/'jobs'/'failed-em.json').read_bytes()==before
    assert proof['sdk_success'] is False and proof['independent_dc_verified'] is False
    assert q.qualified_source(setup[2],runtime.state()['projects']['p'],original)
    artifact=setup[2]/'metric.csv';artifact.write_text('numerical source')
    import hashlib
    report={'em_job_id':'failed-em','em_saved_digest':p['expected_digest'],
        'metrics':{'fmin_hz':0,'fmax_hz':3e9,'fit_error':.001},
        'artifacts':[{'path':str(artifact),'sha256':hashlib.sha256(artifact.read_bytes()).hexdigest()}]}
    path=setup[2]/'analysis.json';write(path,report)
    assert evidence_report(setup[2],runtime.state()['projects']['p'],dict(em_job_id='failed-em',report_path=str(path)))
    monkeypatch.setattr(q,'saved_curves',lambda *a:{'matrix_sha256':'overwritten','run_id':2})
    assert not q.qualified_source(setup[2],runtime.state()['projects']['p'],original)
    with pytest.raises(ServiceError):
        evidence_report(setup[2],runtime.state()['projects']['p'],dict(em_job_id='failed-em',report_path=str(path)))


def test_saved_data_changing_during_read_is_rejected(setup,monkeypatch):
    from tpc_service.sessions import em_qualification as q
    from tpc_service.sessions.operations import execute
    runtime,p,_=eligible(setup)
    def mutate(*args):
        (setup[3].with_suffix('')/'Result'/'Storage.sdb').write_bytes(b'changed');return {}
    monkeypatch.setattr(q,'saved_curves',mutate)
    job=submit(setup,'qualify_saved_em',{k:v for k,v in p.items() if k!='project_id'},'qualify')
    with pytest.raises(ServiceError):execute(runtime,job)
    assert runtime.state()['projects']['p']['workflow']['em_receipt'] is None


@pytest.mark.parametrize('failure',[None,'missing_pair','wrong_run','nonfinite','missing_sample','parameter'])
def test_native_saved_matrix_is_read_completely(monkeypatch,failure):
    import cst_solver
    from tpc_service.sessions.em_qualification import saved_curves
    p=params();trees=[f'1D Results\\S-Parameters\\S{a},{b}' for a in (1,2) for b in (1,2)]
    if failure=='missing_pair':trees.pop()
    class Item:
        xlabel='Frequency / GHz';ylabel='Value / 1'
        def __init__(self,tree):self.tree=tree
        def get_xdata(self):return [.001,3] if failure!='missing_sample' else [.002,3]
        def get_ydata(self):
            if failure=='nonfinite':return [complex(float('nan'),0),0j]
            if 'Residual' in self.tree:return [1e-3,0] if failure=='bad_residual' else [1e-8,0]
            return [0.1+0.2j,0.3+0.4j]
    class Reader:
        def __init__(self,*args):self.result_module=SimpleNamespace(get_parameter_combination=lambda _:dict(width=3 if failure=='parameter' else 2))
        def get_tree_items(self):return trees
        def get_run_ids(self,tree):return [1] if failure=='wrong_run' else [2]
        def get_result_item(self,tree,run_id):assert run_id==2;return Item(tree)
    monkeypatch.setattr(cst_solver,'Result',Reader)
    if failure:
        with pytest.raises((ValueError,RuntimeError)):saved_curves('unused',p,{'width':2})
    else:
        result=saved_curves('unused',p,{'width':2});assert result['samples']==2
