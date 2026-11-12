import pytest

from tpc_service.errors import ServiceError


def test_initial_parameters_sort_dependencies_and_preserve_expressions():
    from tpc_service.sessions.initial_parameters import normalize
    result=normalize({'derived':'base*2','base':'1.5','other':'sqr(derived)'})
    assert list(result)==['base','derived','other']
    assert result['derived']=='base*2' and result['other']=='sqr(derived)'


@pytest.mark.parametrize('values',[{'a':'b+1'},{'a':'b','b':'a'},{'a':'1\nSolver.Start'}, {'A':'1','a':'2'}])
def test_initial_parameters_refuse_unknown_cycles_and_unsafe_text(values):
    from tpc_service.sessions.initial_parameters import normalize
    with pytest.raises((ValueError,ServiceError)): normalize(values)


def test_bad_initial_parameter_request_never_launches_worker(tmp_path,monkeypatch):
    from tpc_service.sessions.manager import SessionManager
    manager=SessionManager(tmp_path,backend='cst');ref=manager.ensure('initial','one')
    monkeypatch.setattr(manager,'_launch',lambda *a,**k:pytest.fail('must not launch'))
    with pytest.raises(ServiceError):
        manager.submit(ref['session_id'],ref['credential'],'r','initialize_parameters',{'project_id':'p'})


def test_reviewed_unbound_batch_queues_without_restarting_existing_worker(tmp_path,monkeypatch):
    import hashlib
    from tpc_service.sessions.manager import SessionManager
    from tpc_service.sessions.store import read,write,digest
    from tpc_service.sessions import initial_parameters
    manager=SessionManager(tmp_path,backend='cst');ref=manager.ensure('initial-ready','one')
    folder=tmp_path/ref['session_id'];path=folder/'model.cst';path.write_bytes(b'baseline')
    sha=hashlib.sha256(b'baseline').hexdigest();state=read(folder/'session.json')
    state.update(status='ready',worker={'pid':1},environment={'pid':2},worker_capabilities=['initial-parameters-v1'],
                 projects={'p':{'path':str(path),'saved':True,'saved_digest':sha}})
    write(folder/'session.json',state);monkeypatch.setattr(initial_parameters,'alive',lambda identity:True)
    monkeypatch.setattr(manager,'_launch',lambda *a,**k:pytest.fail('must not restart worker'))
    values={'base':'1','derived':'base*2'}
    params={'project_id':'p','values':values,'expected_saved_digest':sha,'preview_digest':digest(values),'confirm_idle':True}
    job=manager.submit(ref['session_id'],ref['credential'],'r','initialize_parameters',params,operation_id='initial')
    assert job['status']=='queued' and job['operation']=='initialize_parameters'


def test_initialization_uses_existing_batch_wrapper_and_checks_native_formulas(tmp_path,monkeypatch):
    from types import SimpleNamespace
    from tpc_service.sessions import initial_parameters as initial,inspection
    from cst_solver import dialogs
    from tpc_service.sessions.store import digest
    project=tmp_path/'model.cst';project.write_bytes(b'saved')
    import hashlib
    sha=hashlib.sha256(b'saved').hexdigest();values={'derived':'base*2','base':'1.5'}
    state={'backend':'cst','status':'ready','worker':{'pid':1},'environment':{'pid':2},
           'worker_capabilities':['initial-parameters-v1'],
           'projects':{'p':{'path':str(project),'saved':True,'saved_digest':sha}}}
    request={'project_id':'p','values':values,'expected_saved_digest':sha,'preview_digest':digest(values),'confirm_idle':True}
    observed={'parameters':{},'solids':{},'errors':[]};calls=[]
    def paras(names,expressions,log_flag=0):
        calls.append((names,expressions,log_flag))
        observed['parameters']={'base':{'value':1.5,'expression':'1.5'},'derived':{'value':3.0,'expression':'base*2'}}
    handle=SimpleNamespace(filename=lambda:str(project),model3d=SimpleNamespace(is_solver_running=lambda **kw:False))
    app=SimpleNamespace(cst_file=handle,paras=paras,validate_model=lambda:{'status':'success','rebuild_ok':True})
    runtime=SimpleNamespace(folder=tmp_path,backend='cst',app=app,handles={'p':handle},state=lambda:state,
        check_saved=lambda project:None,save=lambda app,pid:{'saved_digest':sha})
    monkeypatch.setattr(initial,'alive',lambda identity:True)
    monkeypatch.setattr(initial.JobIndex,'load',lambda folder:SimpleNamespace(active_jobs=lambda:[]))
    monkeypatch.setattr(inspection,'inspect_native',lambda *a:observed.copy())
    monkeypatch.setattr(dialogs,'check_dialogs',lambda **kw:None)
    report=initial.execute(runtime,{'job_id':'init','params':request})
    assert calls==[(['base','derived'],['1.5','base*2'],0)]
    assert report['native_expression_readback_verified'] and not report['solver_verified']


def test_write_failure_reports_uncertain_mutation_and_never_saves(tmp_path, monkeypatch):
    import hashlib
    from types import SimpleNamespace
    from cst_solver import dialogs
    from tpc_service.sessions import initial_parameters as initial, inspection
    from tpc_service.sessions.store import digest
    project = tmp_path / 'model.cst'
    project.write_bytes(b'saved')
    sha = hashlib.sha256(b'saved').hexdigest()
    values = {'base': '1'}
    state = {'backend': 'cst', 'status': 'ready', 'worker': {'pid': 1}, 'environment': {'pid': 2},
             'worker_capabilities': ['initial-parameters-v1'],
             'projects': {'p': {'path': str(project), 'saved': True, 'saved_digest': sha}}}
    request = {'project_id': 'p', 'values': values, 'expected_saved_digest': sha,
               'preview_digest': digest(values), 'confirm_idle': True}
    handle = SimpleNamespace(filename=lambda: str(project), model3d=SimpleNamespace(is_solver_running=lambda **kw: False))
    def partial_write(*args, **kwargs):
        raise RuntimeError('interrupted during native write')
    app = SimpleNamespace(cst_file=handle, paras=partial_write)
    runtime = SimpleNamespace(folder=tmp_path, backend='cst', app=app, handles={'p': handle}, state=lambda: state,
                              check_saved=lambda project: None, save=lambda *args: pytest.fail('must not save'))
    monkeypatch.setattr(initial, 'alive', lambda identity: True)
    monkeypatch.setattr(initial.JobIndex, 'load', lambda folder: SimpleNamespace(active_jobs=lambda: []))
    monkeypatch.setattr(inspection, 'inspect_native', lambda *args: {'parameters': {}, 'solids': {}, 'errors': []})
    monkeypatch.setattr(dialogs, 'check_dialogs', lambda **kw: None)
    with pytest.raises(ServiceError) as failure:
        initial.execute(runtime, {'job_id': 'partial', 'params': request})
    assert failure.value.code == 'session_initial_parameters_partial'
    assert failure.value.details['mutation_may_have_occurred'] is True
    assert (tmp_path / 'initial_parameters' / 'partial.before.json').is_file()


def test_partial_batch_failure_fences_session():
    from tpc_service.sessions.worker import _finish_failed_job
    state = {'status': 'ready', 'uncertain_jobs': []}
    job = {'operation': 'initialize_parameters', 'job_id': 'partial', 'params': {'project_id': 'p'}}
    _finish_failed_job(job, {'code': 'session_initial_parameters_partial', 'details': {'mutation_may_have_occurred': True}}, state)
    assert job['status'] == 'failed'
    assert state['status'] == 'needs_reconcile'
