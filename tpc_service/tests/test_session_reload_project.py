from pathlib import Path
from types import SimpleNamespace
import hashlib
import pytest
# Test the native dispatch in isolation; guarded entry is covered by test_workflow_enforcement.
from tpc_service.sessions.operations import _execute_operation as execute
from tpc_service.sessions.validation import validate


def test_reload_requires_matching_review_and_discards_only_current_project_memory(tmp_path):
    p=tmp_path/'model.cst';p.write_bytes(b'saved');d=hashlib.sha256(p.read_bytes()).hexdigest();seen=[]
    project=SimpleNamespace(close=lambda: seen.append('close'))
    app=SimpleNamespace(cst_file=project)
    app.open=lambda path: (seen.append(('open',path)),setattr(app,'cst_file','reopened'))
    class Runtime:
        backend='cst'
        handles={}
        def state(self):return {'last_resolution':{'human_reviewed':True,'project_digests':{'p':d}}}
        def project(self,pid):return app,{'path':str(p),'saved_digest':d}
    job=dict(operation='reload_project',params={'project_id':'p','expected_digest':d})
    out=execute(Runtime(),job)
    assert seen==['close',('open',str(p))]
    assert out['reloaded'] and not out['saved'] and p.read_bytes()==b'saved'


def test_reload_rejects_unreviewed_or_changed_saved_baseline(tmp_path):
    p=tmp_path/'model.cst';p.write_bytes(b'saved');d=hashlib.sha256(p.read_bytes()).hexdigest()
    class Runtime:
        backend='cst'
        def state(self):return {'last_resolution':{}}
        def project(self,pid):return None,{'path':str(p),'saved_digest':d}
    with pytest.raises(Exception,match='review'):
        execute(Runtime(),dict(operation='reload_project',params={'project_id':'p','expected_digest':d}))


def test_reload_requires_explicit_saved_digest_before_acceptance():
    with pytest.raises(Exception,match='digest'):
        validate('reload_project',{'project_id':'p'})
