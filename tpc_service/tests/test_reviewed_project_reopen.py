from pathlib import Path
from types import SimpleNamespace
import hashlib,os
import pytest
from tpc_service.sessions.native import restore_reviewed_projects
from tpc_service.errors import ServiceError

def fixture(tmp_path):
    p=tmp_path/'model.cst';p.write_bytes(b'approved baseline')
    digest=hashlib.sha256(p.read_bytes()).hexdigest()
    state={'projects':{'p':{'path':str(p),'saved_digest':digest}},'last_resolution':{'human_reviewed':True,'project_digests':{'p':digest}}}
    opened=set();calls=[]
    def op(path):calls.append(path);opened.add(os.path.normcase(str(Path(path).resolve())))
    app=SimpleNamespace(open=op,project=SimpleNamespace(list_open_projects=lambda:list(opened)))
    return p,state,app,calls

def test_reopens_only_matching_explicitly_reviewed_saved_baseline(tmp_path):
    p,s,a,calls=fixture(tmp_path)
    paths=restore_reviewed_projects(a,s,set())
    assert calls==[str(p)]
    assert os.path.normcase(str(p.resolve())) in paths

def test_never_reopens_unreviewed_or_changed_project(tmp_path):
    p,s,a,calls=fixture(tmp_path)
    s['last_resolution']={}
    with pytest.raises(ServiceError):restore_reviewed_projects(a,s,set())
    assert not calls
    p,s,a,calls=fixture(tmp_path);p.write_bytes(b'changed')
    with pytest.raises(ServiceError):restore_reviewed_projects(a,s,set())
    assert not calls


def test_adopted_baseline_review_remains_valid_for_unchanged_ready_session(tmp_path):
    p,s,a,calls=fixture(tmp_path)
    record=s['projects']['p']; digest=record['saved_digest']
    s.update(status='ready',last_resolution={})
    record.update(saved=True, path_authorization={'operation':'adopt_project','working_path':str(p)},
                  adoption_review={'review_note':'User approved continuation','expected_digest':digest})
    restore_reviewed_projects(a,s,set())
    assert calls == [str(p)]


@pytest.mark.parametrize('change', ['fenced', 'uncertain', 'launch', 'digest', 'path', 'no_note'])
def test_adoption_review_cannot_bypass_uncertainty_or_changed_baseline(tmp_path, change):
    p,s,a,calls=fixture(tmp_path)
    record=s['projects']['p']; digest=record['saved_digest']
    s.update(status='ready',last_resolution={})
    record.update(saved=True,path_authorization={'operation':'adopt_project','working_path':str(p)},
                  adoption_review={'review_note':'User approved continuation','expected_digest':digest})
    if change=='fenced': s['status']='needs_reconcile'
    if change=='uncertain': s['uncertain_jobs']=['job-original']
    if change=='launch': s['launch_intent']=True
    if change=='digest': p.write_bytes(b'changed')
    if change=='path': record['path_authorization']['working_path']=str(tmp_path/'other.cst')
    if change=='no_note': record['adoption_review']['review_note']=' '
    with pytest.raises(ServiceError): restore_reviewed_projects(a,s,set())
    assert calls==[]
