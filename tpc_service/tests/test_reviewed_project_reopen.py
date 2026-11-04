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
