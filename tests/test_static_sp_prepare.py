import copy
import hashlib
from types import SimpleNamespace as NS
import pytest
from cst_automation.workflow import digest
from cst_solver.circuit.adapter import CircuitError
from cst_solver.circuit.static_sp import prepare_static_sp


class Net:
    def __init__(self):
        self.data = {'L': {('Block','N',0),('Probe','PL',1)}, 'LS': {('Probe','PL',0),('Block','SL',0)},
                     'R': {('Block','N',1),('Probe','PR',1)}, 'RS': {('Probe','PR',0),('Block','SR',0)},
                     'C': {('Block','N',2),('Probe','PC',1)}, 'CS': {('Probe','PC',0),('Block','P',0)},
                     'B': {('Block','P',1),('Block','B',0)}, 'G': {('Block','B',1),('Block','G',0)},
                     'D': {('Block','N',3),('Block','D',0)}}
    def Reset(self): pass
    def GetNumberOfNets(self): return len(self.data)
    def GetNetNameByIndex(self, i): return list(self.data)[i]
    def GetNumberOfSubnets(self, name): return 1
    def GetComponentPorts(self, name, index): return list(self.data[name])
    def AddComponentPorts(self, name, values, new):
        self.data[name].update(map(tuple, values)); return name
    def RemoveComponentPorts(self, values, name):
        for v in values: self.data[name].remove(tuple(v))
    def Apply(self): pass


def fixture(tmp_path, monkeypatch):
    from cst_solver.circuit import linear_sp
    project = tmp_path/'device.cst'; project.write_bytes(b'project')
    path = tmp_path/'device'/'Model'/'DS'/'Block'/'network.s4p'
    path.parent.mkdir(parents=True); path.write_bytes(b'network')
    source = lambda name, kind, p: dict(name=name, type=kind, properties=p,
        property_metadata={k:{'type':'double','unit':'Ohm' if k == 'Ri' else 'V'} for k in p},
        pins=[{'port_index':0},{'port_index':1}], files=[])
    blocks = [dict(name='N', type='TOUCHSTONE block', properties={}, pins=[], files=[str(path)]),
              source('SL','Voltage Signal Source', {'ACAmplitude':'1','HBAmplitude':'1','Ri':'100'}),
              source('SR','Voltage Signal Source', {'ACAmplitude':'1','HBAmplitude':'1','Ri':'100'}),
              source('P','Voltage Signal Source', {'ACAmplitude':'1','HBAmplitude':'1','Ri':'R'}),
              source('B','Voltage DC Source', {'DC':'1','Ri':'0'}),
              dict(name='G',type='Ground',properties={},pins=[{'port_index':0}],files=[]),
              dict(name='D',type='SPICE file block',properties={'model':'diode'},pins=[],files=[])]
    net = Net(); ext = []; tasks = []
    class Port:
        def Reset(self): pass
        def Name(self, n): self.name = n
        def Position(self, *p): pass
        def Create(self): ext.append({'name':self.name})
        def GetNumberOfPorts(self): return 1
    class Block:
        def __init__(self, name): self.entry = next(b for b in blocks if b['name'] == name)
        def DoesExist(self): return True
        def GetTypeName(self): return self.entry['type']
        def GetFile(self): return str(path)
        def SetDoubleProperty(self, key, value): self.entry['properties'][key] = value
        def GetProperty(self, key): return self.entry['properties'][key]
    class Adapter:
        def __init__(self):
            self.app = NS(cst_file=NS(filename=lambda: str(project)))
            self.schematic = NS(Net=net, ExternalPort=Port())
        def select(self, kind, name): return Block(name)
        def property_readback(self, name):
            b = Block(name).entry
            return {'properties':copy.deepcopy(b['properties']), 'property_metadata':copy.deepcopy(b['property_metadata'])}
        def dependencies(self): return {'complete':True, 'unknown':[], 'files':[{'exists':True,'sha256':'a'*64}]}
        def inspect(self):
            return copy.deepcopy(dict(blocks=blocks, nets=[{'name': k, 'subnets': [[list(v) for v in sorted(values)]]}
                for k,values in net.data.items()], external_ports=ext, tasks=tasks, parameters={'R':'50'},
                units={}, probes=[], unknown=[{'field':'parameter_dimensions','status':'unknown'}]))
    adapter = Adapter()
    def configure(schematic, name, **kwargs):
        tasks.append({'name': name, 'type': 's-parameters'})
        return {'sample_count_readback':'unsupported', 'port_impedances_readback':'unsupported'}
    monkeypatch.setattr(linear_sp, 'configure_linear_sp_task', configure)
    rows = [dict(name='A',position=[0,0],net_name='L',expected_members=[list(v) for v in net.data['L']],probe_endpoint=['Probe','PL',1]),
            dict(name='Z',position=[1,0],net_name='R',expected_members=[list(v) for v in net.data['R']],probe_endpoint=['Probe','PR',1])]
    spec = dict(snapshot_sha256=digest(adapter.inspect()), network_block='N',network_sha256=hashlib.sha256(b'network').hexdigest(),
        ports=rows, task=dict(task_name='SP',frequency_unit='GHz',fmin=110,fmax=170,samples=61,port_impedances={'A':100,'Z':100}),
        control=dict(network_pin=2,probe='PC',source='P',bias='B',ground='G',resistance_ohms=50))
    return adapter, spec


def test_complete_preparation_preserves_control_network_and_zeros_sources(tmp_path, monkeypatch):
    adapter, spec = fixture(tmp_path, monkeypatch)
    result = prepare_static_sp(adapter, spec)
    assert result['control_path_verified'] and not result['solver_verified']
    assert adapter.schematic.Net.data['L'] == {('Block','N',0),('ExternalPort','A',0)}
    assert adapter.schematic.Net.data['C'] == {('Block','N',2),('Probe','PC',1)}
    assert adapter.select('Block','P').GetProperty('ACAmplitude') == '0'
    assert adapter.select('Block','P').GetProperty('Ri') == 'R'
    assert result['task']['sample_count_readback'] == 'unsupported'


@pytest.mark.parametrize('issue', ['snapshot', 'network', 'control'])
def test_invalid_input_refuses_before_any_write(tmp_path, monkeypatch, issue):
    adapter, spec = fixture(tmp_path, monkeypatch)
    if issue == 'snapshot': spec['snapshot_sha256'] = '0'*64
    if issue == 'network': spec['network_sha256'] = '0'*64
    if issue == 'control': spec['control']['resistance_ohms'] = 25
    with pytest.raises(ValueError): prepare_static_sp(adapter, spec)
    assert adapter.select('Block','P').GetProperty('ACAmplitude') == '1'
    assert not adapter.inspect()['external_ports']


def test_unexpected_control_pin_inventory_refuses_before_write(tmp_path, monkeypatch):
    adapter, spec = fixture(tmp_path, monkeypatch)
    original = adapter.inspect
    def inspect():
        snapshot = original()
        next(b for b in snapshot['blocks'] if b['name'] == 'P')['pins'].append({'port_index': 2})
        return snapshot
    adapter.inspect = inspect
    spec['snapshot_sha256'] = digest(inspect())
    with pytest.raises(ValueError, match='pin inventory'):
        prepare_static_sp(adapter, spec)
    assert adapter.select('Block', 'P').GetProperty('ACAmplitude') == '1'


def test_partial_change_is_fenced(tmp_path, monkeypatch):
    adapter, spec = fixture(tmp_path, monkeypatch)
    adapter.schematic.Net.AddComponentPorts = lambda *a: (_ for _ in ()).throw(RuntimeError('failed'))
    with pytest.raises(CircuitError) as exc: prepare_static_sp(adapter, spec)
    assert exc.value.code == 'circuit_build_partial'
    assert adapter.select('Block','P').GetProperty('ACAmplitude') == '0'


def test_task_failure_preserves_original_native_diagnostics(tmp_path, monkeypatch):
    from cst_solver.circuit import linear_sp
    adapter, spec = fixture(tmp_path, monkeypatch)
    def fail(*args, **kwargs):
        raise CircuitError('circuit_build_partial', 'task failure',
                           failure_stage='set_broadband_sweep', original_message='native error')
    monkeypatch.setattr(linear_sp, 'configure_linear_sp_task', fail)
    with pytest.raises(CircuitError) as exc:
        prepare_static_sp(adapter, spec)
    assert exc.value.details['original_details']['failure_stage'] == 'set_broadband_sweep'
    assert exc.value.details['original_details']['original_message'] == 'native error'


def test_session_preparation_uses_existing_handle_and_saves_once(tmp_path, monkeypatch):
    from unittest.mock import Mock
    from tpc_service.sessions.operations import execute
    from tpc_service.sessions import store, workflow
    from cst_solver.circuit import static_sp
    project = tmp_path/'project.cst'; project.write_bytes(b'project')
    sha = hashlib.sha256(b'project').hexdigest()
    record = dict(project_id='p', path=str(project), saved_digest=sha, saved=True)
    state = {'projects': {'p':record}, 'environment': {'pid':1}, 'status':'ready'}
    expected = {'blocks':[]}
    fake_adapter = NS(inspect=lambda: expected)
    app = NS(circuit=NS(adapter=fake_adapter), cst_file=object())
    runtime = NS(folder=tmp_path, backend='cst', app=app, handles={'p':app.cst_file},
                 state=lambda:state, check_saved=Mock(), project=Mock(), save=Mock(return_value={'saved_digest':sha}))
    monkeypatch.setattr(store, 'alive', lambda identity: True)
    monkeypatch.setattr(workflow, 'preflight', lambda *a, **kw: None)
    def prepare(adapter, spec, *, before_write):
        before_write({'before': expected})
        return {'after':expected, 'solver_verified':False}
    monkeypatch.setattr(static_sp, 'prepare_static_sp', prepare)
    result = execute(runtime, {'job_id':'job-one', 'operation':'prepare_static_sp',
        'params':{'project_id':'p', 'spec':{}, 'expected_digest':sha, 'confirm_idle':True}})
    assert result['saved'] and result['job_id'] == 'job-one' and not result['solver_verified']
    runtime.project.assert_not_called(); runtime.save.assert_called_once_with(app, 'p')
    assert (tmp_path/'static_sp_prepare'/'job-one.before.json').is_file()


def test_session_partial_failure_never_saves(tmp_path, monkeypatch):
    from unittest.mock import Mock
    from tpc_service.sessions.operations import execute
    from tpc_service.sessions import store, workflow
    from tpc_service.errors import ServiceError
    from cst_solver.circuit import static_sp
    record = dict(project_id='p', path=str(tmp_path/'project.cst'))
    state = {'projects':{'p':record}, 'environment':{'pid':1}}
    app = NS(circuit=NS(adapter=object()), cst_file=object())
    runtime = NS(folder=tmp_path, backend='cst', app=app, handles={'p':app.cst_file},
                 state=lambda:state, check_saved=Mock(), project=Mock(), save=Mock())
    monkeypatch.setattr(store, 'alive', lambda identity: True)
    monkeypatch.setattr(workflow, 'preflight', lambda *a, **kw: None)
    def fail(*args, **kwargs): raise CircuitError('circuit_build_partial', 'partial')
    monkeypatch.setattr(static_sp, 'prepare_static_sp', fail)
    with pytest.raises(ServiceError) as exc:
        execute(runtime, {'job_id':'job-one', 'operation':'prepare_static_sp',
            'params':{'project_id':'p', 'spec':{}, 'expected_digest':'0'*64, 'confirm_idle':True}})
    assert exc.value.code == 'session_static_sp_prepare_failed'
    runtime.project.assert_not_called(); runtime.save.assert_not_called()


@pytest.mark.parametrize('reason', ['missing_worker', 'old_worker', 'busy', 'uncertain', 'changed'])
def test_session_preflight_rejects_unsafe_state_before_worker_action(tmp_path, monkeypatch, reason):
    from tpc_service.sessions import workflow
    from tpc_service.sessions.job_index import JobIndex
    from tpc_service.errors import ServiceError
    project = tmp_path / 'project.cst'
    project.write_bytes(b'baseline')
    sha = hashlib.sha256(b'baseline').hexdigest()
    state = {'backend': 'cst', 'status': 'ready', 'worker': {'pid': 1},
             'worker_capabilities': ['static-sp-prepare-v1'],
             'projects': {'p': {'path': str(project), 'saved_digest': sha}}}
    active = []
    if reason == 'missing_worker': state['worker'] = None
    if reason == 'old_worker': state['worker_capabilities'] = []
    if reason == 'busy': active = [{'job_id': 'other'}]
    if reason == 'uncertain': state['uncertain_jobs'] = ['unknown']
    if reason == 'changed': project.write_bytes(b'changed')
    monkeypatch.setattr(workflow, 'alive', lambda identity: True)
    monkeypatch.setattr(JobIndex, 'load', lambda folder: NS(active_jobs=lambda: active))
    with pytest.raises(ServiceError):
        workflow.preflight(tmp_path, state, 'prepare_static_sp',
                           {'project_id': 'p', 'expected_digest': sha})


def test_invalid_session_request_rejected_before_launch(tmp_path, monkeypatch):
    from tpc_service.sessions.manager import SessionManager
    from tpc_service.errors import ServiceError
    from unittest.mock import Mock
    adapter, spec = fixture(tmp_path, monkeypatch)
    spec['network_sha256'] = 'not-a-hash'
    manager = SessionManager(tmp_path / 'sessions', backend='cst')
    manager._folder = Mock(side_effect=AssertionError('invalid request reached session or worker'))
    with pytest.raises(ServiceError):
        manager.submit('session', 'credential', 'request', 'prepare_static_sp',
                       {'project_id': 'p', 'expected_digest': '0' * 64,
                        'confirm_idle': True, 'spec': spec})
    manager._folder.assert_not_called()
    assert adapter.select('Block', 'P').GetProperty('ACAmplitude') == '1'
