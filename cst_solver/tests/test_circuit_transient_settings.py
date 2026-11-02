from types import SimpleNamespace

import pytest

from cst_automation.circuit_schema import CircuitSpecError
from cst_automation.circuit_tasks import transient_settings
from cst_solver.circuit.api import CircuitAPI
from cst_solver.circuit.adapter import CircuitError, NativeAdapter


def profile():
    return {'mode': 'transient_cosim', 'duration': {'value': 40, 'unit': 'ns'},
            'sampling': {'method': 'simulated', 'points': 8001},
            'integration': {'time_step': {'value': 5, 'unit': 'ps'}, 'auto_solver': False},
            'max_frequency': {'value': 5, 'unit': 'GHz'}, 'accuracy': 1e-6}


@pytest.mark.parametrize('change', [
    {'duration': {'value': 1, 'unit': 'V'}}, {'duration': {'value': -1, 'unit': 'ns'}},
    {'sampling': {'method': 'guessed'}}, {'sampling': {'points': True}},
    {'integration': {'time_step': {'value': 1, 'unit': 's'}}},
    {'integration': {'auto_solver': 'false'}}, {'accuracy': float('nan')},
    {'max_frequency': {'value': 0, 'unit': 'GHz'}}, {'unknown': 1},
])
def test_invalid_profile_rejected_before_native_access(change):
    settings = dict(profile(), **change)
    with pytest.raises(CircuitSpecError):
        CircuitAPI(SimpleNamespace(cst_file=None)).configure_transient_task('T', settings)


class Task:
    def __init__(self, kind='Transient'):
        self.kind, self.calls, self.values = kind, [], {}
    def Reset(self): pass
    def Name(self, name): self.name = name
    def DoesExist(self): return self.kind is not None
    def GetTypeForTask(self, name): return self.kind
    def Type(self, kind): self.calls.append(('type', kind))
    def Create(self): self.kind = 'Transient'; self.calls.append(('create', self.name))
    def SetProperty(self, key, value): self.calls.append((key, value)); self.values[key] = value
    def GetProperty(self, key): return self.values[key]
    def SetSweepData(self, start, stop, points):
        self.calls.append(('sweep', start, stop, points))
        self.values.update({'sampling method': 'Manual', 'tmax': stop})


def native(task):
    return NativeAdapter(SimpleNamespace(cst_file=SimpleNamespace(schematic=SimpleNamespace(
        SimulationTask=task, Units=SimpleNamespace(GetUnit=lambda d: {'Time': 'us', 'Frequency': 'MHz'}[d])))))


def test_sampling_is_selected_after_sweep_and_units_do_not_change():
    task = Task()
    report = native(task).configure_transient_task('T', transient_settings(profile()), create=False)
    assert float(task.values['tmax']) == pytest.approx(.04)
    assert float(task.values['time step']) == pytest.approx(5e-6)
    assert float(task.values['manual fmax']) == pytest.approx(5000)
    assert task.calls[-1] == ('sampling method', 'Simulated')
    assert task.values['sampling method'] == 'Simulated'
    assert report['internal_time_step_verified'] is False
    assert report['solver_verified'] is False
    assert report['requested_output_points'] == 8001
    assert report['output_grid_readback'] == 'unsupported'


@pytest.mark.parametrize('kind,create', [('S-Parameters', False), ('Transient', True), (None, False)])
def test_no_overwrite_or_wrong_task_type(kind, create):
    task = Task(kind)
    with pytest.raises(CircuitError): native(task).configure_transient_task('T', transient_settings(profile()), create=create)
    assert not task.calls


def test_creation_is_explicit_and_does_not_submit_task():
    task = Task(None)
    result = native(task).configure_transient_task('NEW', transient_settings(profile()), create=True)
    assert ('create', 'NEW') in task.calls
    assert result['created'] is True


def test_partial_configuration_invalidates_cache_and_exposes_stage():
    def broken(*a, **kw): raise RuntimeError('SDK interrupted after sweep')
    api = CircuitAPI(SimpleNamespace(), adapter=SimpleNamespace(configure_transient_task=broken))
    api._spec = {'previous': True}
    with pytest.raises(CircuitError) as error: api.configure_transient_task('T', profile())
    assert error.value.code == 'circuit_build_partial'
    assert error.value.details['stage'] == 'configure_transient_task'
    assert api._spec is None


def test_wrong_sampling_readback_remains_partial_and_does_not_claim_verification():
    task = Task()
    native_get = task.GetProperty
    task.GetProperty = lambda key: 'Manual' if key == 'sampling method' else native_get(key)
    with pytest.raises(CircuitError) as error:
        native(task).configure_transient_task('T', transient_settings(profile()))
    assert error.value.code == 'circuit_build_partial'


def test_unknown_native_unit_prevents_writes():
    task = Task(); adapter = native(task)
    adapter.schematic.Units.GetUnit = lambda dim: 'unreadable'
    with pytest.raises(CircuitSpecError): adapter.configure_transient_task('T', transient_settings(profile()))
    assert not task.calls


def test_femtosecond_request_in_seconds_cannot_accept_native_zero():
    task = Task(); adapter = native(task)
    adapter.schematic.Units.GetUnit = lambda dim: 's'
    settings = transient_settings({'mode':'network','duration':{'value':1,'unit':'fs'}})
    native_get = task.GetProperty
    task.GetProperty = lambda key: '0' if key=='tmax' else native_get(key)
    with pytest.raises(CircuitError): adapter.configure_transient_task('T', settings)
