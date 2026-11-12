import hashlib
import pytest
from types import SimpleNamespace
from tpc_service.errors import ServiceError
from tpc_service.sessions.store import write, digest


def setup_state(tmp_path):
    path=tmp_path/'model.cst'; path.write_bytes(b'baseline')
    sha=hashlib.sha256(b'baseline').hexdigest()
    error={'code':'session_static_sp_prepare_failed','details':{'mutation_may_have_occurred':True}}
    job={'job_id':'job-failed','session_id':'session',
        'status':'failed','finished_at':1,'operation':'prepare_static_sp',
        'params':{'project_id':'p'},'error':error}
    write(tmp_path/'jobs'/'job-failed.json',job)
    partial={'failed_job_id':'job-failed','project_id':'p','snapshot_digest':'a'*64,
             'failed_job_digest':digest(job),'saved_disk_only':True}
    handoff={'mode':'preserve_native_de_v1','phase':'complete','return_to_fence':True,
             'static_partial':partial,'project_digests':{'p':sha},
             'release_native':{'static_partial':{'p':'a'*64}},'environment':{'pid':2},'new_worker':{'pid':1}}
    state={'session_id':'session','backend':'cst','status':'needs_reconcile','last_error':error,
           'worker':{'pid':1},'environment':{'pid':2},'worker_capabilities':['static-sp-fenced-recovery-v1','static-sp-self-em-exclusion-v1'],
           'projects':{'p':{'path':str(path),'saved':True,'saved_digest':sha}},'last_worker_upgrade':handoff}
    return state, {'project_id':'p','failed_job_id':'job-failed','expected_disk_digest':sha,
                   'snapshot_digest':'a'*64,'confirm_idle':True}


def test_capture_preflight_accepts_only_matching_handoff(tmp_path, monkeypatch):
    from tpc_service.sessions import static_fenced_recovery as s
    state, params=setup_state(tmp_path)
    monkeypatch.setattr(s,'alive',lambda identity:True)
    monkeypatch.setattr(s.JobIndex,'load',lambda folder:SimpleNamespace(active_jobs=lambda:[]))
    assert s.preflight(tmp_path,state,params)['failed_job_id']=='job-failed'
    state['last_worker_upgrade']['release_native']['static_partial']['p']='b'*64
    with pytest.raises(ServiceError): s.preflight(tmp_path,state,params)


@pytest.mark.parametrize('issue',['disk','worker','queued','failure'])
def test_capture_rejects_unreviewed_or_unsafe_state(tmp_path, monkeypatch, issue):
    from tpc_service.sessions import static_fenced_recovery as s
    state, params=setup_state(tmp_path)
    monkeypatch.setattr(s,'alive',lambda identity:True)
    active=[]
    monkeypatch.setattr(s.JobIndex,'load',lambda folder:SimpleNamespace(active_jobs=lambda:active))
    if issue=='disk': (tmp_path/'model.cst').write_bytes(b'changed')
    if issue=='worker': state['worker_capabilities']=[]
    if issue=='queued': active.append({'job_id':'other'})
    if issue=='failure': state['last_error']={'code':'other'}
    with pytest.raises(ServiceError): s.preflight(tmp_path,state,params)


def test_prewrite_refusal_preserves_original_failure_fence():
    from tpc_service.sessions.worker import _finish_failed_job
    original={'code':'session_static_sp_prepare_failed'}
    state={'status':'needs_reconcile','last_error':original,'uncertain_jobs':[]}
    job={'operation':'capture_failed_static','params':{}}
    error={'code':'session_static_recovery_refused','message':'snapshot changed'}
    _finish_failed_job(job,error,state)
    assert state['last_error']==original and state['status']=='needs_reconcile'
    assert state['last_static_recovery_error']==error


@pytest.mark.parametrize('operation', ['capture_failed_static','complete_failed_static_task','inspect_failed_static_task','exclude_unconnected_self_em','read_fenced_static_impedances'])
def test_invalid_fenced_recovery_never_starts_or_opens_session(tmp_path, operation):
    from unittest.mock import Mock
    from tpc_service.sessions.manager import SessionManager
    manager=SessionManager(tmp_path/'sessions',backend='cst')
    manager._folder=Mock(side_effect=AssertionError('invalid request reached session'))
    manager._launch=Mock(side_effect=AssertionError('invalid request launched worker'))
    with pytest.raises(ServiceError):
        manager.submit('session','credential','request',operation,{'project_id':'p'})
    manager._folder.assert_not_called();manager._launch.assert_not_called()


def test_capture_saves_only_reviewed_dirty_snapshot_and_keeps_fence(tmp_path, monkeypatch):
    from unittest.mock import Mock
    from tpc_service.sessions import static_fenced_recovery as s
    from cst_solver import dialogs
    from cst_solver.circuit import adapter as circuit_adapter
    state, params=setup_state(tmp_path)
    snapshot={'blocks':[{'name':'reviewed'}], 'unknown':[]}
    params['snapshot_digest']=digest(snapshot)
    handoff=state['last_worker_upgrade']; handoff['static_partial']['snapshot_digest']=params['snapshot_digest']
    handoff['release_native']['static_partial']['p']=params['snapshot_digest']
    handle=SimpleNamespace(filename=lambda: state['projects']['p']['path'],
                           model3d=SimpleNamespace(is_solver_running=lambda **kw:False))
    app=SimpleNamespace(cst_file=handle,circuit=SimpleNamespace(adapter=SimpleNamespace(inspect=lambda:snapshot)))
    monkeypatch.setattr(circuit_adapter,'NativeAdapter',lambda app:app.circuit.adapter)
    state['environment']={'pid':2}
    def save(app, project_id):
        path=tmp_path/'model.cst';path.write_bytes(b'partial-saved')
        state['projects']['p']['saved_digest']=hashlib.sha256(b'partial-saved').hexdigest()
        return state['projects']['p']
    runtime=SimpleNamespace(folder=tmp_path,backend='cst',app=app,handles={'p':handle},
                            state=lambda:state,check_saved=Mock(),save=Mock(side_effect=save))
    monkeypatch.setattr(s,'alive',lambda identity:True)
    monkeypatch.setattr(s.JobIndex,'load',lambda folder:SimpleNamespace(active_jobs=lambda:[]))
    monkeypatch.setattr(dialogs,'check_dialogs',lambda **kw:None)
    report=s.capture(runtime, {'job_id':'capture-1','params':params})
    assert report['saved'] and report['original_failed_job_id']=='job-failed'
    assert state['status']=='needs_reconcile' and state['last_error']['code']=='session_static_sp_prepare_failed'
    runtime.save.assert_called_once_with(app,'p')


def test_capture_never_saves_changed_memory(tmp_path, monkeypatch):
    from unittest.mock import Mock
    from tpc_service.sessions import static_fenced_recovery as s
    from cst_solver import dialogs
    from cst_solver.circuit import adapter as circuit_adapter
    state, params=setup_state(tmp_path);state['environment']={'pid':2}
    handle=SimpleNamespace(filename=lambda:state['projects']['p']['path'],
                           model3d=SimpleNamespace(is_solver_running=lambda **kw:False))
    app=SimpleNamespace(cst_file=handle,circuit=SimpleNamespace(adapter=SimpleNamespace(inspect=lambda:{'changed':True})))
    monkeypatch.setattr(circuit_adapter,'NativeAdapter',lambda app:app.circuit.adapter)
    runtime=SimpleNamespace(folder=tmp_path,backend='cst',app=app,handles={'p':handle},
                            state=lambda:state,check_saved=Mock(),save=Mock())
    monkeypatch.setattr(s,'alive',lambda identity:True)
    monkeypatch.setattr(s.JobIndex,'load',lambda folder:SimpleNamespace(active_jobs=lambda:[]))
    monkeypatch.setattr(dialogs,'check_dialogs',lambda **kw:None)
    with pytest.raises(ServiceError): s.capture(runtime, {'job_id':'capture-1','params':params})
    runtime.save.assert_not_called()


def test_completion_preflight_binds_saved_capture_and_original_intent(tmp_path, monkeypatch):
    from tpc_service.sessions import static_fenced_recovery as s
    state, params=setup_state(tmp_path)
    from tpc_service.sessions.store import read
    old=read(tmp_path/'jobs'/'job-failed.json')
    old['params']['spec']={'task':{'task_name':'SP'}}
    write(tmp_path/'jobs'/'job-failed.json',old)
    state['last_worker_upgrade']['static_partial']['failed_job_digest']=digest(old)
    capture={'job_id':'capture-1','session_id':'session','operation':'capture_failed_static','status':'succeeded',
             'params':params,'result':{'saved':True,'saved_digest':params['expected_disk_digest'],
                'snapshot_digest':params['snapshot_digest'],'original_failed_job_id':'job-failed'}}
    write(tmp_path/'jobs'/'capture-1.json',capture)
    monkeypatch.setattr(s,'alive',lambda identity:True)
    monkeypatch.setattr(s.JobIndex,'load',lambda folder:SimpleNamespace(active_jobs=lambda:[]))
    request={'project_id':'p','failed_job_id':'job-failed','capture_job_id':'capture-1',
             'expected_saved_digest':params['expected_disk_digest'],'snapshot_digest':params['snapshot_digest'],
             'expected_task':{},'confirm_idle':True}
    result=s.completion_preflight(tmp_path,state,request)
    assert result['original']['params']['spec']['task']['task_name']=='SP'
    capture['result']['snapshot_digest']='b'*64;write(tmp_path/'jobs'/'capture-1.json',capture)
    with pytest.raises(ServiceError): s.completion_preflight(tmp_path,state,request)


@pytest.mark.parametrize('unexpected_change',[False,True])
def test_completion_changes_only_existing_task_and_keeps_fence(tmp_path, monkeypatch, unexpected_change):
    from unittest.mock import Mock
    from cst_solver import dialogs
    from cst_solver.circuit import linear_sp
    from cst_solver.circuit import adapter as circuit_adapter
    from cst_solver.circuit.static_sp import prepare_static_sp
    from tpc_service.sessions import static_fenced_recovery as s
    from test_static_sp_prepare import fixture
    adapter, spec=fixture(tmp_path,monkeypatch)
    prepare_static_sp(adapter,spec)
    before=adapter.inspect(); snapshot=digest(before)
    state, params=setup_state(tmp_path)
    project=tmp_path/'device.cst'; sha=hashlib.sha256(project.read_bytes()).hexdigest()
    state['projects']['p']={'path':str(project),'saved':True,'saved_digest':sha}
    from tpc_service.sessions.store import read
    original=read(tmp_path/'jobs'/'job-failed.json');original['params']['spec']=spec
    write(tmp_path/'jobs'/'job-failed.json',original)
    handoff=state['last_worker_upgrade'];handoff['static_partial'].update(snapshot_digest=snapshot,failed_job_digest=digest(original))
    handoff['release_native']['static_partial']['p']=snapshot
    capture={'job_id':'capture-1','session_id':'session','operation':s.CAPTURE,'status':'succeeded',
             'params':{'project_id':'p'},'result':{'saved':True,'saved_digest':sha,'snapshot_digest':snapshot,
             'original_failed_job_id':'job-failed'}}
    write(tmp_path/'jobs'/'capture-1.json',capture)
    request={'project_id':'p','failed_job_id':'job-failed','capture_job_id':'capture-1','expected_saved_digest':sha,
             'snapshot_digest':snapshot,'expected_task':{},'confirm_idle':True}
    handle=SimpleNamespace(filename=lambda:str(project),model3d=SimpleNamespace(is_solver_running=lambda **kw:False))
    app=SimpleNamespace(cst_file=handle,circuit=SimpleNamespace(adapter=adapter))
    monkeypatch.setattr(circuit_adapter,'NativeAdapter',lambda app:app.circuit.adapter)
    def save(app,project_id):
        project.write_bytes(b'completed');state['projects']['p']['saved_digest']=hashlib.sha256(b'completed').hexdigest()
        return state['projects']['p']
    runtime=SimpleNamespace(folder=tmp_path,backend='cst',app=app,handles={'p':handle},state=lambda:state,
                            check_saved=Mock(),save=Mock(side_effect=save))
    monkeypatch.setattr(s,'alive',lambda identity:True)
    monkeypatch.setattr(s.JobIndex,'load',lambda folder:SimpleNamespace(active_jobs=lambda:[]))
    monkeypatch.setattr(dialogs,'check_dialogs',lambda **kw:None)
    def complete(*args,**kwargs):
        if unexpected_change: adapter.select('Block','P').SetDoubleProperty('Ri','1')
        return {'solver_verified':False}
    monkeypatch.setattr(linear_sp,'complete_existing_linear_sp_task',complete)
    if unexpected_change:
        with pytest.raises(ServiceError,match='Unrelated circuit state'):
            s.complete_task(runtime,{'job_id':'completion-1','params':request})
        runtime.save.assert_not_called()
        return
    report=s.complete_task(runtime,{'job_id':'completion-1','params':request})
    assert report['saved'] and not report['solver_verified'] and state['status']=='needs_reconcile'
    assert report['original_failed_job_id']=='job-failed' and report['network_sha256']==spec['network_sha256']


def test_exclusion_preflight_requires_matching_completed_task_and_saved_snapshot(tmp_path,monkeypatch):
    from tpc_service.sessions import static_fenced_recovery as s
    state, capture_params=setup_state(tmp_path)
    snapshot={'blocks':[{'name':'self'}],'unknown':[]}; snapshot_sha=digest(snapshot)
    completed={'job_id':'complete-1','session_id':'session','operation':'complete_failed_static_task','status':'succeeded',
        'params':{'project_id':'p','failed_job_id':'job-failed'},
        'result':{'saved':True,'saved_digest':capture_params['expected_disk_digest'],
                  'original_failed_job_id':'job-failed','after':snapshot}}
    write(tmp_path/'jobs'/'complete-1.json',completed)
    monkeypatch.setattr(s,'alive',lambda identity:True)
    monkeypatch.setattr(s.JobIndex,'load',lambda folder:SimpleNamespace(active_jobs=lambda:[]))
    request={'project_id':'p','failed_job_id':'job-failed','completion_job_id':'complete-1',
             'expected_saved_digest':capture_params['expected_disk_digest'],'snapshot_digest':snapshot_sha,
             'block_name':'self','confirm_idle':True,'confirm_static_only_copy':True}
    assert s.exclusion_preflight(tmp_path,state,request)['job_id']=='complete-1'
    request['snapshot_digest']='0'*64
    with pytest.raises(ServiceError): s.exclusion_preflight(tmp_path,state,request)
    request['snapshot_digest']=snapshot_sha
    state['worker_capabilities']=['static-sp-fenced-recovery-v1']
    with pytest.raises(ServiceError): s.exclusion_preflight(tmp_path,state,request)


@pytest.mark.parametrize('unexpected_3d_change',[False,True])
def test_exclusion_preserves_unrelated_circuit_and_3d_inventory(tmp_path,monkeypatch,unexpected_3d_change):
    from unittest.mock import Mock
    from cst_solver import dialogs
    from cst_solver.circuit import adapter as circuit_adapter, static_sp
    from cst_solver.simulation import port_replacement
    from tpc_service.sessions import static_fenced_recovery as s, inspection
    from tpc_service.sessions.store import read
    from test_static_self_em_exclusion import fake_adapter
    state, unused=setup_state(tmp_path);adapter=fake_adapter(tmp_path)
    project=tmp_path/'model.cst';sha=hashlib.sha256(project.read_bytes()).hexdigest()
    state['projects']['p']['saved_digest']=sha
    original=read(tmp_path/'jobs'/'job-failed.json')
    original['params']['spec']={'network_block':'network','network_sha256':'b'*64}
    write(tmp_path/'jobs'/'job-failed.json',original)
    state['last_worker_upgrade']['static_partial']['failed_job_digest']=digest(original)
    before=adapter.inspect();snap=digest(before)
    completed={'job_id':'complete-1','session_id':'session','operation':s.COMPLETE,'status':'succeeded',
        'params':{'project_id':'p','failed_job_id':'job-failed'},
        'result':{'saved':True,'saved_digest':sha,'original_failed_job_id':'job-failed','after':before}}
    write(tmp_path/'jobs'/'complete-1.json',completed)
    request={'project_id':'p','failed_job_id':'job-failed','completion_job_id':'complete-1',
             'expected_saved_digest':sha,'snapshot_digest':snap,'block_name':'self',
             'confirm_idle':True,'confirm_static_only_copy':True}
    original_select=adapter.select
    def select(kind,name):
        if name=='network': return SimpleNamespace(GetFile=lambda:str(tmp_path/'model'/'Model'/'DS'/'Block'/'n.s2p'))
        return original_select(kind,name)
    adapter.select=select;adapter.dependencies=lambda:{'complete':True,'unknown':[],'files':[]}
    handle=SimpleNamespace(filename=lambda:str(project),model3d=SimpleNamespace(is_solver_running=lambda **kw:False))
    app=SimpleNamespace(cst_file=handle,circuit=SimpleNamespace(adapter=adapter))
    def save(app,project_id):
        project.write_bytes(b'saved');state['projects']['p']['saved_digest']=hashlib.sha256(b'saved').hexdigest()
        return state['projects']['p']
    runtime=SimpleNamespace(folder=tmp_path,backend='cst',app=app,handles={'p':handle},state=lambda:state,
                            check_saved=Mock(),save=Mock(side_effect=save))
    monkeypatch.setattr(s,'alive',lambda identity:True)
    monkeypatch.setattr(s.JobIndex,'load',lambda folder:SimpleNamespace(active_jobs=lambda:[]))
    monkeypatch.setattr(dialogs,'check_dialogs',lambda **kw:None)
    monkeypatch.setattr(circuit_adapter,'NativeAdapter',lambda app:adapter)
    monkeypatch.setattr(static_sp,'validate_prepare_spec',lambda spec:None)
    monkeypatch.setattr(static_sp,'_sha',lambda path:'b'*64)
    monkeypatch.setattr(s,'_model3d_files',lambda path:{'ModelHistory.json':'a'*64})
    monkeypatch.setattr(port_replacement,'port_inventory',lambda app:{'1':{'type':'Discrete'}})
    def inspect_3d(app,params):
        changed=unexpected_3d_change and not original_select('Block','self').DoesExist()
        return {'errors':[],'solids':{'shape':{'volume':2 if changed else 1}}}
    monkeypatch.setattr(inspection,'inspect_native',inspect_3d)
    if unexpected_3d_change:
        with pytest.raises(ServiceError,match='3D inventory'): s.exclude_self_em(runtime,{'job_id':'exclude-1','params':request})
        runtime.save.assert_not_called();assert state['status']=='needs_reconcile'
        return
    result=s.exclude_self_em(runtime,{'job_id':'exclude-1','params':request})
    assert result['saved'] and result['3d_inventory_unchanged'] and not result['no_em_dependency_verified']
    assert not result['geometry_verified'] and state['status']=='needs_reconcile'


@pytest.mark.parametrize('bad_impedance',[False,True])
def test_fenced_impedance_read_uses_exact_project_and_never_saves(tmp_path,monkeypatch,bad_impedance):
    from unittest.mock import Mock
    from cst_solver import dialogs
    from cst_solver.circuit import adapter as circuit_adapter, static_sp, native
    from tpc_service.sessions import static_fenced_recovery as s
    from tpc_service.sessions.store import read
    from test_static_self_em_exclusion import fake_adapter
    state,unused=setup_state(tmp_path);adapter=fake_adapter(tmp_path);project=tmp_path/'model.cst'
    static_sp.remove_unconnected_self_em_block(adapter,'self',expected_snapshot_digest=digest(adapter.inspect()))
    snapshot=adapter.inspect();sha=hashlib.sha256(project.read_bytes()).hexdigest();snap=digest(snapshot)
    state['projects']['p']['saved_digest']=sha
    original=read(tmp_path/'jobs'/'job-failed.json')
    original['params']['spec']={'task':{'task_name':'SP','port_impedances':{'P':50}}}
    write(tmp_path/'jobs'/'job-failed.json',original)
    state['last_worker_upgrade']['static_partial']['failed_job_digest']=digest(original)
    excluded={'job_id':'exclude-1','session_id':'session','operation':s.EXCLUDE,'status':'succeeded',
        'params':{'project_id':'p'},'result':{'saved':True,'saved_digest':sha,
            'original_failed_job_id':'job-failed','after':snapshot}}
    write(tmp_path/'jobs'/'exclude-1.json',excluded)
    params={'project_id':'p','failed_job_id':'job-failed','exclude_job_id':'exclude-1',
            'expected_saved_digest':sha,'snapshot_digest':snap,'confirm_idle':True}
    handle=SimpleNamespace(filename=lambda:str(project),model3d=SimpleNamespace(is_solver_running=lambda **kw:False))
    app=SimpleNamespace(cst_file=handle,circuit=SimpleNamespace(adapter=adapter))
    runtime=SimpleNamespace(folder=tmp_path,backend='cst',app=app,handles={'p':handle},state=lambda:state,
                            check_saved=Mock(),save=Mock())
    monkeypatch.setattr(s,'alive',lambda identity:True)
    monkeypatch.setattr(s.JobIndex,'load',lambda folder:SimpleNamespace(active_jobs=lambda:[]))
    monkeypatch.setattr(dialogs,'check_dialogs',lambda **kw:None)
    monkeypatch.setattr(circuit_adapter,'NativeAdapter',lambda app:adapter)
    monkeypatch.setattr(static_sp,'validate_prepare_spec',lambda spec:None)
    def read_impedance(project_arg,task,ports,**kw):
        assert project_arg is handle and task=='SP' and ports==['P']
        return {'ports':{'P':{'real':75 if bad_impedance else 50,'imaginary':0,'impedance_type':'Constant'}},
                'native_bridge_verified':False,'schematic_identity_verified':False}
    monkeypatch.setattr(native,'read_project_sp_impedances',read_impedance)
    if bad_impedance:
        with pytest.raises(ServiceError,match='impedance'): s.read_impedances(runtime,{'job_id':'read-1','params':params})
    else:
        report=s.read_impedances(runtime,{'job_id':'read-1','params':params})
        assert report['matches_requested'] and not report['impedances']['native_bridge_verified']
    runtime.save.assert_not_called();assert state['status']=='needs_reconcile'


def test_3d_file_inventory_detects_content_changes(tmp_path):
    from tpc_service.sessions.static_fenced_recovery import _model3d_files
    project=tmp_path/'model.cst';project.write_bytes(b'project')
    root=tmp_path/'model'/'Model'/'3D';root.mkdir(parents=True)
    (root/'ModelHistory.json').write_bytes(b'old')
    (root/'shape.sab').write_bytes(b'shape')
    before=_model3d_files(project)
    (root/'shape.sab').write_bytes(b'other')
    after=_model3d_files(project)
    assert before['ModelHistory.json']==after['ModelHistory.json']
    assert before['shape.sab']!=after['shape.sab']
