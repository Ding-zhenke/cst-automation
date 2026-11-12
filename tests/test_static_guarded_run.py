import json
from pathlib import Path
from types import SimpleNamespace
import pytest
from cst_automation.sp_impedance_bridge import build_impedance_query, parse_impedance_receipt
from tpc_service.errors import ServiceError
from tpc_service.sessions.store import digest, write
from test_static_fenced_recovery import setup_state
from test_static_sp_network_gate import setup_gate


def setup_run(tmp_path,monkeypatch):
    from tpc_service.sessions import static_sp_run as run
    snapshot,spec,task,deps,observed,project=setup_gate(tmp_path,monkeypatch)
    state,_=setup_state(tmp_path);state['projects']['p']={'path':project,'saved':True,
        'saved_digest':next(f['sha256'] for f in deps['files'] if Path(f['path'])==Path(project))}
    state['worker_capabilities']+=['static-sp-guarded-run-v1']
    original={'job_id':'job-failed','session_id':'session','status':'failed','finished_at':1,
        'operation':'prepare_static_sp','params':{'project_id':'p','spec':spec},'error':state['last_error']}
    write(tmp_path/'jobs'/'job-failed.json',original)
    state['last_worker_upgrade']['static_partial']['failed_job_digest']=digest(original)
    state['last_worker_upgrade']['static_partial']['snapshot_digest']=digest(snapshot)
    sha=state['projects']['p']['saved_digest']; snap=digest(snapshot)
    complete={'job_id':'complete-1','session_id':'session','status':'succeeded','operation':'complete_failed_static_task',
        'params':{'project_id':'p'},'result':{'task_report':{'after':task}}}
    excluded={'job_id':'exclude-1','session_id':'session','status':'succeeded','operation':'exclude_unconnected_self_em',
        'params':{'project_id':'p','completion_job_id':'complete-1'},'result':{'saved':True,'saved_digest':sha,
        'original_failed_job_id':'job-failed','after':snapshot,'3d_inventory_unchanged':True,'remaining_mws_blocks':[]}}
    write(tmp_path/'jobs'/'complete-1.json',complete);write(tmp_path/'jobs'/'exclude-1.json',excluded)
    q=build_impedance_query(project,'SP',['A','Z'],receipt_root=tmp_path/'sp_impedance_queries')
    out=Path(q['output_path']);out.parent.mkdir(parents=True,exist_ok=True)
    encode=lambda s:s.encode('utf-16-be').hex().upper()
    lines=['CST_SP_IMPEDANCE_V1','request\t'+q['request_id'],'project\t'+encode(q['project_resources']),
           'task\t'+encode('SP'),'unit\t'+encode('Ohm'),'count\t2']
    lines += ['port\t'+encode(n)+'\t'+encode('Constant')+'\t'+encode('unsupported')+'\t'+encode('100')+'\t'+encode('0') for n in ('A','Z')]
    lines += ['END\t'+q['request_id']];out.write_text('\n'.join(lines),encoding='ascii')
    manifest=out.with_suffix('.request.json');manifest.write_text(json.dumps(q),encoding='utf-8')
    report=parse_impedance_receipt(out.read_bytes(),request=q);report.update(artifact_path=str(out),manifest_path=str(manifest))
    impedance={'job_id':'impedance-1','session_id':'session','status':'succeeded','operation':'read_fenced_static_impedances',
        'params':{'project_id':'p'},'result':{'original_failed_job_id':'job-failed','exclude_job_id':'exclude-1',
        'saved_digest':sha,'snapshot_digest':snap,'matches_requested':True,'impedances':report}}
    write(tmp_path/'jobs'/'impedance-1.json',impedance)
    params={'project_id':'p','failed_job_id':'job-failed','exclude_job_id':'exclude-1','impedance_job_id':'impedance-1',
        'expected_saved_digest':sha,'snapshot_digest':snap,'confirm_idle':True,'confirm_run':True}
    monkeypatch.setattr('tpc_service.sessions.static_fenced_recovery.alive',lambda identity:True)
    monkeypatch.setattr('tpc_service.sessions.store.alive',lambda identity:True)
    monkeypatch.setattr('tpc_service.sessions.static_fenced_recovery.JobIndex.load',lambda folder:SimpleNamespace(active_jobs=lambda:[]))
    return run,state,params


def test_run_preflight_accepts_documented_pure_network_leaf(tmp_path,monkeypatch):
    run,state,params=setup_run(tmp_path,monkeypatch)
    result=run.preflight(tmp_path,state,params)
    assert result['gate']['structural_no_em_dependency_verified']
    assert not result['gate']['native_no_em_execution_verified']


@pytest.mark.parametrize('issue',['no_confirmation','unexpected_field','missing_capability','changed_impedance','3d_block'])
def test_invalid_or_unproven_run_is_rejected_before_launch(tmp_path,monkeypatch,issue):
    run,state,params=setup_run(tmp_path,monkeypatch)
    if issue=='no_confirmation': params['confirm_run']=False
    if issue=='unexpected_field': params['unexpected']=True
    if issue=='missing_capability': state['worker_capabilities'].remove('static-sp-guarded-run-v1')
    if issue=='changed_impedance':
        job=__import__('tpc_service.sessions.store',fromlist=['read']).read(tmp_path/'jobs'/'impedance-1.json')
        job['result']['impedances']['ports']['A']['real']=50;write(tmp_path/'jobs'/'impedance-1.json',job)
    if issue=='3d_block':
        job=__import__('tpc_service.sessions.store',fromlist=['read']).read(tmp_path/'jobs'/'exclude-1.json')
        job['result']['after']['blocks'].append({'name':'mws','type':'CST MICROWAVE STUDIO schematic block','files':[]})
        params['snapshot_digest']=digest(job['result']['after']);write(tmp_path/'jobs'/'exclude-1.json',job)
    with pytest.raises((ServiceError,ValueError)): run.preflight(tmp_path,state,params)


def test_live_circuit_drift_refuses_before_task_update(tmp_path,monkeypatch):
    from unittest.mock import Mock
    from cst_solver import dialogs
    from cst_solver.circuit import adapter as circuit_adapter
    from tpc_service.sessions import operations, static_fenced_recovery
    run,state,params=setup_run(tmp_path,monkeypatch)
    excluded=__import__('tpc_service.sessions.store',fromlist=['read']).read(tmp_path/'jobs'/'exclude-1.json')
    changed=excluded['result']['after'].copy();changed['blocks']=changed['blocks']+[{'name':'mws','type':'CST MICROWAVE STUDIO schematic block'}]
    adapter=SimpleNamespace(inspect=lambda:changed)
    project=state['projects']['p']['path']
    handle=SimpleNamespace(filename=lambda:project,model3d=SimpleNamespace(is_solver_running=lambda **kw:False))
    app=SimpleNamespace(cst_file=handle,circuit=SimpleNamespace())
    runtime=SimpleNamespace(folder=tmp_path,backend='cst',app=app,handles={'p':handle},state=lambda:state,check_saved=Mock())
    monkeypatch.setattr('tpc_service.sessions.store.alive',lambda identity:True)
    monkeypatch.setattr(dialogs,'check_dialogs',lambda **kw:None)
    monkeypatch.setattr(circuit_adapter,'NativeAdapter',lambda app:adapter)
    update=Mock(side_effect=AssertionError('Task update must not be called'))
    monkeypatch.setattr(operations,'circuit',update)
    with pytest.raises(ServiceError,match='Native circuit changed'):
        run.execute(runtime,{'job_id':'run-1','params':params})
    update.assert_not_called()


def test_running_3d_solver_refuses_before_task_update(tmp_path,monkeypatch):
    from unittest.mock import Mock
    from cst_solver import dialogs
    from tpc_service.sessions import operations
    run,state,params=setup_run(tmp_path,monkeypatch);project=state['projects']['p']['path']
    handle=SimpleNamespace(filename=lambda:project,model3d=SimpleNamespace(is_solver_running=lambda **kw:True))
    app=SimpleNamespace(cst_file=handle,circuit=SimpleNamespace())
    runtime=SimpleNamespace(folder=tmp_path,backend='cst',app=app,handles={'p':handle},state=lambda:state,check_saved=Mock())
    monkeypatch.setattr('tpc_service.sessions.store.alive',lambda identity:True)
    monkeypatch.setattr(dialogs,'check_dialogs',lambda **kw:None)
    update=Mock(side_effect=AssertionError('Task update must not be called'))
    monkeypatch.setattr(operations,'circuit',update)
    with pytest.raises(ServiceError,match='3D idle'):
        run.execute(runtime,{'job_id':'run-1','params':params})
    update.assert_not_called()


@pytest.mark.parametrize('matching_positive',[True,False])
def test_guarded_leaf_run_archives_actual_curves_without_fabricating_positive_id(tmp_path,monkeypatch,matching_positive):
    from unittest.mock import Mock
    from cst_solver import dialogs
    from cst_solver.circuit import adapter as circuit_adapter, linear_sp, native, results
    from tpc_service.sessions import operations, static_fenced_recovery
    from tpc_service.sessions.store import read
    run,state,params=setup_run(tmp_path,monkeypatch);evidence=run.preflight(tmp_path,state,params)
    snapshot=evidence['excluded']['result']['after'];task=evidence['completion']['result']['task_report']['after']
    adapter=SimpleNamespace(inspect=lambda:snapshot,schematic=object(),
        select=lambda kind,name:SimpleNamespace(GetProperty=lambda key:'true'),
        dependencies=lambda:evidence['dependencies'])
    project=state['projects']['p']['path']
    handle=SimpleNamespace(filename=lambda:project,model3d=SimpleNamespace(is_solver_running=lambda **kw:False))
    app=SimpleNamespace(cst_file=handle,circuit=SimpleNamespace(_adapter=None,_spec=None))
    runtime=SimpleNamespace(folder=tmp_path,backend='cst',app=app,handles={'p':handle},state=lambda:state,check_saved=Mock())
    monkeypatch.setattr('tpc_service.sessions.store.alive',lambda identity:True)
    monkeypatch.setattr(dialogs,'check_dialogs',lambda **kw:None)
    monkeypatch.setattr(circuit_adapter,'NativeAdapter',lambda app:adapter)
    monkeypatch.setattr(linear_sp,'inspect_existing_linear_sp',lambda *a,**kw:task)
    monkeypatch.setattr(native,'read_project_sp_impedances',lambda *a,**kw:{'ports':evidence['parsed_impedance']['ports']})
    monkeypatch.setattr(static_fenced_recovery,'_model3d_files',lambda path:{'same':'hash'})
    calls=[]
    paths={k:f'Tasks\\SP\\S-Parameters\\S{k[0]},{k[1]}' for k in ('11','12','21','22')}
    def execute_task(runtime_arg,app_arg,project_arg,request):
        calls.append(request)
        return {'result_summary':{'circuit_outcome':{'status':'succeeded','execution_returned':True,
            'run_token':'token','task_name':'SP','mode':'network','submitted':True,'update_call_state':'returned',
            'saved':True,'saved_digest':params['expected_saved_digest'],'execution_evidence':{'completed':True},
            'resolved_result_paths':paths}}}
    monkeypatch.setattr(operations,'circuit',execute_task)
    class Reader:
        def __init__(self,path): self.path=path
        def get_run_ids(self,path): return [0,7]
        def read_curve(self,path,*,run_id):
            key=path[-3:].replace(',','');value=0.2 if key=='21' else 0.1
            if run_id==7 and not matching_positive: value+=0.01
            return {'tree_path':path,'run_id':run_id,'parameters':{'R':'50'},'domain':'schematic',
                'project_path':project,'x_unit':'GHz','y_unit':'1','x':[110+i for i in range(61)],
                'y':[complex(value,0)]*61,'sample_digest':str(value)}
    monkeypatch.setattr(results,'CircuitResult',Reader)
    report=run.execute(runtime,{'job_id':'run-1','params':params})
    assert len(calls)==1 and calls[0]['settings']['mode']=='network'
    assert calls[0]['settings']['expected_results']==[] and calls[0]['settings']['result_selectors']==['11','12','21','22']
    assert report['actual_grid_verified'] and report['solver_verified']
    assert report['positive_run_id']==(7 if matching_positive else None)
    assert not report['positive_fresh_attribution_verified'] and not report['native_no_em_execution_verified']
    assert Path(report['current_curves_path']).is_file()
    assert state['status']=='needs_reconcile'
    write(tmp_path/'jobs'/'run-1.json',{'job_id':'run-1','session_id':'session','operation':run.OPERATION,
        'status':'succeeded','params':params,'result':report})
    read_request={'project_id':'p','failed_job_id':'job-failed','run_job_id':'run-1',
        'expected_saved_digest':report['saved_digest'],'positive_run_id':7,'confirm_idle':True}
    if matching_positive:
        loaded=run.read_positive(runtime,{'job_id':'read-1','params':read_request})
        assert loaded['positive_run_id']==7 and loaded['current_content_matches_positive']
        assert not loaded['positive_fresh_attribution_verified'] and Path(loaded['positive_curves_path']).is_file()
    else:
        with pytest.raises(ServiceError,match='does not match'):
            run.read_positive(runtime,{'job_id':'read-1','params':read_request})


@pytest.mark.parametrize('operation',['run_fenced_static_sp','read_fenced_static_sp'])
def test_invalid_run_request_never_opens_session_or_launches_worker(tmp_path,operation):
    from unittest.mock import Mock
    from tpc_service.sessions.manager import SessionManager
    manager=SessionManager(tmp_path/'sessions',backend='cst')
    manager._folder=Mock(side_effect=AssertionError('invalid request reached session'))
    manager._launch=Mock(side_effect=AssertionError('invalid request launched worker'))
    with pytest.raises(ServiceError):
        manager.submit('session','credential','request',operation,{'project_id':'p'})
    manager._folder.assert_not_called();manager._launch.assert_not_called()


def test_positive_read_requires_original_successful_run_and_unchanged_artifact(tmp_path,monkeypatch):
    from tpc_service.sessions.store import read
    from tpc_service.sessions.native import file_digest
    run,state,params=setup_run(tmp_path,monkeypatch)
    raw=tmp_path/'static_sp_runs'/'run-1'/'current-curves.json';raw.parent.mkdir(parents=True)
    raw.write_text('{}',encoding='utf-8')
    receipt={'job_id':'run-1','session_id':'session','operation':'run_fenced_static_sp','status':'succeeded',
        'params':params,'result':{'saved':True,'saved_digest':params['expected_saved_digest'],
        'original_failed_job_id':'job-failed','exclude_job_id':'exclude-1','impedance_job_id':'impedance-1',
        'task_name':'SP','run_token':'token','actual_grid_verified':True,'solver_verified':True,
        'structural_no_em_dependency_verified':True,'current_curves_path':str(raw),'current_curves_sha256':file_digest(raw),
        'circuit_outcome':{'status':'succeeded','submitted':True,'execution_returned':True,'update_call_state':'returned',
            'saved':True,'saved_digest':params['expected_saved_digest'],'task_name':'SP','mode':'network',
            'run_token':'token','execution_evidence':{'completed':True}}}}
    write(tmp_path/'jobs'/'run-1.json',receipt)
    request={'project_id':'p','failed_job_id':'job-failed','run_job_id':'run-1',
             'expected_saved_digest':params['expected_saved_digest'],'positive_run_id':7,'confirm_idle':True}
    assert run.read_preflight(tmp_path,state,request)['run']['job_id']=='run-1'
    raw.write_text('{"changed":true}',encoding='utf-8')
    with pytest.raises(ServiceError): run.read_preflight(tmp_path,state,request)
