import pytest
from tpc_service.sessions import SessionManager
from tpc_service.sessions.store import read,write,digest
from tpc_service.sessions.native import file_digest
from tpc_service.errors import ServiceError


def observed(runtime, proof):
    import time
    runtime.handoff_native_observed_at = time.time()
    return proof


@pytest.fixture
def handoff(tmp_path,monkeypatch):
    from tpc_service.sessions import native_handoff as h
    m=SessionManager(str(tmp_path),backend='cst');ref=m.ensure('handoff','one')
    folder=tmp_path/ref['session_id'];p=folder/'model.cst';p.write_bytes(b'baseline')
    worker={'pid':11,'started':1,'image':'python.exe'}
    de={'pid':22,'started':2,'image':'cstd.exe'}
    state=read(folder/'session.json');state.update(status='ready',worker=worker,environment=de,
        worker_capabilities=['cooperative-worker-upgrade-v1','preserved-de-worker-handoff-v1'],projects={
            'p':{'project_id':'p','path':str(p),'saved':True,'saved_digest':file_digest(p)}})
    write(folder/'session.json',state)
    live={11,22}
    monkeypatch.setattr(h,'alive',lambda identity: bool(identity and identity['pid'] in live))
    monkeypatch.setattr('tpc_service.sessions.manager.alive',lambda identity:bool(identity and identity['pid'] in live))
    args=dict(environment_identity=de,worker_identity=worker,project_digests={'p':file_digest(p)},
        review_note='Reviewed original saved, idle, borrowed worker',required_capabilities=['hf-tet-adaptation-controls-v1'],
        confirm_idle=True,confirm_saved_tabs=True,confirm_borrowed_worker=True,accept_unverified_native_handoff=True)
    return m,ref,folder,live,args,h


@pytest.mark.parametrize('field',['confirm_idle','confirm_saved_tabs','confirm_borrowed_worker','accept_unverified_native_handoff'])
def test_missing_authorization_never_freezes_or_probes(handoff,field,monkeypatch):
    m,r,f,live,args,h=handoff;before=read(f/'session.json');args[field]=False
    monkeypatch.setattr(h,'verify_native',lambda *a:pytest.fail('No native probe'))
    with pytest.raises(ServiceError):m.begin_native_worker_handoff(r['session_id'],r['credential'],**args)
    assert read(f/'session.json')==before


def test_freeze_verify_ack_attach_then_release(handoff,monkeypatch):
    m,r,f,live,args,h=handoff;sid,cred=r['session_id'],r['credential'];proof={'tabs':['original'],'parameters':{'p':{}}}
    monkeypatch.setattr(h,'verify_native',lambda runtime,state:observed(runtime,proof))
    assert m.begin_native_worker_handoff(sid,cred,**args)['phase']=='reviewing'
    with pytest.raises(ServiceError):m.submit(sid,cred,'new','start')
    with pytest.raises(ServiceError):m.resume(sid,cred)
    assert m.finish_native_worker_handoff(sid,cred)['phase']=='stop_requested'
    assert m.finish_native_worker_handoff(sid,cred)['phase']=='stop_requested'
    s=read(f/'session.json');s['worker_upgrade']['stop_ack']=True;write(f/'session.json',s);live.remove(11)
    launched=[]
    monkeypatch.setattr(m,'_launch',lambda *a,**k:launched.append(True))
    assert m.finish_native_worker_handoff(sid,cred)['phase']=='starting'
    assert launched==[True]
    assert m.finish_native_worker_handoff(sid,cred)['phase']=='starting'
    assert launched==[True]
    s=read(f/'session.json');new={'pid':33,'started':3,'image':'python.exe'};live.add(33)
    s.update(worker=new,worker_capabilities=[h.CAPABILITY,'hf-tet-adaptation-controls-v1'])
    s['worker_upgrade'].update(new_worker_ready=new,new_worker_native=proof)
    write(f/'session.json',s)
    monkeypatch.setattr(h,'process_identity',lambda pid:new)
    assert m.finish_native_worker_handoff(sid,cred)['phase']=='release_requested'
    from tpc_service.sessions.native import Runtime
    assert h.verify_release(Runtime(f,'cst'))
    assert m.finish_native_worker_handoff(sid,cred)['phase']=='complete'
    assert read(f/'session.json')['environment']==args['environment_identity']


def test_failed_static_handoff_preserves_original_fence(handoff, monkeypatch):
    m,r,f,live,args,h=handoff; sid,cred=r['session_id'],r['credential']
    error={'code':'session_static_sp_prepare_failed','details':{'mutation_may_have_occurred':True}}
    state=read(f/'session.json');state.update(status='needs_reconcile',last_error=error)
    write(f/'session.json',state)
    job={'job_id':'job-failed','session_id':sid,'status':'failed','finished_at':1,
         'operation':'prepare_static_sp','params':{'project_id':'p'},'error':error}
    write(f/'jobs'/'job-failed.json',job)
    monkeypatch.setattr(h.JobIndex,'load',lambda folder: type('Index',(),{'active_jobs':lambda self: []})())
    review=dict(failed_job_id='job-failed',project_id='p',
        snapshot_digest='a'*64,environment_identity=args['environment_identity'],worker_identity=args['worker_identity'],
        project_digests=args['project_digests'],review_note='Reviewed partial state',confirm_idle=True,
        confirm_borrowed_worker=True,accept_unverified_native_handoff=True)
    report=h.begin_failed_static(m,sid,cred,**review)
    assert report['return_to_fence'] is True and report['static_partial']['snapshot_digest']=='a'*64
    assert report['phase']=='reviewing' and read(f/'session.json')['last_error']==error
    assert h.begin_failed_static(m,sid,cred,**review)['token']==report['token']


def test_dead_worker_recovery_freezes_and_reviews_existing_de(handoff,monkeypatch):
    m,r,f,live,args,h=handoff;sid,cred=r['session_id'],r['credential']
    error={'code':'session_static_sp_prepare_failed','details':{'mutation_may_have_occurred':True}}
    state=read(f/'session.json');state.update(status='needs_reconcile',last_error=error,worker_launch_intent=True);write(f/'session.json',state)
    write(f/'jobs'/'failed.json',{'job_id':'failed','session_id':sid,'status':'failed','finished_at':1,
        'operation':'prepare_static_sp','params':{'project_id':'p'},'error':error})
    snapshot={'blocks':[]};write(f/'jobs'/'complete.json',{'job_id':'complete','session_id':sid,'status':'succeeded',
        'operation':'complete_failed_static_task','params':{'project_id':'p','failed_job_id':'failed'},
        'result':{'original_failed_job_id':'failed','saved':True,'saved_digest':args['project_digests']['p'],'after':snapshot}})
    live.remove(11);monkeypatch.setattr(h,'process_identity',lambda pid:None)
    monkeypatch.setattr(h.JobIndex,'load',lambda folder:type('Index',(),{'active_jobs':lambda self: []})())
    proof={'tabs':['original'],'parameters':{'p':{}},'static_partial':{'p':digest(snapshot)}}
    monkeypatch.setattr(h,'verify_native',lambda runtime,state:observed(runtime,proof))
    review=dict(failed_job_id='failed',completion_job_id='complete',project_id='p',snapshot_digest=digest(snapshot),
        environment_identity=args['environment_identity'],worker_identity=args['worker_identity'],
        project_digests=args['project_digests'],review_note='Reviewed dead worker and saved circuit',
        confirm_idle=True,confirm_no_worker_processes=True,require_self_em_exclusion=True,require_guarded_static_run=True)
    result=h.begin_dead_static_worker_recovery(m,sid,cred,**review)
    assert result['phase']=='stop_requested' and result['stop_ack'] is True
    assert result['pre_exit_native']==proof and result['return_to_fence'] is True
    assert read(f/'session.json')['last_error']==error and read(f/'jobs'/'failed.json')['status']=='failed'
    from tpc_service.sessions.__main__ import main
    from cst_mcp import tools
    from cst_mcp.session_tools import register_session_tools
    write(f/'review.json',review);write(f/'reference.json',dict(r,root=str(m.root)))
    assert main(['--root',str(m.root),'--reference',str(f/'reference.json'),
                 'begin-dead-static-worker-recovery','--review-file',str(f/'review.json')])==0
    for name in ('TOOL_SPECS','HANDLERS','READ_TOOLS','WRITE_TOOLS'):
        monkeypatch.setattr(tools,name,getattr(tools,name).copy())
    register_session_tools(str(m.root),backend='cst')
    assert tools.dispatch('begin_cst_dead_static_worker_recovery',dict(session_id=sid,credential=cred,review=review))['ok']
    launched=[];monkeypatch.setattr(m,'_launch',lambda *a,**k:launched.append(k))
    assert m.finish_native_worker_handoff(sid,cred)['phase']=='starting'
    assert len(launched)==1 and launched[0]['recover'] is True


def test_dead_worker_recovery_rejects_pid_reuse_before_freeze(handoff,monkeypatch):
    m,r,f,live,args,h=handoff;sid,cred=r['session_id'],r['credential']
    state=read(f/'session.json');state['status']='needs_reconcile';write(f/'session.json',state)
    monkeypatch.setattr(h,'process_identity',lambda pid:{'pid':pid,'started':999,'image':'other.exe'})
    with pytest.raises(ServiceError):
        h.begin_dead_static_worker_recovery(m,sid,cred,failed_job_id='failed',completion_job_id='complete',
            project_id='p',snapshot_digest='a'*64,environment_identity=args['environment_identity'],
            worker_identity=args['worker_identity'],project_digests=args['project_digests'],review_note='Review',
            confirm_idle=True,confirm_no_worker_processes=True)
    assert read(f/'session.json')['status']=='needs_reconcile'


def test_failed_static_handoff_rejects_unrelated_failure(handoff, monkeypatch):
    m,r,f,live,args,h=handoff; sid,cred=r['session_id'],r['credential']
    error={'code':'other','details':{'mutation_may_have_occurred':True}}
    state=read(f/'session.json');state.update(status='needs_reconcile',last_error=error)
    write(f/'session.json',state)
    job={'job_id':'job-failed','session_id':sid,'status':'failed','finished_at':1,
         'operation':'prepare_static_sp','params':{'project_id':'p'},'error':error}
    write(f/'jobs'/'job-failed.json',job)
    monkeypatch.setattr(h.JobIndex,'load',lambda folder: type('Index',(),{'active_jobs':lambda self: []})())
    with pytest.raises(ServiceError):
        h.begin_failed_static(m,sid,cred,failed_job_id='job-failed',project_id='p',snapshot_digest='a'*64,
            environment_identity=args['environment_identity'],worker_identity=args['worker_identity'],
            project_digests=args['project_digests'],review_note='Review',confirm_idle=True,
            confirm_borrowed_worker=True,accept_unverified_native_handoff=True)
    assert read(f/'session.json')['status']=='needs_reconcile'


def test_failed_static_owned_worker_requires_exit_risk_acknowledgment(handoff,monkeypatch):
    m,r,f,live,args,h=handoff;sid,cred=r['session_id'],r['credential']
    error={'code':'session_static_sp_prepare_failed','details':{'mutation_may_have_occurred':True}}
    state=read(f/'session.json');state.update(status='needs_reconcile',last_error=error)
    write(f/'session.json',state)
    write(f/'jobs'/'job-failed.json',{'job_id':'job-failed','session_id':sid,'status':'failed','finished_at':1,
        'operation':'prepare_static_sp','params':{'project_id':'p'},'error':error})
    monkeypatch.setattr(h.JobIndex,'load',lambda folder:type('Index',(),{'active_jobs':lambda self: []})())
    review=dict(failed_job_id='job-failed',project_id='p',snapshot_digest='a'*64,
        environment_identity=args['environment_identity'],worker_identity=args['worker_identity'],
        project_digests=args['project_digests'],review_note='Reviewed',confirm_idle=True,
        worker_ownership='owned',confirm_owned_worker=True,accept_unverified_native_handoff=True)
    with pytest.raises(ServiceError): h.begin_failed_static(m,sid,cred,**review)
    assert read(f/'session.json')['status']=='needs_reconcile'
    review['accept_owned_worker_exit_risk']=True
    assert h.begin_failed_static(m,sid,cred,**review)['worker_ownership']=='owned'


def test_failed_static_old_worker_without_preserved_de_capability_is_rejected(handoff,monkeypatch):
    m,r,f,live,args,h=handoff;sid,cred=r['session_id'],r['credential']
    error={'code':'session_static_sp_prepare_failed','details':{'mutation_may_have_occurred':True}}
    state=read(f/'session.json');state.update(status='needs_reconcile',last_error=error,
        worker_capabilities=['cooperative-worker-upgrade-v1']);write(f/'session.json',state)
    write(f/'jobs'/'job-failed.json',{'job_id':'job-failed','session_id':sid,'status':'failed','finished_at':1,
        'operation':'prepare_static_sp','params':{'project_id':'p'},'error':error})
    monkeypatch.setattr(h.JobIndex,'load',lambda folder:type('Index',(),{'active_jobs':lambda self: []})())
    with pytest.raises(ServiceError):
        h.begin_failed_static(m,sid,cred,failed_job_id='job-failed',project_id='p',snapshot_digest='a'*64,
            environment_identity=args['environment_identity'],worker_identity=args['worker_identity'],
            project_digests=args['project_digests'],review_note='Reviewed',confirm_idle=True,
            confirm_borrowed_worker=True,accept_unverified_native_handoff=True)
    assert read(f/'session.json')['status']=='needs_reconcile'


def test_failed_static_handoff_can_require_new_exclusion_capability(handoff,monkeypatch):
    m,r,f,live,args,h=handoff;sid,cred=r['session_id'],r['credential']
    error={'code':'session_static_sp_prepare_failed','details':{'mutation_may_have_occurred':True}}
    state=read(f/'session.json');state.update(status='needs_reconcile',last_error=error);write(f/'session.json',state)
    write(f/'jobs'/'job-failed.json',{'job_id':'job-failed','session_id':sid,'status':'failed','finished_at':1,
        'operation':'prepare_static_sp','params':{'project_id':'p'},'error':error})
    monkeypatch.setattr(h.JobIndex,'load',lambda folder:type('Index',(),{'active_jobs':lambda self: []})())
    record=h.begin_failed_static(m,sid,cred,failed_job_id='job-failed',project_id='p',snapshot_digest='a'*64,
        environment_identity=args['environment_identity'],worker_identity=args['worker_identity'],
        project_digests=args['project_digests'],review_note='Reviewed',confirm_idle=True,
        confirm_borrowed_worker=True,accept_unverified_native_handoff=True,require_self_em_exclusion=True,
        require_guarded_static_run=True)
    assert 'static-sp-self-em-exclusion-v1' in record['required_capabilities']
    assert 'static-sp-guarded-run-v1' in record['required_capabilities']


def test_failed_static_cli_and_mcp_use_same_frozen_handoff(handoff,monkeypatch,capsys):
    from tpc_service.sessions.__main__ import main
    from cst_mcp import tools
    from cst_mcp.session_tools import register_session_tools
    m,r,f,live,args,h=handoff;sid,cred=r['session_id'],r['credential']
    error={'code':'session_static_sp_prepare_failed','details':{'mutation_may_have_occurred':True}}
    state=read(f/'session.json');state.update(status='needs_reconcile',last_error=error);write(f/'session.json',state)
    write(f/'jobs'/'job-failed.json',{'job_id':'job-failed','session_id':sid,'status':'failed','finished_at':1,
        'operation':'prepare_static_sp','params':{'project_id':'p'},'error':error})
    monkeypatch.setattr(h.JobIndex,'load',lambda folder:type('Index',(),{'active_jobs':lambda self: []})())
    review=dict(failed_job_id='job-failed',project_id='p',snapshot_digest='a'*64,
        environment_identity=args['environment_identity'],worker_identity=args['worker_identity'],
        project_digests=args['project_digests'],review_note='Reviewed',confirm_idle=True,
        confirm_borrowed_worker=True,accept_unverified_native_handoff=True)
    write(f/'review.json',review);write(f/'reference.json',dict(r,root=str(m.root)))
    assert main(['--root',str(m.root),'--reference',str(f/'reference.json'),
                 'begin-failed-static-worker-handoff','--review-file',str(f/'review.json')])==0
    assert 'reviewing' in capsys.readouterr().out
    for name in ('TOOL_SPECS','HANDLERS','READ_TOOLS','WRITE_TOOLS'):
        monkeypatch.setattr(tools,name,getattr(tools,name).copy())
    register_session_tools(str(m.root),backend='cst')
    result=tools.dispatch('begin_cst_failed_static_worker_handoff',dict(session_id=sid,credential=cred,review=review))
    assert result['ok'] and result['upgrade']['return_to_fence']


def test_dirty_static_snapshot_drift_is_not_handoff_proof(monkeypatch):
    from types import SimpleNamespace
    from cst_solver.circuit import adapter
    from tpc_service.sessions.native_handoff import verify_static_partial
    expected={'blocks':[{'name':'one'}], 'unknown':[]}
    app=SimpleNamespace(circuit=SimpleNamespace(adapter=SimpleNamespace(inspect=lambda:expected)))
    monkeypatch.setattr(adapter,'NativeAdapter',lambda app:app.circuit.adapter)
    review={'project_id':'p','snapshot_digest':digest(expected)}
    assert verify_static_partial(app, review, 'p') == digest(expected)
    expected['blocks'][0]['name']='changed'
    with pytest.raises(ServiceError): verify_static_partial(app, review, 'p')


def test_dirty_snapshot_uses_new_adapter_for_selected_project(monkeypatch):
    from types import SimpleNamespace
    from cst_solver.circuit import adapter
    from tpc_service.sessions.native_handoff import verify_static_partial
    target={'blocks':[{'name':'target'}], 'unknown':[]}
    app=SimpleNamespace(cst_file=SimpleNamespace(snapshot=target),
        circuit=SimpleNamespace(adapter=SimpleNamespace(inspect=lambda:pytest.fail('stale cached adapter used'))))
    monkeypatch.setattr(adapter,'NativeAdapter',lambda current:SimpleNamespace(inspect=lambda:current.cst_file.snapshot))
    assert verify_static_partial(app,{'project_id':'p','snapshot_digest':digest(target)},'p')==digest(target)


def test_failed_static_handoff_returns_to_fence_without_saving(handoff, monkeypatch):
    from tpc_service.sessions.native import Runtime
    m,r,f,live,args,h=handoff;sid,cred=r['session_id'],r['credential']
    original={'code':'session_static_sp_prepare_failed','details':{'mutation_may_have_occurred':True}}
    state=read(f/'session.json');state.update(status='needs_reconcile',last_error=original)
    write(f/'session.json',state)
    job={'job_id':'job-failed','session_id':sid,'status':'failed','finished_at':1,
         'operation':'prepare_static_sp','params':{'project_id':'p'},'error':original}
    write(f/'jobs'/'job-failed.json',job)
    monkeypatch.setattr(h.JobIndex,'load',lambda folder: type('Index',(),{'active_jobs':lambda self: []})())
    proof={'tabs':['original'],'parameters':{'p':{}},'static_partial':{'p':'a'*64}}
    monkeypatch.setattr(h,'verify_native',lambda runtime,state:observed(runtime,proof))
    review=dict(failed_job_id='job-failed',project_id='p',snapshot_digest='a'*64,
        environment_identity=args['environment_identity'],worker_identity=args['worker_identity'],
        project_digests=args['project_digests'],review_note='Reviewed partial state',confirm_idle=True,
        confirm_borrowed_worker=True,accept_unverified_native_handoff=True)
    h.begin_failed_static(m,sid,cred,**review)
    assert m.finish_native_worker_handoff(sid,cred)['phase']=='stop_requested'
    state=read(f/'session.json');state['worker_upgrade']['stop_ack']=True;write(f/'session.json',state);live.remove(11)
    monkeypatch.setattr(m,'_launch',lambda *a,**kw:None)
    assert m.finish_native_worker_handoff(sid,cred)['phase']=='starting'
    state=read(f/'session.json');new={'pid':33,'started':3,'image':'python.exe'};live.add(33)
    state.update(worker=new,worker_capabilities=[h.CAPABILITY,'static-sp-fenced-recovery-v1'])
    state['worker_upgrade'].update(new_worker_ready=new,new_worker_native=proof)
    write(f/'session.json',state)
    monkeypatch.setattr(h,'process_identity',lambda pid:new)
    assert m.finish_native_worker_handoff(sid,cred)['phase']=='release_requested'
    assert h.verify_release(Runtime(f,'cst'))
    assert m.finish_native_worker_handoff(sid,cred)['phase']=='complete'
    state=read(f/'session.json')
    assert state['status']=='needs_reconcile' and state['last_error']==original
    assert state['projects']['p']['saved_digest']==args['project_digests']['p']


@pytest.mark.parametrize('failure',['native','disk','de','parameter'])
def test_changed_or_failed_evidence_stays_frozen(handoff,monkeypatch,failure):
    m,r,f,live,args,h=handoff;sid,cred=r['session_id'],r['credential']
    monkeypatch.setattr(h,'verify_native',lambda *a:{'parameters':{}})
    m.begin_native_worker_handoff(sid,cred,**args)
    m.finish_native_worker_handoff(sid,cred)
    s=read(f/'session.json');s['worker_upgrade']['stop_ack']=True;write(f/'session.json',s);live.remove(11)
    monkeypatch.setattr(m,'_launch',lambda *a,**k:pytest.fail('Must not launch'))
    if failure=='native': monkeypatch.setattr(h,'verify_native',lambda *a:(_ for _ in ()).throw(OSError('probe failed')))
    elif failure=='disk':(f/'model.cst').write_bytes(b'changed')
    elif failure=='de':live.remove(22)
    else:monkeypatch.setattr(h,'verify_native',lambda *a:{'parameters':{'changed':1}})
    with pytest.raises((ServiceError,OSError)):m.finish_native_worker_handoff(sid,cred)
    assert read(f/'session.json')['status']=='closing'
    assert read(f/'session.json')['worker_upgrade']['phase']=='stop_requested'


@pytest.mark.parametrize('case',['valid','missing','foreign','wrong_pid','running','unknown_idle',
    'parameter_error','parameter_drift','nonfinite','dialog','path_changed'])
def test_native_verifier_borrows_existing_tabs_only(handoff,monkeypatch,case):
    from types import SimpleNamespace
    from cst_solver import setup
    from tpc_service.sessions.native import Runtime
    m,r,f,live,args,h=handoff;state=read(f/'session.json');path=state['projects']['p']['path']
    monkeypatch.setattr('tpc_service.sessions.store.alive',h.alive)
    def dialogs(**kw):
        if case=='dialog':raise RuntimeError('dialog unreadable')
    monkeypatch.setattr('cst_solver.dialogs.check_dialogs',dialogs)
    model=SimpleNamespace(is_solver_running=lambda **kw: True if case=='running' else None if case=='unknown_idle' else False,
        GetNumberOfParameters=lambda:1,GetParameterName=lambda i:'length',RestoreParameterExpression=lambda n:'1')
    handle=SimpleNamespace(model3d=model,filename=lambda: path+'other' if case=='path_changed' else path)
    de=SimpleNamespace(pid=77 if case=='wrong_pid' else 22,
        list_open_projects=lambda:[] if case=='missing' else [path,'foreign.cst'] if case=='foreign' else [path],
        get_open_project=lambda p:handle)
    calls=[]
    def value(name):
        calls.append(name)
        if case=='parameter_error':raise RuntimeError('read failure')
        if case=='parameter_drift':return float(len(calls))
        return float('nan') if case=='nonfinite' else 1.
    app=SimpleNamespace(project=de,get_parameter=value)
    borrowed=[]
    def attach(*,pid):
        assert pid==22;borrowed.append(pid);return app
    monkeypatch.setattr(setup,'attach',attach)
    runtime=Runtime(f,'cst')
    if case=='valid':
        proof=h.verify_native(runtime,state)
        assert proof['parameters']=={'p':{'length':{'value':1.,'expression':'1'}}}
        assert runtime.handles=={'p':handle} and runtime.app is app
        assert borrowed==[22]
    else:
        with pytest.raises((ServiceError,RuntimeError)):h.verify_native(runtime,state)
    assert (f/'model.cst').read_bytes()==b'baseline'


@pytest.mark.parametrize('fails',[False,True])
def test_replacement_readiness_requires_matching_native_proof(handoff,monkeypatch,fails):
    from tpc_service.sessions.native import Runtime
    m,r,f,live,args,h=handoff;sid,cred=r['session_id'],r['credential'];proof={'parameters':{}}
    monkeypatch.setattr(h,'verify_native',lambda runtime,state:observed(runtime,proof))
    m.begin_native_worker_handoff(sid,cred,**args);m.finish_native_worker_handoff(sid,cred)
    s=read(f/'session.json');s['worker_upgrade'].update(phase='starting',stop_ack=True,launch_claimed=True)
    new={'pid':33,'started':3,'image':'python.exe'};s['worker']=new
    write(f/'session.json',s);live.remove(11);live.add(33)
    monkeypatch.setattr(h,'process_identity',lambda pid:new)
    if fails:monkeypatch.setattr(h,'verify_native',lambda *a:{'parameters':{'changed':True}})
    assert h.prepare_new_worker(Runtime(f,'cst')) is (not fails)
    s=read(f/'session.json');assert s['status']=='closing'
    if fails:assert 'new_worker_ready' not in s['worker_upgrade'] and s['worker_upgrade']['new_worker_error']
    else:assert s['worker_upgrade']['new_worker_ready']==new


def test_ordinary_finish_cannot_bypass_lost_native_de(handoff):
    m,r,f,live,args,h=handoff
    m.begin_native_worker_handoff(r['session_id'],r['credential'],**args);live.remove(22)
    with pytest.raises(ServiceError) as error:m.finish_worker_upgrade(r['session_id'],r['credential'])
    assert error.value.code=='session_maintenance'
    assert read(f/'session.json')['status']=='closing'


@pytest.mark.parametrize('failure',['drift','expired','foreign_token'])
def test_release_requires_fresh_matching_worker_ack(handoff,monkeypatch,failure):
    from tpc_service.sessions.native import Runtime
    m,r,f,live,args,h=handoff;sid,cred=r['session_id'],r['credential'];proof={'parameters':{}}
    monkeypatch.setattr(h,'verify_native',lambda runtime,state:observed(runtime,proof))
    m.begin_native_worker_handoff(sid,cred,**args);m.finish_native_worker_handoff(sid,cred)
    s=read(f/'session.json');new={'pid':33,'started':3,'image':'python.exe'};live.remove(11);live.add(33)
    s.update(worker=new,worker_capabilities=[h.CAPABILITY,'hf-tet-adaptation-controls-v1'])
    s['worker_upgrade'].update(phase='starting',stop_ack=True,new_worker_ready=new,new_worker_native=proof)
    write(f/'session.json',s);monkeypatch.setattr(h,'process_identity',lambda pid:new)
    m.finish_native_worker_handoff(sid,cred)
    if failure=='drift':monkeypatch.setattr(h,'verify_native',lambda *a:{'parameters':{'changed':1}})
    accepted=h.verify_release(Runtime(f,'cst'))
    if failure=='drift':
        assert not accepted
    else:
        assert accepted
        s=read(f/'session.json');token=s['worker_upgrade']['release_token']
        if failure=='expired':s['worker_upgrade']['release_verified_at']-=10
        else:s['worker_upgrade']['release_ack']='wrong'
        write(f/'session.json',s)
        result=m.finish_native_worker_handoff(sid,cred)
        assert result['phase']=='release_requested' and result['release_token']!=token
    assert read(f/'session.json')['status']=='closing'


@pytest.mark.parametrize('launch_fails',[False,True])
def test_launch_token_is_required_and_consumed_once(handoff,monkeypatch,launch_fails):
    from tpc_service.sessions import manager as module
    m,r,f,live,args,h=handoff
    m.begin_native_worker_handoff(r['session_id'],r['credential'],**args)
    s=read(f/'session.json');s.update(worker=None);s['worker_upgrade'].update(phase='starting',stop_ack=True)
    token=s['worker_upgrade']['token'];write(f/'session.json',s);live.remove(11)
    seen=[]
    def launch(*a,**k):
        seen.append(1)
        if launch_fails:raise OSError('uncertain launch')
        from types import SimpleNamespace
        return SimpleNamespace(pid=33)
    monkeypatch.setattr(module.subprocess,'Popen',launch)
    monkeypatch.setattr(module,'process_identity',lambda pid:{'pid':pid,'started':3,'image':'python.exe'})
    with pytest.raises(ServiceError):m._launch(f,recover=True)
    assert not seen
    if launch_fails:
        with pytest.raises(OSError):m._launch(f,recover=True,native_handoff_token=token)
    else:m._launch(f,recover=True,native_handoff_token=token)
    assert read(f/'session.json')['worker_upgrade']['launch_claimed'] is True
    with pytest.raises(ServiceError):m._launch(f,recover=True,native_handoff_token=token)
    assert seen==[1]


def test_reconcile_and_submit_cannot_bypass_frozen_error_state(handoff):
    m,r,f,live,args,h=handoff;sid,cred=r['session_id'],r['credential']
    m.begin_native_worker_handoff(sid,cred,**args)
    s=read(f/'session.json');s['status']='needs_reconcile';write(f/'session.json',s)
    with pytest.raises(ServiceError) as error:
        m.reconcile(sid,cred,'review',args['project_digests'],confirm_idle=True,environment_identity=args['environment_identity'])
    assert error.value.code=='session_maintenance'
    with pytest.raises(ServiceError):m.submit(sid,cred,'no','start')
    assert read(f/'session.json')['worker_upgrade']['phase']=='reviewing'


def test_dialog_failure_preserves_structured_snapshot(handoff,monkeypatch):
    from cst_solver.dialogs import CstDialogTimeout
    m,r,f,live,args,h=handoff
    m.begin_native_worker_handoff(r['session_id'],r['credential'],**args)
    details={'dialogs':[{'pid':22,'title':'Unknown','body':'Do not proceed','buttons':['Cancel']}]}
    def fail(*a):raise CstDialogTimeout('blocked',details)
    monkeypatch.setattr(h,'verify_native',fail)
    with pytest.raises(CstDialogTimeout):m.finish_native_worker_handoff(r['session_id'],r['credential'])
    assert read(f/'session.json')['worker_upgrade']['last_verification_error']['details']==details


def test_cli_begin_freezes_only_and_mcp_uses_same_guard(handoff,monkeypatch,capsys):
    from tpc_service.sessions.__main__ import main
    from cst_mcp import tools
    from cst_mcp.session_tools import register_session_tools
    m,r,f,live,args,h=handoff;review=f/'review.json';reference=f/'reference.json'
    write(review,args);write(reference,dict(r,root=str(m.root)))
    monkeypatch.setattr(h,'verify_native',lambda *a:pytest.fail('Begin must not touch CST'))
    assert main(['--root',str(m.root),'--reference',str(reference),'begin-native-worker-handoff',
                 '--review-file',str(review)])==0
    assert 'reviewing' in capsys.readouterr().out
    for name in ('TOOL_SPECS','HANDLERS','READ_TOOLS','WRITE_TOOLS'):
        monkeypatch.setattr(tools,name,getattr(tools,name).copy())
    register_session_tools(str(m.root),backend='cst')
    result=tools.dispatch('begin_cst_native_worker_handoff',dict(
        session_id=r['session_id'],credential=r['credential'],review=args))
    assert result['ok'] and result['upgrade']['phase']=='reviewing'
    assert 'finish_cst_native_worker_handoff' in tools.WRITE_TOOLS


def test_unapproved_direct_worker_start_does_not_replace_identity(handoff,monkeypatch):
    from tpc_service.sessions import worker
    m,r,f,live,args,h=handoff
    m.begin_native_worker_handoff(r['session_id'],r['credential'],**args)
    before=read(f/'session.json')
    monkeypatch.setattr(worker,'process_identity',lambda pid:{'pid':99,'started':1,'image':'python.exe'})
    worker.run(f)
    after=read(f/'session.json')
    assert after['worker_upgrade'].pop('startup_error')['code']=='native_handoff_refused'
    assert after==before

@pytest.mark.parametrize('case', ['child','direct','wrong_parent','wrong_token','wrong_image','replay'])
def test_startup_admission_binds_token_and_launcher(handoff, monkeypatch, case):
    import os
    from tpc_service.sessions import worker
    m,r,f,live,args,h=handoff
    m.begin_native_worker_handoff(r['session_id'],r['credential'],**args)
    launcher={'pid':33,'started':3,'image':'venv/python.exe'}
    child=launcher if case=='direct' else {'pid':44,'started':4,'image':'base/python.exe'}
    s=read(f/'session.json');s['worker']=launcher
    s['worker_upgrade'].update(phase='starting',launch_claimed=True,launch_nonce_digest=digest('secret'),
        launcher=launcher,expected_worker_image=child['image'],stop_ack=True)
    if case=='replay':s['worker_upgrade']['startup_worker']=child
    write(f/'session.json',s)
    monkeypatch.setattr(h,'process_identity',lambda pid: child if pid==os.getpid() else launcher)
    monkeypatch.setattr(h.os,'getppid',lambda:99 if case=='wrong_parent' else 33)
    if case=='wrong_image':s['worker_upgrade']['expected_worker_image']='other.exe';write(f/'session.json',s)
    if case in ('child','direct'):
        assert h.admit_worker(s,'secret')==child
        assert s['worker_upgrade']['startup_worker']==child
    else:
        with pytest.raises(ServiceError):h.admit_worker(s,'wrong' if case=='wrong_token' else 'secret')


def test_failed_launch_recovery_rotates_token_without_launch(handoff,monkeypatch):
    m,r,f,live,args,h=handoff;sid,cred=r['session_id'],r['credential']
    proof={'parameters':{}}
    monkeypatch.setattr(h,'verify_native',lambda *a:proof)
    m.begin_native_worker_handoff(sid,cred,**args);m.finish_native_worker_handoff(sid,cred)
    s=read(f/'session.json');old=s['worker_upgrade']['token'];launcher={'pid':33,'started':3,'image':'venv.exe'}
    s['worker']=launcher;s['worker_upgrade'].update(phase='starting',stop_ack=True,launch_claimed=True,launch_attempted=True)
    write(f/'session.json',s);live.remove(11)
    monkeypatch.setattr(h,'process_identity',lambda pid:None)
    monkeypatch.setattr(m,'_launch',lambda *a,**k:pytest.fail('Recovery must not launch'))
    result=m.recover_native_worker_handoff(sid,cred,expected_token=old,expected_launcher=launcher,
        review_note='Reviewed failed pre-admission process tree is gone',confirm_no_worker_processes=True)
    assert result['phase']=='stop_requested' and result['token']!=old
    assert result['failed_launches'][0]['token']==old
    assert read(f/'session.json')['worker'] is None
    with pytest.raises(ServiceError):
        m.recover_native_worker_handoff(sid,cred,expected_token=old,expected_launcher=launcher,
            review_note='retry',confirm_no_worker_processes=True)

@pytest.mark.parametrize('failure',['alive_launcher','admitted','ready','wrong_token','missing_review','native_drift','worker_lock'])
def test_recovery_cannot_bypass_uncertainty(handoff,monkeypatch,failure):
    from contextlib import nullcontext
    from tpc_service.sessions.store import lock
    m,r,f,live,args,h=handoff;sid,cred=r['session_id'],r['credential'];proof={'parameters':{}}
    monkeypatch.setattr(h,'verify_native',lambda *a:proof)
    m.begin_native_worker_handoff(sid,cred,**args);m.finish_native_worker_handoff(sid,cred)
    s=read(f/'session.json');launcher={'pid':33,'started':3,'image':'venv.exe'};s['worker']=launcher
    s['worker_upgrade'].update(phase='starting',stop_ack=True,launch_claimed=True)
    if failure=='admitted':s['worker_upgrade']['startup_worker']=launcher
    if failure=='ready':s['worker_upgrade']['new_worker_ready']=launcher
    write(f/'session.json',s);live.remove(11)
    monkeypatch.setattr(h,'process_identity',lambda pid:launcher if failure=='alive_launcher' else None)
    if failure=='native_drift':monkeypatch.setattr(h,'verify_native',lambda *a:{'changed':True})
    with lock(f/'worker.lock',blocking=False) if failure=='worker_lock' else nullcontext():
        with pytest.raises(ServiceError):
            m.recover_native_worker_handoff(sid,cred,
                expected_token='wrong' if failure=='wrong_token' else s['worker_upgrade']['token'],
                expected_launcher=launcher,review_note='Reviewed',confirm_no_worker_processes=failure!='missing_review')
    assert read(f/'session.json')==s


def test_real_python_launcher_registers_actual_worker_without_sdk(handoff,monkeypatch):
    import subprocess
    from tpc_service.sessions import manager as module
    m,r,f,live,args,h=handoff
    m.begin_native_worker_handoff(r['session_id'],r['credential'],**args)
    s=read(f/'session.json');s['worker']=None;s['worker_upgrade'].update(phase='starting',stop_ack=True)
    write(f/'session.json',s);live.remove(11)
    original=subprocess.Popen;processes=[]
    code='''import sys,os
from pathlib import Path
from tpc_service.sessions.store import lock,read,write
from tpc_service.sessions.native_handoff import admit_worker,STARTUP_ENV
folder=Path(sys.argv[1])
with lock(folder/'worker.lock'),lock(folder/'state.lock'):
    state=read(folder/'session.json')
    state['worker']=admit_worker(state,os.environ.pop(STARTUP_ENV,None))
    assert not any(k=='cst' or k.startswith('cst.') for k in sys.modules)
    write(folder/'session.json',state)
'''
    def launch(command,**kwargs):
        process=original([command[0],'-c',code,str(f)],**kwargs);processes.append(process);return process
    monkeypatch.setattr(module.subprocess,'Popen',launch)
    m._launch(f,recover=True,native_handoff_token=s['worker_upgrade']['token'])
    assert processes[0].wait(timeout=20)==0, (f/'worker.log').read_text()
    result=read(f/'session.json');record=result['worker_upgrade']
    assert record['startup_worker']==result['worker']
    assert record['launcher']['pid']==processes[0].pid
    assert result['status']=='closing' and result['environment']==s['environment']

@pytest.mark.parametrize('case',['valid','missing_confirm','missing_risk','contradictory'])
def test_owned_worker_handoff_requires_distinct_explicit_review(handoff,monkeypatch,case):
    m,r,f,live,args,h=handoff
    args.update(worker_ownership='owned',confirm_borrowed_worker=False,confirm_owned_worker=True,
                accept_owned_worker_exit_risk=True)
    if case=='missing_confirm':args['confirm_owned_worker']=False
    if case=='missing_risk':args['accept_owned_worker_exit_risk']=False
    if case=='contradictory':args['confirm_borrowed_worker']=True
    monkeypatch.setattr(h,'verify_native',lambda *a:pytest.fail('Begin never touches CST'))
    before=read(f/'session.json')
    if case=='valid':
        record=m.begin_native_worker_handoff(r['session_id'],r['credential'],**args)
        assert record['worker_ownership']=='owned'
        assert record['borrowed_worker_asserted_by_caller'] is False
        assert record['owned_worker_exit_risk_accepted'] is True
        args.update(worker_ownership='borrowed',confirm_borrowed_worker=True,confirm_owned_worker=False,
                    accept_owned_worker_exit_risk=False)
        with pytest.raises(ServiceError):m.begin_native_worker_handoff(r['session_id'],r['credential'],**args)
    else:
        with pytest.raises(ServiceError):m.begin_native_worker_handoff(r['session_id'],r['credential'],**args)
        assert read(f/'session.json')==before


def test_owned_exit_lost_de_never_launches_replacement(handoff,monkeypatch):
    m,r,f,live,args,h=handoff;sid,cred=r['session_id'],r['credential']
    args.update(worker_ownership='owned',confirm_borrowed_worker=False,confirm_owned_worker=True,
                accept_owned_worker_exit_risk=True)
    monkeypatch.setattr(h,'verify_native',lambda *a:{'parameters':{}})
    m.begin_native_worker_handoff(sid,cred,**args);m.finish_native_worker_handoff(sid,cred)
    s=read(f/'session.json');s['worker_upgrade']['stop_ack']=True;write(f/'session.json',s)
    live.clear();monkeypatch.setattr(m,'_launch',lambda *a,**k:pytest.fail('Never replace lost DE'))
    with pytest.raises(ServiceError):m.finish_native_worker_handoff(sid,cred)
    assert read(f/'session.json')==s
