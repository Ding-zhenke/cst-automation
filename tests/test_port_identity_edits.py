from types import SimpleNamespace
import pytest
from cst_solver.simulation.ports import PortMixin
from tpc_service.sessions.model_api import validate_calls

class NativePort:
    def __init__(self, ports): self.ports = ports
    def StartPortNumberIteration(self): self.ids = iter(sorted(self.ports)); return len(self.ports)
    def GetNextPortNumber(self): return next(self.ids)
    def GetType(self, i): return self.ports[i][0]
    def GetNumberOfModes(self, i): return self.ports[i][1]

def app_with(ports):
    port = NativePort(ports)
    def submit(_caption, code):
        parts = code.replace(',', '').split()
        if parts[0] == 'Port.Delete': del port.ports[int(parts[1])]
        elif parts[0] == 'Port.Rename': port.ports[int(parts[2])] = port.ports.pop(int(parts[1]))
        else: raise AssertionError(code)
    app = SimpleNamespace(cst_file=SimpleNamespace(model3d=SimpleNamespace(Port=port, add_to_history=submit)))
    return app

def test_delete_and_rename_verify_inventory():
    app = app_with({1: ('Discrete', 0), 2: ('Waveguide', 1)})
    result = PortMixin.delete_port(app, 1, expected_type='Discrete')
    assert result['after'] == {'2': {'type': 'Waveguide', 'number_of_modes': 1}}
    result = PortMixin.rename_port(app, 2, 1, expected_type='Waveguide')
    assert result['after'] == {'1': {'type': 'Waveguide', 'number_of_modes': 1}}

def test_rename_rejects_occupied_destination_before_mutation():
    app = app_with({1: ('Discrete', 0), 2: ('Waveguide', 1)})
    with pytest.raises(Exception) as exc:
        PortMixin.rename_port(app, 2, 1, expected_type='Waveguide')
    assert exc.value.receipt['mutation_attempted'] is False
    assert len(app.cst_file.model3d.Port.ports) == 2

def test_session_validates_ids_before_batch():
    with pytest.raises(Exception):
        validate_calls([{'method':'delete_port', 'args':[True], 'kwargs':{'expected_type':'Discrete'}}])
    validate_calls([{'method':'rename_port', 'args':[2,1], 'kwargs':{'expected_type':'Discrete'}}])

@pytest.mark.parametrize('method,args', [('delete_port',[1]), ('rename_port',[1,3])])
@pytest.mark.parametrize('corrupt', [False, True])
def test_session_identity_edit_rechecks_after_rebuild(tmp_path, method, args, corrupt):
    from cst_solver.simulation.port_replacement import edit_port_identity
    from tpc_service.sessions.operations import _execute_operation
    from tpc_service.errors import ServiceError
    app = app_with({1: ('Discrete',0), 2: ('Waveguide',1)})
    app.delete_port = lambda i, **kw: edit_port_identity(app, i, **kw)
    app.rename_port = lambda i, dest, **kw: edit_port_identity(app, i, new_id=dest, **kw)
    saves=[]
    def rebuild(**kwargs):
        if corrupt: app.cst_file.model3d.Port.ports[2] = ('Discrete',0)
        return {'status':'success','rebuild_ok':True,'rebuild_performed':True,'rebuild_returned':True}
    app.validate_model = rebuild
    record={'path':str(tmp_path/'model.cst'),'saved_digest':'saved'}
    runtime=SimpleNamespace(folder=tmp_path,backend='cst',project=lambda pid:(app,record),save=lambda *a:saves.append(a) or record)
    calls=[{'method':method,'args':args,'kwargs':{'expected_type':'Discrete'}}]
    job=dict(operation='model_api',job_id='j',operation_id='o',fingerprint='f',params={'project_id':'p','calls':calls})
    if corrupt:
        with pytest.raises(ServiceError) as exc: _execute_operation(runtime,job)
        assert exc.value.details['receipt']['stage']=='post_rebuild_readback'
        assert saves == []
    else:
        result=_execute_operation(runtime,job)
        assert result['configuration_receipts'][0]['receipt']['post_rebuild_identity_verified'] is True
        assert len(saves)==1

@pytest.mark.parametrize('method,args', [('delete_port',[1]), ('rename_port',[1,3])])
def test_old_worker_rejects_identity_edit_before_queue(tmp_path, monkeypatch, method, args):
    import hashlib,json
    from tpc_service.sessions import manager as module
    from tpc_service.sessions.store import read,write
    from tpc_service.errors import ServiceError
    manager=module.SessionManager(str(tmp_path),backend='fake')
    ref=manager.ensure('test','test'); folder=tmp_path/ref['session_id']
    state=read(folder/'session.json')
    state.update(status='ready',worker={'pid':123},worker_capabilities=['port-replacement-readback-v1'])
    write(folder/'session.json',state)
    monkeypatch.setattr(module,'alive',lambda *a:True)
    monkeypatch.setattr(manager,'_launch',lambda *a:pytest.fail('Must not launch'))
    calls=[{'method':method,'args':args,'kwargs':{'expected_type':'Discrete'}}]
    params=dict(project_id='p',stage_id='edit',calls=calls,preview_digest=hashlib.sha256(json.dumps(calls,sort_keys=True,ensure_ascii=False).encode()).hexdigest())
    with pytest.raises(ServiceError) as exc: manager.submit(ref['session_id'],ref['credential'],'request','model_api',params)
    assert exc.value.code=='workflow_worker_upgrade_required'
    assert not list((folder/'jobs').glob('*.json'))
