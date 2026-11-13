import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from tpc_service.errors import ServiceError
from tpc_service.sessions.store import digest,write
from test_native_static_gate import setup_native


def setup_case(tmp_path,monkeypatch):
    from tpc_service.sessions import native_static_run as native
    snapshot,spec,task,deps,impedance,project=setup_native(tmp_path,monkeypatch)
    sha=hashlib.sha256(Path(project).read_bytes()).hexdigest()
    workflow={'revision':'rev','em_generation':3,'em_receipt':{'job_id':'em','em_generation':3,'saved_digest':sha}}
    state={'session_id':'session','backend':'cst','status':'ready','worker':{'pid':1},'environment':{'pid':2},
           'worker_capabilities':['native-static-sp-v2','static-sp-guarded-run-v1'],
           'projects':{'p':{'project_id':'p','path':project,'saved':True,'saved_digest':sha,'workflow':workflow}}}
    from tpc_service.sessions.workflow import marker
    write(marker(project),{'session_folder':str(tmp_path.resolve()),'project_id':'p'})
    write(tmp_path/'jobs'/'em.json',{'job_id':'em','session_id':'session','operation':'solve','status':'succeeded',
                                   'params':{'project_id':'p'}})
    monkeypatch.setattr(native,'alive',lambda value:True)
    monkeypatch.setattr(native.JobIndex,'load',lambda folder:SimpleNamespace(active_jobs=lambda:[]))
    monkeypatch.setattr('tpc_service.sessions.workflow.check_evidence',lambda *a:None)
    task_spec=spec['task'];observed={'source':'gui_observation','task_name':task_spec['task_name'],
        'frequency_unit':task_spec['frequency_unit'],'fmin':task_spec['fmin'],'fmax':task_spec['fmax'],
        'samples':task_spec['samples'],'observed_at':'2026-11-13T00:00:00+08:00','review_note':'test'}
    observation=tmp_path/'sample-observation.json';observation.write_text(json.dumps(observed),encoding='utf-8')
    params={'project_id':'p','em_job_id':'em','expected_saved_digest':sha,'snapshot_digest':digest(snapshot),
            'spec':spec,'confirm_idle':True,'sample_observation':{'path':str(observation),
            'sha256':hashlib.sha256(observation.read_bytes()).hexdigest()}}
    return native,state,params,snapshot,task,deps,impedance


def test_native_static_review_requires_current_em_receipt(tmp_path,monkeypatch):
    native,state,params,*_=setup_case(tmp_path,monkeypatch)
    assert native.preflight(tmp_path,state,params)['em_generation']==3
    state['projects']['p']['workflow']['em_generation']=4
    with pytest.raises(ServiceError): native.preflight(tmp_path,state,params)


def test_sampling_observation_must_match_review_and_unchanged_bytes(tmp_path,monkeypatch):
    native,state,params,*_=setup_case(tmp_path,monkeypatch)
    assert native.preflight(tmp_path,state,params)['sample_observation']['source']=='gui_observation'
    Path(params['sample_observation']['path']).write_text('{}',encoding='utf-8')
    with pytest.raises(ServiceError): native.preflight(tmp_path,state,params)


def test_invalid_native_static_request_never_launches_worker(tmp_path,monkeypatch):
    from tpc_service.sessions.manager import SessionManager
    manager=SessionManager(tmp_path,backend='cst');ref=manager.ensure('native-static','one')
    monkeypatch.setattr(manager,'_launch',lambda *a,**k:pytest.fail('must not launch'))
    with pytest.raises(ServiceError):
        manager.submit(ref['session_id'],ref['credential'],'request','review_native_static_sp',{'project_id':'p'})


def test_invalid_native_static_prepare_never_launches_worker(tmp_path,monkeypatch):
    from tpc_service.sessions.manager import SessionManager, OPERATIONS
    assert 'prepare_native_static_sp' in OPERATIONS
    manager=SessionManager(tmp_path,backend='cst');ref=manager.ensure('native-prepare','one')
    monkeypatch.setattr(manager,'_launch',lambda *a,**k:pytest.fail('must not launch'))
    with pytest.raises(ServiceError):
        manager.submit(ref['session_id'],ref['credential'],'request','prepare_native_static_sp',{'project_id':'p'})


def test_partial_native_static_prepare_fences_session():
    from tpc_service.sessions.worker import _finish_failed_job
    state={'status':'ready','uncertain_jobs':[]}
    job={'operation':'prepare_native_static_sp','job_id':'partial','params':{'project_id':'p'}}
    _finish_failed_job(job,{'code':'session_native_static_prepare_partial','details':{'mutation_may_have_occurred':True}},state)
    assert state['status']=='needs_reconcile' and job['status']=='failed'


def test_native_static_review_uses_current_em_and_existing_project_without_solve(tmp_path,monkeypatch):
    from cst_solver import dialogs
    from cst_solver.circuit import adapter,linear_sp,native as bridge
    native,state,params,snapshot,task,deps,impedance=setup_case(tmp_path,monkeypatch)
    project=state['projects']['p']['path']
    obj=SimpleNamespace(inspect=lambda:snapshot,schematic=SimpleNamespace(),dependencies=lambda:deps,
                        select=lambda kind,name:SimpleNamespace(GetProperty=lambda key:'True'))
    handle=SimpleNamespace(filename=lambda:project,model3d=SimpleNamespace(is_solver_running=lambda **kw:False))
    app=SimpleNamespace(cst_file=handle)
    runtime=SimpleNamespace(folder=tmp_path,backend='cst',app=app,handles={'p':handle},state=lambda:state,
                            check_saved=lambda p:None)
    monkeypatch.setattr(dialogs,'check_dialogs',lambda **kw:None)
    monkeypatch.setattr(adapter,'NativeAdapter',lambda app:obj)
    monkeypatch.setattr(linear_sp,'inspect_existing_linear_sp',lambda *a:task)
    monkeypatch.setattr(bridge,'read_project_sp_impedances',lambda *a,**k:impedance)
    monkeypatch.setattr('tpc_service.sessions.workflow.live_checks',lambda *a:None)
    result=native.review(runtime,{'job_id':'review','params':params})
    assert result['em_job_id']=='em' and result['em_generation']==3
    assert result['native_host_present'] and not result['em_reuse_verified'] and not result['solver_verified']


def test_native_static_run_requires_current_review_and_em_receipt(tmp_path,monkeypatch):
    import json
    from cst_automation.sp_impedance_bridge import build_impedance_query,parse_impedance_receipt
    native,state,params,snapshot,task,deps,impedance=setup_case(tmp_path,monkeypatch)
    project=state['projects']['p']['path'];q=build_impedance_query(project,'SP',['A','Z'],receipt_root=tmp_path/'sp_impedance_queries')
    out=Path(q['output_path']);out.parent.mkdir(parents=True,exist_ok=True);encode=lambda s:s.encode('utf-16-be').hex().upper()
    lines=['CST_SP_IMPEDANCE_V1','request\t'+q['request_id'],'project\t'+encode(q['project_resources']),
           'task\t'+encode('SP'),'unit\t'+encode('Ohm'),'count\t2']
    lines += ['port\t'+encode(n)+'\t'+encode('Constant')+'\t'+encode('unsupported')+'\t'+encode('100')+'\t'+encode('0') for n in ('A','Z')]
    lines+=['END\t'+q['request_id']];out.write_text('\n'.join(lines),encoding='ascii')
    manifest=out.with_suffix('.request.json');manifest.write_text(json.dumps(q),encoding='utf-8')
    report=parse_impedance_receipt(out.read_bytes(),request=q);report.update(artifact_path=str(out),manifest_path=str(manifest))
    result={'em_job_id':'em','snapshot_digest':params['snapshot_digest'],'saved_digest':params['expected_saved_digest'],
            'after':snapshot,'spec':params['spec'],'task_report':task,'impedances':report,'workflow_revision':'rev',
            'em_generation':3,'em_receipt':state['projects']['p']['workflow']['em_receipt'],'native_host_present':True,
            'sample_observation':native.read_sample_observation(params)}
    write(tmp_path/'jobs'/'review.json',{'job_id':'review','session_id':'session','status':'succeeded',
          'operation':'review_native_static_sp','params':params,'result':result})
    monkeypatch.setattr('cst_solver.circuit.links.dependency_manifest',lambda *args:deps)
    request={'project_id':'p','review_job_id':'review','expected_saved_digest':params['expected_saved_digest'],
             'confirm_idle':True,'confirm_run':True}
    assert native.run_preflight(tmp_path,state,request)['review']['job_id']=='review'
    state['projects']['p']['workflow']['em_generation']=4
    with pytest.raises(ServiceError): native.run_preflight(tmp_path,state,request)


def test_invalid_native_static_run_is_rejected_without_worker_launch(tmp_path, monkeypatch):
    from tpc_service.sessions.manager import SessionManager, OPERATIONS
    assert 'run_native_static_sp' in OPERATIONS
    manager = SessionManager(tmp_path, backend='cst')
    ref = manager.ensure('native-run-invalid', 'one')
    monkeypatch.setattr(manager, '_launch', lambda *a, **k: pytest.fail('must not launch'))
    with pytest.raises(ServiceError):
        manager.submit(ref['session_id'], ref['credential'], 'request', 'run_native_static_sp', {'project_id': 'p'})


def test_native_static_run_rechecks_host_and_uses_shared_kernel(tmp_path, monkeypatch):
    from cst_solver import dialogs
    from cst_solver.circuit import adapter, linear_sp, native as bridge
    from tpc_service.sessions import static_sp_run
    native, state, params, snapshot, task, deps, impedance = setup_case(tmp_path, monkeypatch)
    project = state['projects']['p']['path']
    (Path(project).with_suffix('') / 'Model' / '3D').mkdir(parents=True)
    (Path(project).with_suffix('') / 'Model' / '3D' / 'model.dat').write_bytes(b'geometry')
    reviewed = {'params': params, 'result': {'after': snapshot, 'spec': params['spec'], 'task_report': task}}
    evidence = {'review': reviewed, 'parsed_impedance': impedance, 'em_generation': 3,
                'sample_observation': native.read_sample_observation(params)}
    request = {'project_id': 'p', 'review_job_id': 'review', 'expected_saved_digest': params['expected_saved_digest'],
               'confirm_idle': True, 'confirm_run': True}
    obj = SimpleNamespace(inspect=lambda: snapshot, schematic=SimpleNamespace(), dependencies=lambda: deps,
                          select=lambda kind, name: SimpleNamespace(GetProperty=lambda key: 'True'))
    handle = SimpleNamespace(filename=lambda: project, model3d=SimpleNamespace(is_solver_running=lambda **kw: False))
    app = SimpleNamespace(cst_file=handle)
    runtime = SimpleNamespace(folder=tmp_path, backend='cst', app=app, handles={'p': handle}, state=lambda: state,
                              check_saved=lambda p: None)
    monkeypatch.setattr(native, 'run_preflight', lambda *a, **k: evidence)
    monkeypatch.setattr(dialogs, 'check_dialogs', lambda **kw: None)
    monkeypatch.setattr(adapter, 'NativeAdapter', lambda app: obj)
    monkeypatch.setattr(linear_sp, 'inspect_existing_linear_sp', lambda *a: task)
    monkeypatch.setattr(bridge, 'read_project_sp_impedances', lambda *a, **k: impedance)
    monkeypatch.setattr('tpc_service.sessions.workflow.live_checks', lambda *a: None)
    calls = []
    monkeypatch.setattr(static_sp_run, 'run_and_archive', lambda **kw: calls.append(kw) or {'solver_verified': True})
    result = native.execute(runtime, {'job_id': 'run', 'params': request})
    assert result['solver_verified'] is True and len(calls) == 1
    assert calls[0]['require_no_3d'] is False and calls[0]['snapshot'] == snapshot


def test_native_static_read_refuses_invalid_request_before_worker_launch(tmp_path, monkeypatch):
    from tpc_service.sessions.manager import SessionManager, OPERATIONS
    assert 'read_native_static_sp' in OPERATIONS
    manager = SessionManager(tmp_path, backend='cst')
    ref = manager.ensure('native-read-invalid', 'one')
    monkeypatch.setattr(manager, '_launch', lambda *a, **k: pytest.fail('must not launch'))
    with pytest.raises(ServiceError):
        manager.submit(ref['session_id'], ref['credential'], 'request', 'read_native_static_sp', {'project_id': 'p'})


@pytest.mark.parametrize('task_exists',[True,False])
@pytest.mark.parametrize('fail_task',[True,False])
@pytest.mark.parametrize('change_3d',[True,False])
def test_native_host_preparation_zeros_sources_and_configures_single_task(tmp_path,monkeypatch,task_exists,fail_task,change_3d):
    import copy
    from cst_solver import dialogs
    from cst_solver.circuit import adapter,linear_sp,native as bridge
    from tpc_service.sessions import workflow
    native,state,params,snapshot,task,deps,impedance=setup_case(tmp_path,monkeypatch)
    params.pop('sample_observation')
    if not task_exists: snapshot['tasks']=[row for row in snapshot['tasks'] if row.get('name')!='SP']
    next(b for b in snapshot['blocks'] if b['name']=='P')['properties']['ACAmplitude']='1'
    params['snapshot_digest']=digest(snapshot)
    project=state['projects']['p']['path'];observed=copy.deepcopy(snapshot);writes=[]
    (Path(project).with_suffix('')/'Model'/'3D').mkdir(parents=True)
    (Path(project).with_suffix('')/'Model'/'3D'/'model.dat').write_bytes(b'geometry')
    def select(kind,name):
        if kind=='SimulationTask': return SimpleNamespace(GetProperty=lambda key:'True',SetProperty=lambda *args:None)
        block=next(b for b in observed['blocks'] if b['name']==name)
        def write_field(field,value): writes.append((name,field,value));block['properties'][field]=value
        return SimpleNamespace(SetDoubleProperty=write_field)
    obj=SimpleNamespace(inspect=lambda:copy.deepcopy(observed),schematic=SimpleNamespace(),dependencies=lambda:deps,select=select)
    handle=SimpleNamespace(filename=lambda:project,model3d=SimpleNamespace(is_solver_running=lambda **kw:False))
    app=SimpleNamespace(cst_file=handle)
    runtime=SimpleNamespace(folder=tmp_path,backend='cst',app=app,handles={'p':handle},state=lambda:state,
        check_saved=lambda p:None,save=lambda app,pid:{'saved_digest':params['expected_saved_digest']})
    monkeypatch.setattr(native,'preflight',lambda *a,**kw:{'em_generation':3})
    monkeypatch.setattr(dialogs,'check_dialogs',lambda **kw:None)
    monkeypatch.setattr(adapter,'NativeAdapter',lambda app:obj)
    monkeypatch.setattr(linear_sp,'inspect_existing_linear_sp',lambda *a:task)
    def complete(*args,**kwargs):
        if fail_task: raise RuntimeError('native task failed')
        return {'sample_count_readback':'unsupported'}
    monkeypatch.setattr(linear_sp,'complete_existing_linear_sp_task',complete)
    def configure(*args,**kwargs):
        if fail_task: raise RuntimeError('native task failed')
        observed['tasks'].append({'name':'SP','type':'S-Parameters'})
        return {'sample_count_readback':'unsupported'}
    monkeypatch.setattr(linear_sp,'configure_linear_sp_task',configure)
    monkeypatch.setattr(bridge,'read_project_sp_impedances',lambda *a,**kw:impedance)
    monkeypatch.setattr(workflow,'live_checks',lambda *a:None)
    monkeypatch.setattr(workflow,'invalidate',lambda *a:None)
    if change_3d:
        inventories=iter([{'x':'before'},{'x':'before'},{'x':'after'}])
        monkeypatch.setattr('tpc_service.sessions.static_fenced_recovery._model3d_files',lambda *a:next(inventories))
    job={'job_id':'prepare','operation':'prepare_native_static_sp','params':params}
    if fail_task or change_3d:
        with pytest.raises(ServiceError) as error: native.prepare(runtime,job)
        assert error.value.code=='session_native_static_prepare_partial'
        assert error.value.details['mutation_may_have_occurred'] is True
        assert (tmp_path/'native_static_prepare'/'prepare.before.json').is_file()
        return
    report=native.prepare(runtime,job)
    assert ('P','ACAmplitude','0') in writes and report['saved'] is True
    assert report['after']['nets']==snapshot['nets']
    assert len([row for row in report['after']['tasks'] if row.get('name')=='SP'])==1
    assert not report['solver_verified'] and report['sample_count_native_readback']=='unsupported'


def test_native_host_preparation_invalid_control_fails_before_write(tmp_path,monkeypatch):
    from cst_solver.circuit.native_static_gate import validate_native_static
    snapshot,spec,task,deps,impedance,project=setup_native(tmp_path,monkeypatch)
    spec['control']['resistance_ohms']=75
    with pytest.raises(ValueError):
        validate_native_static(snapshot,spec,task,deps,impedance,project_path=project,task_enabled=True)


def test_preparation_refuses_existing_task_unit_mismatch_before_write(tmp_path,monkeypatch):
    from cst_solver import dialogs
    from cst_solver.circuit import adapter,linear_sp
    native,state,params,snapshot,task,deps,impedance=setup_case(tmp_path,monkeypatch)
    params.pop('sample_observation');task['frequency_unit']='MHz'
    project=state['projects']['p']['path']
    (Path(project).with_suffix('')/'Model'/'3D').mkdir(parents=True)
    (Path(project).with_suffix('')/'Model'/'3D'/'model.dat').write_bytes(b'geometry')
    handle=SimpleNamespace(filename=lambda:project,model3d=SimpleNamespace(is_solver_running=lambda **kw:False))
    app=SimpleNamespace(cst_file=handle)
    obj=SimpleNamespace(inspect=lambda:snapshot,schematic=SimpleNamespace(),
        select=lambda *a:pytest.fail('must not write or select source'))
    runtime=SimpleNamespace(folder=tmp_path,backend='cst',app=app,handles={'p':handle},state=lambda:state,
                            check_saved=lambda p:None)
    monkeypatch.setattr(native,'preflight',lambda *a,**kw:{'em_generation':3})
    monkeypatch.setattr(dialogs,'check_dialogs',lambda **kw:None)
    monkeypatch.setattr(adapter,'NativeAdapter',lambda app:obj)
    monkeypatch.setattr(linear_sp,'inspect_existing_linear_sp',lambda *a:task)
    monkeypatch.setattr('tpc_service.sessions.workflow.live_checks',lambda *a:None)
    with pytest.raises(ServiceError,match='units or circuit simulator'):
        native.prepare(runtime,{'job_id':'prepare','operation':'prepare_native_static_sp','params':params})


def test_native_read_rejects_incomplete_run_or_changed_archive(tmp_path,monkeypatch):
    native,state,params,snapshot,task,deps,impedance=setup_case(tmp_path,monkeypatch)
    review={'job_id':'review','session_id':'session','status':'succeeded','operation':'review_native_static_sp',
            'params':params,'result':{'after':snapshot,'workflow_revision':'rev',
                                      'em_receipt':state['projects']['p']['workflow']['em_receipt']}}
    write(tmp_path/'jobs'/'review.json',review)
    root=tmp_path/'static_sp_runs'/'run';root.mkdir(parents=True);raw=root/'current-curves.json';raw.write_text('{}')
    receipt={'status':'succeeded','submitted':True,'execution_returned':True,'update_call_state':'returned',
             'saved':True,'saved_digest':params['expected_saved_digest'],'task_name':'SP','mode':'network',
             'run_token':'token','execution_evidence':{'completed':True}}
    result={'saved':True,'saved_digest':params['expected_saved_digest'],'solver_verified':True,'actual_grid_verified':True,
            'run_token':'token','review_job_id':'review','em_job_id':'em','em_generation':3,'task_name':'SP',
            'circuit_outcome':receipt,'current_curves_path':str(raw),'current_curves_sha256':hashlib.sha256(raw.read_bytes()).hexdigest()}
    run={'job_id':'run','session_id':'session','status':'succeeded','operation':'run_native_static_sp',
         'params':{'project_id':'p'},'result':result}
    write(tmp_path/'jobs'/'run.json',run)
    request={'project_id':'p','run_job_id':'run','expected_saved_digest':params['expected_saved_digest'],
             'positive_run_id':7,'confirm_idle':True}
    assert native.read_preflight(tmp_path,state,request)['raw']==raw.resolve()
    state['projects']['p']['workflow']['revision']='changed'
    with pytest.raises(ServiceError,match='workflow or EM identity'): native.read_preflight(tmp_path,state,request)
    state['projects']['p']['workflow']['revision']='rev'
    receipt['execution_returned']=False;write(tmp_path/'jobs'/'run.json',run)
    with pytest.raises(ServiceError,match='incomplete'): native.read_preflight(tmp_path,state,request)
    receipt['execution_returned']=True;write(tmp_path/'jobs'/'run.json',run);raw.write_text('changed')
    with pytest.raises(ServiceError,match='archive changed'): native.read_preflight(tmp_path,state,request)


def test_native_read_uses_owned_handle_and_shared_archive_reader(tmp_path,monkeypatch):
    from cst_solver import dialogs
    from cst_solver.circuit import adapter
    from tpc_service.sessions import static_sp_run
    native,state,params,snapshot,task,deps,impedance=setup_case(tmp_path,monkeypatch)
    project=state['projects']['p']['path'];raw=tmp_path/'raw.json';raw.write_text('{}')
    run={'result':{'em_job_id':'em','resolved_result_paths':{'11':'a','12':'b','21':'c','22':'d'}}}
    review={'result':{'after':snapshot,'spec':params['spec']}}
    evidence={'run':run,'review':review,'raw':raw}
    request={'project_id':'p','run_job_id':'run','expected_saved_digest':params['expected_saved_digest'],
             'positive_run_id':7,'confirm_idle':True}
    obj=SimpleNamespace(inspect=lambda:snapshot)
    handle=SimpleNamespace(filename=lambda:project,model3d=SimpleNamespace(is_solver_running=lambda **kw:False))
    app=SimpleNamespace(cst_file=handle)
    runtime=SimpleNamespace(folder=tmp_path,backend='cst',app=app,handles={'p':handle},state=lambda:state,
                            check_saved=lambda p:None)
    monkeypatch.setattr(native,'read_preflight',lambda *a,**kw:evidence)
    monkeypatch.setattr(dialogs,'check_dialogs',lambda **kw:None)
    monkeypatch.setattr(adapter,'NativeAdapter',lambda app:obj)
    calls=[]
    monkeypatch.setattr(static_sp_run,'read_archived_positive',lambda **kw:calls.append(kw) or {'saved':False})
    result=native.read_positive(runtime,{'job_id':'read','params':request})
    assert result['saved'] is False and calls[0]['positive_run_id']==7 and calls[0]['expected']==snapshot
