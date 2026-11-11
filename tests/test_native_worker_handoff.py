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
        worker_capabilities=['cooperative-worker-upgrade-v1'],projects={
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
    assert read(f/'session.json')==before
