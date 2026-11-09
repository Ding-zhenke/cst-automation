from types import SimpleNamespace
import re
import pytest


def settings():
    return dict(xrange=[0, 0], yrange=[-1, 1], zrange=[0, 2], orientation='xmin',
                number_of_modes=1, port_on_bound=True)


def app_fixture(mode='normal'):
    ports = {1: ('Discrete', 1), 2: ('Discrete', 1), 3: ('Discrete', 1)}
    calls = []
    class Port:
        def StartPortNumberIteration(self):
            self.ids = iter(ports)
            return len(ports)
        def GetNextPortNumber(self): return next(self.ids)
        def GetType(self, pid): return ports[pid][0]
        def GetNumberOfModes(self, pid): return ports[pid][1]
    def history(name, code):
        calls.append(code)
        target = int(re.search(r'Port.Delete\s+(\d+)', code).group(1))
        if mode == 'raise':
            del ports[target]
            raise RuntimeError('native failed after deletion')
        if mode != 'ignored': ports[target] = ('Waveguide', 1)
        if mode == 'other_changed': ports[3] = ('Waveguide', 1)
    app = SimpleNamespace(cst_file=SimpleNamespace(model3d=SimpleNamespace(Port=Port(), add_to_history=history)))
    return app, ports, calls


@pytest.mark.parametrize('changes', [{'xrange':[0, 1]}, {'yrange':[1, -1]}, {'zrange':[0, 0]},
    {'number_of_modes': True}, {'port_on_bound': 'True'}, {'orientation':'positive'},
    {'xrange':['lb','lb']}, {'shield':'anything'}, {'reference_plane_distance':float('nan')}])
def test_invalid_replacement_never_reads_or_deletes(changes):
    from cst_solver.simulation.port_replacement import replace_port_with_waveguide
    with pytest.raises(ValueError):
        replace_port_with_waveguide(SimpleNamespace(), 1, dict(settings(), **changes),
                                   expected_type='Discrete', preserve_ports={'3':'Discrete'})


def test_exact_id_and_preserved_ports_readback():
    from cst_solver.simulation.port_replacement import replace_port_with_waveguide
    app, ports, calls = app_fixture()
    out = replace_port_with_waveguide(app, 1, settings(), expected_type='Discrete', preserve_ports={'3':'Discrete'})
    assert len(calls) == 1 and calls[0].startswith('Port.Delete 1\n')
    assert '.PortNumber "1"' in calls[0]
    assert ports[2] == ports[3] == ('Discrete',1)
    assert out['identity_readback_verified'] is True
    assert out['geometry_readback_verified'] is out['mode_impedance_verified'] is False


@pytest.mark.parametrize('mode', ['ignored','raise','other_changed'])
def test_failure_keeps_partial_receipt_without_retry(mode):
    from cst_solver.simulation.port_replacement import replace_port_with_waveguide, PortReplacementError
    app, ports, calls = app_fixture(mode)
    with pytest.raises(PortReplacementError) as caught:
        replace_port_with_waveguide(app, 1, settings(), expected_type='Discrete', preserve_ports={'3':'Discrete'})
    assert len(calls) == 1
    assert caught.value.receipt['mutation_attempted'] is True
    assert caught.value.receipt['before']['3']['type'] == 'Discrete'


def test_missing_query_or_wrong_original_blocks_delete():
    from cst_solver.simulation.port_replacement import replace_port_with_waveguide, PortReplacementError
    app, ports, calls = app_fixture()
    with pytest.raises(PortReplacementError):
        replace_port_with_waveguide(app, 1, settings(), expected_type='Waveguide', preserve_ports={})
    assert calls == []

    del app.cst_file.model3d.Port
    with pytest.raises(PortReplacementError):
        replace_port_with_waveguide(app, 1, settings(), expected_type='Discrete', preserve_ports={})
    assert calls == []


def replacement_call(pid=1):
    return {'method':'replace_port_with_waveguide', 'args':[pid,settings()],
            'kwargs':{'expected_type':'Discrete','preserve_ports':{'3':'Discrete'}}}


@pytest.mark.parametrize('calls', [[replacement_call(), replacement_call()],
    [replacement_call(), {'method':'activate_global_wcs'}], [replacement_call(3)]])
def test_bad_batch_rejected_before_dispatch(calls):
    from tpc_service.sessions.model_api import validate_calls
    from tpc_service.errors import ServiceError
    with pytest.raises(ServiceError): validate_calls(calls)


@pytest.mark.parametrize('corrupt_after_rebuild', [False,True])
def test_session_rechecks_after_full_rebuild_before_save(tmp_path, corrupt_after_rebuild):
    from cst_solver.simulation.port_replacement import replace_port_with_waveguide
    from tpc_service.sessions.operations import _execute_operation
    from tpc_service.errors import ServiceError
    app, ports, commands = app_fixture()
    app.replace_port_with_waveguide = lambda *a,**k: replace_port_with_waveguide(app,*a,**k)
    saves, rebuilds = [], []
    def validate(**kwargs):
        rebuilds.append(kwargs)
        if corrupt_after_rebuild: ports[3] = ('Waveguide',1)
        return {'status':'success','rebuild_ok':True,'rebuild_performed':True,'rebuild_returned':True}
    app.validate_model = validate
    record = {'path':str(tmp_path/'model.cst'), 'saved_digest':'saved'}
    runtime = SimpleNamespace(folder=tmp_path, backend='cst', project=lambda pid:(app,record),
        save=lambda *a:saves.append(a) or record)
    job = dict(operation='model_api',job_id='j',operation_id='o',fingerprint='f',
               params={'project_id':'p','calls':[replacement_call(1),replacement_call(2)]})
    if corrupt_after_rebuild:
        with pytest.raises(ServiceError) as caught: _execute_operation(runtime,job)
        assert caught.value.code == 'session_port_replacement_failed'
        assert caught.value.details['receipt']['stage'] == 'post_rebuild_readback'
        assert not saves
    else:
        result = _execute_operation(runtime,job)
        assert len(saves) == 1
        assert all(r['receipt']['post_rebuild_identity_verified'] for r in result['configuration_receipts'])
    assert len(commands) == 2 and rebuilds == [{}]


def test_old_worker_cannot_receive_replacement(tmp_path,monkeypatch):
    import hashlib,json
    from tpc_service.sessions import manager as module
    from tpc_service.sessions.store import read,write
    from tpc_service.errors import ServiceError
    manager=module.SessionManager(str(tmp_path),backend='fake')
    ref=manager.ensure('test','test')
    folder=tmp_path/ref['session_id']
    state=read(folder/'session.json')
    state.update(status='ready',worker={'pid':123},worker_capabilities=['mesh-settings-no-rebuild-v1'])
    write(folder/'session.json',state)
    monkeypatch.setattr(module,'alive',lambda *a:True)
    monkeypatch.setattr(manager,'_launch',lambda *a:pytest.fail('Must not launch'))
    calls=[replacement_call()]
    params=dict(project_id='p',stage_id='replace',calls=calls,
                preview_digest=hashlib.sha256(json.dumps(calls,sort_keys=True,ensure_ascii=False).encode()).hexdigest())
    with pytest.raises(ServiceError) as caught:
        manager.submit(ref['session_id'],ref['credential'],'request','model_api',params)
    assert caught.value.code == 'workflow_worker_upgrade_required'
    assert not list((folder/'jobs').glob('*.json'))


@pytest.mark.parametrize('bad_calls', [
    [dict(replacement_call(), args=[1, dict(settings(), xrange=[0,1])])],
    [replacement_call(), replacement_call()],
    [replacement_call(), {'method':'activate_global_wcs'}],
])
def test_invalid_submission_never_launches_worker(tmp_path, monkeypatch, bad_calls):
    import hashlib, json
    from tpc_service.sessions.manager import SessionManager
    from tpc_service.errors import ServiceError
    manager = SessionManager(str(tmp_path), backend='cst')
    ref = manager.ensure('invalid-port', 'invalid-port')
    monkeypatch.setattr(manager, '_launch', lambda *a: pytest.fail('Invalid request launched CST worker'))
    params = dict(project_id='p', stage_id='replace', calls=bad_calls,
                  preview_digest=hashlib.sha256(json.dumps(bad_calls, sort_keys=True, ensure_ascii=False).encode()).hexdigest())
    with pytest.raises(ServiceError) as caught:
        manager.submit(ref['session_id'], ref['credential'], 'request', 'model_api', params)
    assert caught.value.code == 'invalid_session_argument'
    assert not list((tmp_path / ref['session_id'] / 'jobs').glob('*.json'))


def test_wrong_second_original_prevents_entire_batch_mutation():
    from tpc_service.sessions.model_api import dispatch
    from tpc_service.errors import ServiceError
    from cst_solver.simulation.port_replacement import replace_port_with_waveguide
    app, ports, commands = app_fixture()
    app.replace_port_with_waveguide = lambda *a, **k: replace_port_with_waveguide(app, *a, **k)
    second = replacement_call(2)
    second['kwargs']['expected_type'] = 'Waveguide'
    with pytest.raises(ServiceError) as caught:
        dispatch(app, [replacement_call(1), second])
    assert caught.value.details['receipt']['mutation_attempted'] is False
    assert commands == []
    assert all(v == ('Discrete', 1) for v in ports.values())
