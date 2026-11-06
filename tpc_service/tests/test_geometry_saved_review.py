"""Geometry validity is separate from a known returned/saved operation."""
from pathlib import Path
from types import SimpleNamespace
import hashlib
import pytest
from cst_solver.validation import ValidationMixin
from tpc_service.errors import ServiceError
from tpc_service.sessions.operations import execute
from tpc_service.sessions.worker import _finish_failed_job


def validation_app(messages, *, raises=False):
    class App(ValidationMixin): pass
    app=App(); batches=iter([[],messages])
    def rebuild():
        if raises: raise RuntimeError('native rebuild raised')
    app.cst_file=SimpleNamespace(get_messages=lambda:next(batches),model3d=SimpleNamespace(Rebuild=rebuild))
    return app


def test_info_is_not_rebuild_error_or_dependency_acceptance():
    out=validation_app([{'type':'INFO','text':'External source is missing; cached shape may exist'}]).validate_model()
    assert out['rebuild_ok'] is out['rebuild_returned'] is True
    assert out['status']=='unverified' and out['dependency_validation']=='unknown'
    assert out['message_summary']['info']==1


@pytest.mark.parametrize('kind,status',[('WARNING','unverified'),('ERROR','error'),('OTHER','error')])
def test_native_severity_remains_conservative(kind,status):
    out=validation_app([{'type':kind,'text':'message'}]).validate_model()
    assert out['status']==status


def receipt(tmp_path):
    path=tmp_path/'p.cst'; path.write_bytes(b'baseline')
    record={'project_id':'p','path':str(path),'saved':True,'saved_digest':hashlib.sha256(path.read_bytes()).hexdigest()}
    state={'projects':{'p':record},'status':'ready','uncertain_jobs':[],'launch_intent':False}
    validation={'status':'unverified','rebuild_ok':True,'rebuild_returned':True,
                'rebuild_performed':True,'messages':[{'type':'INFO','text':'source missing'}]}
    app=SimpleNamespace(para=lambda *a,**k:None,validate_model=lambda **kwargs:validation)
    def save(*args):
        path.write_bytes(b'saved partial model'); record['saved_digest']=hashlib.sha256(path.read_bytes()).hexdigest()
        return record
    runtime=SimpleNamespace(backend='cst',folder=tmp_path,project=lambda p:(app,record),save=save,
                            state=lambda:state,update=lambda **kw:state.update(kw))
    job={'operation':'set_parameters','job_id':'j','operation_id':'o','fingerprint':'f',
         'params':{'project_id':'p','values':{'new_unused_parameter':1}}}
    return runtime,app,record,state,job


def test_parameter_update_uses_parametric_validation_not_full_rebuild(tmp_path):
    runtime, app, record, state, job = receipt(tmp_path)
    seen = []
    app.validate_model = lambda **kw: seen.append(kw) or {
        'status': 'success', 'rebuild_ok': True, 'rebuild_performed': True,
        'rebuild_returned': True}
    result = execute(runtime, job)
    assert seen == [{'rebuild_mode': 'parametric'}]
    assert result['saved'] is True


def test_solve_does_not_rebuild_after_parameter_update(tmp_path):
    runtime, app, record, state, job = receipt(tmp_path)
    app.validate_model = lambda **kwargs: pytest.fail('solve must not rebuild')
    app.run_checked = lambda **kwargs: {'status': 'succeeded'}
    job.update(operation='solve', params={'project_id': 'p'})
    assert execute(runtime, job)['solver_outcome']['status'] == 'succeeded'


def test_parametric_validation_checks_native_return_and_preserves_full_path():
    app = validation_app([])
    calls = []
    app.update = lambda: calls.append('update')
    app.cst_file.model3d.Rebuild = lambda: pytest.fail('full rebuild destroys results')
    result = app.validate_model(rebuild_mode='parametric')
    assert calls == ['update']
    assert result['status'] == 'success' and result['rebuild_mode'] == 'parametric'


def test_parametric_validation_rejects_update_exception():
    app = validation_app([])
    def fail():
        raise RuntimeError('SDK update failed')
    app.update = fail
    result = app.validate_model(rebuild_mode='parametric')
    assert result['status'] != 'success' and result['rebuild_ok'] is False


def error_receipt(case):
    with pytest.raises(ServiceError) as caught: execute(case[0],case[4])
    return caught.value.to_dict()


def test_known_geometry_failure_is_saved_failed_and_reviewable(tmp_path):
    case=receipt(tmp_path); error=error_receipt(case); runtime,app,record,state,job=case
    _finish_failed_job(job,error,state)
    assert state['status']=='ready' and job['status']=='failed'
    assert job['result']['execution_state']=='returned_saved'
    assert job['result']['geometry_outcome']['validation_passed'] is False
    assert job['result']['geometry_outcome']['geometry_verified'] is False
    assert job['result']['review_required'] is True
    assert not (tmp_path/'checkpoints'/'j.json').exists()


@pytest.mark.parametrize('change',['rebuild_exception','missing_receipt','digest','disk','foreign','operation',
                                   'prior_fence','unknown','launch','dialog'])
def test_geometry_receipt_never_clears_unknown_work(tmp_path,change):
    case=receipt(tmp_path); error=error_receipt(case); runtime,app,record,state,job=case
    proof=error['details'].get('geometry_outcome',{})
    monitor=None
    if change=='rebuild_exception': proof.setdefault('validation',{})['rebuild_returned']=False
    if change=='missing_receipt': error['details'].pop('geometry_outcome',None)
    if change=='digest': error['details']['saved_digest']='0'*64
    if change=='disk': Path(record['path']).write_bytes(b'changed later')
    if change=='foreign': proof['project']=str(tmp_path/'foreign.cst')
    if change=='operation': proof['operation']='history'
    if change=='prior_fence': state['status']='needs_reconcile'
    if change=='unknown': state['uncertain_jobs']=['old']
    if change=='launch': state['launch_intent']=True
    if change=='dialog': monitor={'state':'blocked_by_dialog'}
    _finish_failed_job(job,error,state,monitor_failure=monitor)
    assert state['status']=='needs_reconcile' and not job.get('result')


def review_case(tmp_path):
    from tpc_service.sessions.native import Runtime,file_digest
    from tpc_service.tests.test_session_project_discipline import fixture
    manager,ref,runtime,record=fixture(tmp_path); runtime.backend='cst'
    identity={'pid':424242}; runtime.update(status='needs_reconcile',environment=identity,
        last_error={'code':'session_geometry_unverified'},uncertain_jobs=[])
    calls=[]
    model=SimpleNamespace(GetNumberOfParameters=lambda:1,GetParameterName=lambda i:'x',
        RestoreParameterExpression=lambda name:'1',Solid=SimpleNamespace(GetNumberOfShapes=lambda:0))
    handle=SimpleNamespace(filename=lambda:record['path'],model3d=model)
    app=SimpleNamespace(cst_file=handle,get_parameter=lambda name:1,
        project=SimpleNamespace(pid=identity['pid'],list_open_projects=lambda:[record['path']],get_open_project=lambda path:handle))
    runtime.project=lambda *a:pytest.fail('must not use automatic project recovery')
    runtime.environment=lambda:pytest.fail('must not recover or open missing tabs')
    runtime.save=lambda *a:pytest.fail('must not save')
    runtime.app=app; runtime.handles['main']=handle
    params={'project_id':'main','native_readback':True,'read_only_review':True,'confirm_idle':True,
            'expected_digest':file_digest(record['path'])}
    return runtime,app,record,params,identity


def test_fenced_explicit_native_review_keeps_fence_and_does_not_consume_messages(tmp_path,monkeypatch):
    runtime,app,record,params,identity=review_case(tmp_path)
    from tpc_service.sessions import store
    monkeypatch.setattr(store,'alive',lambda value:value==identity)
    before=runtime.state()
    result=runtime.execute({'operation':'inspect','job_id':'review','params':params})
    assert result['native_readback']['parameters']['x']['value']==1
    assert result['geometry_verified'] is False
    assert result['message_read_status']=='not_read_preserve_queue'
    assert runtime.state()==before


@pytest.mark.parametrize('issue',['idle','digest','closed','dialog','busy','unknown','other_fence'])
def test_fenced_review_rejects_unsafe_context_without_reopening(tmp_path,monkeypatch,issue):
    runtime,app,record,p,identity=review_case(tmp_path)
    from tpc_service.sessions import store
    monkeypatch.setattr(store,'alive',lambda value:value==identity)
    if issue=='idle': p['confirm_idle']=False
    if issue=='digest': p['expected_digest']='0'*64
    if issue=='closed': app.project.list_open_projects=lambda:[]
    if issue=='dialog': runtime.update(runtime_diagnostics={'state':'blocked_by_dialog'})
    if issue=='busy':
        from tpc_service.sessions.store import write
        write(runtime.folder/'jobs'/'busy.json',{'job_id':'other','status':'running'})
    if issue=='unknown': runtime.update(uncertain_jobs=['old'])
    if issue=='other_fence': runtime.update(last_error={'code':'native_write_uncertain'})
    with pytest.raises(ServiceError): runtime.execute({'operation':'inspect','job_id':'review','params':p})
    assert runtime.state()['status']=='needs_reconcile'


def test_unknown_rebuild_exception_does_not_trigger_another_save(tmp_path):
    case=receipt(tmp_path); calls=[]
    case[1].validate_model=lambda **kwargs:{'status':'error','rebuild_ok':False,'rebuild_performed':True,'rebuild_returned':False}
    case[0].save=lambda *args:calls.append('save')
    error=error_receipt(case)
    assert calls==[] and error['details']['saved'] is False
    _finish_failed_job(case[4],error,case[3])
    assert case[3]['status']=='needs_reconcile'


def test_read_review_failure_preserves_existing_fence_and_geometry_error():
    job={'operation':'inspect','params':{'read_only_review':True}}
    original={'code':'session_geometry_unverified'}
    state={'status':'needs_reconcile','last_error':original}
    error={'code':'session_read_review_refused'}
    _finish_failed_job(job,error,state)
    assert state['status']=='needs_reconcile' and state['last_error']==original
    assert state['last_read_review_error']==error and job['status']=='failed'


def test_cached_review_rejects_foreign_de_identity(tmp_path,monkeypatch):
    runtime,app,record,p,identity=review_case(tmp_path)
    from tpc_service.sessions import store
    monkeypatch.setattr(store,'alive',lambda value:value==identity)
    app.project.pid=424243
    with pytest.raises(ServiceError): runtime.execute({'operation':'inspect','job_id':'review','params':p})


def test_fresh_worker_review_attaches_only_exact_owned_open_project(tmp_path,monkeypatch):
    runtime,app,record,p,identity=review_case(tmp_path)
    from tpc_service.sessions import store
    import cst_solver
    calls=[]; runtime.app=None; runtime.handles.clear()
    monkeypatch.setattr(store,'alive',lambda value:value==identity)
    monkeypatch.setattr(cst_solver,'setup',SimpleNamespace(attach=lambda **kw:calls.append(kw) or app))
    result=runtime.execute({'operation':'inspect','job_id':'review','params':p})
    assert calls==[{'pid':424242}] and result['read_only_review'] is True
    assert runtime.state()['status']=='needs_reconcile'
