"""Initial intents are not mistaken for missing old projects on exact-DE attach."""
from pathlib import Path
from types import SimpleNamespace
import pytest
from tpc_service.errors import ServiceError
from tpc_service.sessions.native import Runtime, file_digest
from tpc_service.sessions.store import write, read
from tpc_service.tests.test_session_formal_paths import make_session, submit


def live_stub(tmp_path, monkeypatch):
    manager, ref, runtime=make_session(tmp_path)
    runtime.backend='cst'
    identity={'pid':424242}
    runtime.update(environment=identity,status='ready')
    events=[]; handles={}
    class App:
        def __init__(self):
            self.cst_file=None
            self.project=SimpleNamespace(list_open_projects=lambda:list(handles),get_open_project=lambda p:handles[p])
        def open(self,path):
            events.append(('open',path)); self.cst_file=SimpleNamespace(filename=lambda:path,activate=lambda:None); handles[path]=self.cst_file
        def new_project(self): events.append(('new','MWS')); self.cst_file=object()
        def new_circuit_project(self): events.append(('new','DS')); self.cst_file=object()
        def save(self,path,**kw): events.append(('save',path)); Path(path).write_bytes(b'new saved synthetic project')
        def get_messages(self): return []
    app=App()
    import cst_solver
    from cst_solver import environment
    from tpc_service.sessions import native
    monkeypatch.setattr(native,'alive',lambda value:value==identity)
    monkeypatch.setattr(environment,'environment_pid',lambda p:identity['pid'])
    monkeypatch.setattr(cst_solver,'setup',SimpleNamespace(attach=lambda **kw:events.append(('attach',kw['pid'])) or app))
    return manager,ref,runtime,app,events


@pytest.mark.parametrize('operation,kind',[('import_project','MWS'),('create_project','MWS'),('create_project','DS')])
def test_first_project_succeeds_after_worker_lost_handles(tmp_path,monkeypatch,operation,kind):
    manager,ref,runtime,app,events=live_stub(tmp_path,monkeypatch)
    path=tmp_path/'formal'/'New.cst'; source=tmp_path/'source.cst'; source.write_bytes(b'original untouched')
    p={'project_id':'new','project_type':kind,'working_path':str(path),'authorize_working_path':True}
    if operation=='import_project': p['source_path']=str(source)
    request=submit(manager,ref,'initial',operation,**p)
    result=runtime.execute(request)
    assert result['saved'] is True and result['project']['saved_digest']==file_digest(path)
    assert events[0]==('attach',424242)
    assert len([e for e in events if e[0]=='save'])==1
    assert source.read_bytes()==b'original untouched'
    assert 'last_resolution' not in runtime.state()
    assert runtime.state()['projects']['new']['project_id']=='new'


def test_unreviewed_existing_project_still_blocks_before_new_native_open(tmp_path,monkeypatch):
    manager,ref,runtime,app,events=live_stub(tmp_path,monkeypatch)
    old=tmp_path/'old.cst'; old.write_bytes(b'old baseline')
    runtime.update(projects={'old':dict(project_id='old',path=str(old),saved=True,saved_digest=file_digest(old))})
    source=tmp_path/'source.cst'; source.write_bytes(b'copy')
    request=submit(manager,ref,'new','import_project',project_id='new',source_path=str(source))
    with pytest.raises(ServiceError,match='matching explicit review'): runtime.execute(request)
    assert not any(e[0] in ('open','save','new') for e in events)


def test_unknown_native_open_keeps_pending_intent_and_does_not_fake_review(tmp_path,monkeypatch):
    manager,ref,runtime,app,events=live_stub(tmp_path,monkeypatch)
    source=tmp_path/'source.cst'; source.write_bytes(b'copy')
    request=submit(manager,ref,'new','import_project',project_id='new',source_path=str(source))
    def fail(path): raise RuntimeError('native open uncertain')
    app.open=fail
    with pytest.raises(RuntimeError): runtime.execute(request)
    state=runtime.state()
    assert state['projects']['new']['saved'] is False and 'last_resolution' not in state
    assert Path(state['projects']['new']['path']).read_bytes()==b'copy'


def test_old_failed_copied_import_continues_only_after_real_review_api(tmp_path,monkeypatch):
    manager,ref,runtime,app,events=live_stub(tmp_path,monkeypatch)
    source=tmp_path/'source.cst'; source.write_bytes(b'original')
    request=submit(manager,ref,'original-import','import_project',project_id='new',source_path=str(source))
    path=runtime.folder/'projects'/'new'/'model.cst'; path.parent.mkdir(parents=True); path.write_bytes(source.read_bytes())
    record=dict(project_id='new',path=str(path),source_path=str(source),saved=False)
    original_error={'code':'session_project_mismatch','message':'Absent saved project has no matching explicit review'}
    request.update(status='failed',error=original_error)
    write(runtime.folder/'jobs'/(request['job_id']+'.json'),request)
    runtime.update(projects={'new':record},status='needs_reconcile')
    with pytest.raises(ServiceError): submit(manager,ref,'no-bypass','set_parameters',project_id='new',values={'synthetic':1})
    manager.reconcile(ref['session_id'],ref['credential'],'Offline caller reviewed exact copied baseline and idle',
                      {'new':file_digest(path)},confirm_idle=True)
    reviewed=read(runtime.folder/'jobs'/(request['job_id']+'.json'))
    assert reviewed['error']==original_error and reviewed['resolution']['human_reviewed'] is True
    probe=submit(manager,ref,'inspect-reviewed','inspect',project_id='new')
    result=runtime.execute(probe)
    assert result['project']['project_id']=='new'
    assert len([e for e in events if e[0]=='open'])==1 and not any(e[0]=='save' for e in events)
    assert source.read_bytes()==b'original'
    assert submit(manager,ref,'original-import','import_project',project_id='new',source_path=str(source))['job_id']==request['job_id']
