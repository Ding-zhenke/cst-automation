import copy
from datetime import datetime, timezone

import pytest

from test_em_qualification import native_log, params, eligible
from test_workflow_enforcement import setup, submit
from tpc_service.errors import ServiceError
from tpc_service.sessions.store import read, write


def exploratory_params():
    p = params()
    p.pop('delta_s_limit'); p.pop('consecutive_passes')
    p['acknowledged_warnings']=['mesh adaptation disabled']
    return p


def warning_job(setup):
    runtime,p,job = eligible(setup)
    p.pop('delta_s_limit'); p.pop('consecutive_passes')
    p['acknowledged_warnings']=['mesh adaptation disabled']
    job['status']='failed'
    job['completion_evidence']['known_saved_solve']=True
    job['completion_evidence']['decision']='ready'
    job['completion_evidence']['monitor_snapshot_available']=True
    job['error']['details'].update(execution_returned=True,session_monitor={'failure_latched':False,'final_snapshot':{'state':'clear'}})
    job['error']['details']['outcome']={'status':'unverified','submitted':True,'execution_returned':True,
        'mesh_convergence':'unknown','errors':[{'code':'run_warnings'}],
        'messages':[{'type':'WARNING','text':'mesh adaptation disabled'}]}
    job['result']={'saved':True, 'saved_digest':p['expected_digest'], 'execution_state':'returned_saved',
                   'review_required':True}
    write(setup[2]/'jobs'/'failed-em.json',job)
    return runtime,p,job


def exploratory_log():
    text=native_log().replace('2026-01-01 08:00:04   Mesh adaptation terminated because the desired accuracy limit is reached.\n','')
    return text.replace('calculating 8 frequency samples:', 'calculating 2 frequency samples:')


def test_warning_log_keeps_mesh_unknown_and_requires_all_port_samples():
    from cst_automation.em_qualification import exploratory_log_proof
    start=datetime(2026,1,1,tzinfo=timezone.utc).timestamp()
    job={'started_at':start,'finished_at':start+10}; p=exploratory_params()
    proof=exploratory_log_proof(exploratory_log(),job,p)
    assert proof['mesh_convergence']=='unknown' and proof['direct_samples']==2
    with pytest.raises(ValueError):
        exploratory_log_proof(exploratory_log().replace('Stimulation port : 2','Stimulation port : 3',1),job,p)
    with pytest.raises(ValueError):
        exploratory_log_proof(exploratory_log().replace('calculating 2 frequency samples:', 'calculating 3 frequency samples:'),job,p)


def test_exploratory_receipt_does_not_create_formal_em_gate(setup,monkeypatch):
    from tpc_service.sessions import exploratory_em as q
    runtime,p,original=warning_job(setup)
    folder=setup[3].with_suffix('')/'Result'
    (folder/'Model.log').write_text(exploratory_log())
    before=(setup[2]/'jobs'/'failed-em.json').read_bytes()
    monkeypatch.setattr(q,'saved_curves',lambda *args:{'run_id':2,'fmin_hz':1e6,'fmax_hz':3e9,'matrix_sha256':'test'})
    from tpc_service.sessions.operations import execute
    runtime.project=lambda *args:pytest.fail('Must not acquire CST project')
    job=submit(setup,'qualify_exploratory_em',{k:v for k,v in p.items() if k!='project_id'},'exploratory')
    proof=execute(runtime,job)
    assert proof['purpose']=='exploratory_ads_handoff'
    assert proof['mesh_convergence']=='unknown' and proof['solver_verified'] is False
    assert proof['warnings']==[{'type':'WARNING','text':'mesh adaptation disabled'}]
    assert runtime.state()['projects']['p']['workflow']['em_receipt'] is None
    assert (setup[2]/'jobs'/'failed-em.json').read_bytes()==before


@pytest.mark.parametrize('change',['error','unreturned','monitor','monitor_unknown','generation','other_errors','warning'])
def test_ineligible_warning_result_is_refused(setup,change):
    from tpc_service.sessions import exploratory_em as q
    runtime,p,job=warning_job(setup)
    if change=='error': job['error']['code']='other'
    if change=='unreturned': job['error']['details']['execution_returned']=False
    if change=='monitor': job['completion_evidence']['monitor_failure_seen']=True
    if change=='monitor_unknown': job['error']['details']['session_monitor']['final_snapshot']=None
    if change=='other_errors': job['error']['details']['outcome']['errors'].append({'code':'run_exception'})
    if change=='warning': p['acknowledged_warnings']=['different warning']
    if change=='generation':
        state=runtime.state();state['projects']['p']['workflow']['em_generation']+=1;runtime.update(projects=state['projects'])
    write(setup[2]/'jobs'/'failed-em.json',job)
    with pytest.raises(ServiceError): q.preflight(runtime.folder,runtime.state(),p)


def test_legacy_worker_rejects_before_queued_job(setup, monkeypatch):
    from tpc_service.sessions import exploratory_em as q
    from tpc_service.sessions import workflow
    runtime,p,_=warning_job(setup)
    state=runtime.state();state.update(worker={'pid':111},worker_capabilities=['saved-em-qualification-v1'])
    runtime.update(worker=state['worker'],worker_capabilities=state['worker_capabilities'])
    monkeypatch.setattr(q,'alive',lambda _:True)
    monkeypatch.setattr(workflow,'alive',lambda _:True)
    runtime.update(worker_capabilities=['saved-em-qualification-v1','parameter-em-hb-v1'])
    with pytest.raises(ServiceError) as exc:
        submit(setup,'qualify_exploratory_em',{k:v for k,v in p.items() if k!='project_id'},'legacy')
    assert exc.value.code=='workflow_worker_upgrade_required'
    assert not (runtime.folder/'requests').exists()


def test_exploratory_log_rejects_coverage_and_failure():
    from cst_automation.em_qualification import exploratory_log_proof
    start=datetime(2026,1,1,tzinfo=timezone.utc).timestamp()
    job={'started_at':start,'finished_at':start+10}; p=exploratory_params()
    p['fmax_hz']=4e9
    with pytest.raises(ValueError): exploratory_log_proof(exploratory_log(),job,p)
    p['fmax_hz']=3e9
    with pytest.raises(ValueError): exploratory_log_proof(exploratory_log()+'2026-01-01 08:00:08   Solver failed\n',job,p)
