import pytest

from tpc_service.sessions.linear_sp import validate_setup, validate_solve, setup_preflight, execute_setup
from tpc_service.errors import ServiceError


def valid():
    return {'project_id': 'p', 'network_job_id': 'net',
            'task': {'task_name': 'SP', 'frequency_unit': 'GHz', 'fmin': 1.0,
                     'fmax': 2.0, 'samples': 11, 'port_impedances': {'P1': 50, 'P2': 50}},
            'ports': [{'name': 'P1', 'position': [0, 0], 'net_name': 'n1',
                       'expected_members': [['Block', 'source', 0]]},
                      {'name': 'P2', 'position': [10, 0], 'net_name': 'n2',
                       'expected_members': [['Block', 'load', 0]]}]}


def test_rejects_duplicate_port_and_missing_port_reference():
    data = valid(); data['ports'][1]['name'] = 'P1'
    with pytest.raises(ValueError): validate_setup(data)
    data = valid(); del data['task']['port_impedances']['P2']
    with pytest.raises(ValueError): validate_setup(data)


def test_rejects_nonfinite_position_or_invalid_net_members():
    data = valid(); data['ports'][0]['position'][0] = float('nan')
    with pytest.raises(ValueError): validate_setup(data)
    data = valid(); data['ports'][0]['expected_members'] = []
    with pytest.raises(ValueError): validate_setup(data)


def test_solve_requires_results_scoped_to_requested_task():
    p = {'project_id': 'p', 'network_job_id': 'net', 'setup_job_id': 'setup',
         'task_name': 'SP', 'expected_results': [{'tree_path': 'Tasks\\OTHER\\S-Parameters\\S1,1', 'run_id': 0}]}
    with pytest.raises(ValueError): validate_solve(p)


def test_setup_rejects_missing_network_before_native_access(tmp_path):
    state = {'status': 'ready', 'projects': {'p': {'project_id': 'p',
             'workflow': {'em_generation': 2}}}}
    with pytest.raises(ServiceError): setup_preflight(tmp_path, state, valid())


def test_setup_does_not_replace_existing_port(tmp_path, monkeypatch):
    from types import SimpleNamespace
    data = valid()
    project = {'project_id': 'p', 'path': str(tmp_path/'a.cst'),
               'workflow': {'em_generation': 2, 'hb_generation': 1}}
    class Runtime:
        folder = tmp_path
        def state(self): return {'projects': {'p': project}}
    class Ports:
        def StartPortNameIteration(self): self.items = iter(['P1'])
        def GetNextPortName(self): return next(self.items, '')
    schematic = SimpleNamespace(ExternalPort=Ports())
    app = SimpleNamespace(circuit=SimpleNamespace(adapter=SimpleNamespace(schematic=schematic)))
    monkeypatch.setattr('tpc_service.sessions.linear_sp.check_prepared_network', lambda *a: {'params': {'block_name': 'N'}})
    monkeypatch.setattr('tpc_service.sessions.workflow.live_checks', lambda *a: None)
    monkeypatch.setattr('cst_solver.circuit.embedded_network.snapshot', lambda *a: {})
    with pytest.raises(ServiceError) as caught:
        execute_setup(Runtime(), {'job_id': 'j', 'params': data}, app)
    assert caught.value.code == 'exploratory_sp_setup_conflict'


def test_setup_saves_bound_task_and_keeps_hb_closed(tmp_path, monkeypatch):
    from types import SimpleNamespace
    data = valid()
    project = {'project_id': 'p', 'path': str(tmp_path/'a.cst'),
               'workflow': {'em_generation': 2, 'hb_generation': 1, 'evidence': {'old': True}}}
    class Runtime:
        folder = tmp_path
        def state(self): return {'projects': {'p': project}}
        def update(self, **kwargs): pass
        def save(self, *args):
            project['saved_digest'] = 'saved'
            return project
    class Ports:
        def StartPortNameIteration(self): self.names = iter([])
        def GetNextPortName(self): return next(self.names, '')
        def Reset(self): pass
        def Name(self, name): self.name = name
        def Position(self, *args): pass
        def Create(self): pass
        def GetNumberOfPorts(self): return 1
    class Task:
        def Reset(self): pass
        def Name(self, name): pass
        def DoesExist(self): return False
    schematic = SimpleNamespace(ExternalPort=Ports(), SimulationTask=Task(), Net=object())
    app = SimpleNamespace(circuit=SimpleNamespace(adapter=SimpleNamespace(schematic=schematic)))
    before = {'blocks': [], 'probes': [], 'units': {}, 'parameters': {}, 'unknown': [],
              'external_ports': [], 'tasks': [], 'nets': []}
    after = dict(before, external_ports=[{'name': 'P1'}, {'name': 'P2'}], tasks=[{'name': 'SP'}])
    snapshots = iter([before, after, after])
    monkeypatch.setattr('tpc_service.sessions.linear_sp.check_prepared_network',
                        lambda *a: {'params': {'block_name': 'N'}, 'receipt': {'after': 'payload'}})
    monkeypatch.setattr('tpc_service.sessions.linear_sp.network_options', lambda *a: {})
    monkeypatch.setattr('tpc_service.sessions.workflow.live_checks', lambda *a: None)
    monkeypatch.setattr('cst_solver.circuit.embedded_network.snapshot', lambda *a: next(snapshots))
    monkeypatch.setattr('cst_solver.circuit.embedded_network.observe', lambda *a: 'payload')
    monkeypatch.setattr('cst_solver.circuit.adapter.attach_external_port_to_net', lambda *a: None)
    monkeypatch.setattr('cst_solver.circuit.linear_sp.configure_linear_sp_task', lambda *a, **k: {'properties_readback': {}})
    result = execute_setup(Runtime(), {'job_id': 'setup', 'params': data}, app)
    assert result['saved'] is True
    assert project['workflow']['sp_setup']['task_name'] == 'SP'
    assert project['workflow']['network_required'] is True and project['workflow']['evidence'] is None
