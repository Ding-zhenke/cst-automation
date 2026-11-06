from types import SimpleNamespace
import pytest
from tpc_service.sessions.operations import execute

class Runtime:
    backend = 'cst'
    def __init__(self):
        self.calls = []
        self.app = SimpleNamespace(para=lambda *a, **kw: self.calls.append((a,kw)),
            validate_model=lambda **kwargs: {'status':'success','rebuild_ok':True})
    def project(self, project_id): return self.app, {'path':'model.cst'}
    def save(self, app, project_id): return {'saved_digest':'test'}
    def checkpoint(self, value): pass

def job(expressions):
    return dict(operation='set_parameters', params=dict(project_id='p',
        values={'yf':'e2/2+dy'}, expressions=expressions),
        job_id='j',operation_id='o',fingerprint='f')

def test_expression_reaches_existing_python_parameter_api(monkeypatch):
    from tpc_service.sessions import operations
    monkeypatch.setattr(operations, 'write', lambda *a: None)
    r=Runtime()
    # Stop after API call; this test checks dispatch, not CST or file saving.
    r.app.validate_model=lambda **kwargs: (_ for _ in ()).throw(RuntimeError('stop after call'))
    with pytest.raises(RuntimeError,match='stop after call'):
        execute(r,job({'yf':'探针、波导及端口共同中心，随dy联动'}))
    assert r.calls == [(('yf','e2/2+dy'), {'expression':'探针、波导及端口共同中心，随dy联动'})]

def test_invalid_expression_never_writes_parameters():
    r=Runtime()
    with pytest.raises(Exception): execute(r,job({'unknown':'说明'}))
    assert r.calls == []


def test_description_is_restored_after_history_rebuild_before_save(tmp_path):
    r=Runtime()
    r.folder=tmp_path
    (tmp_path/'checkpoints').mkdir()
    actual={}
    def rebuild(**kwargs):
        actual['yf']='Old English history description'
        return {'status':'success','rebuild_ok':True}
    r.app.validate_model=rebuild
    r.app._set_parameter_description=lambda name,text: actual.update({name:text})
    r.app.get_messages=lambda: []
    def save(app,project_id):
        assert actual['yf']=='共同中心，随dy联动'
        return {'saved_digest':'test'}
    r.save=save
    result=execute(r,job({'yf':'共同中心，随dy联动'}))
    assert result['saved']
