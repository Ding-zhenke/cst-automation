"""Offline contracts for reusable source/model configuration; never a solver."""
from types import SimpleNamespace

import pytest

from cst_automation.circuit_schema import CircuitSpecError
from cst_automation.circuit_tasks import transient_settings
from cst_solver.circuit.api import CircuitAPI
from cst_solver.circuit.adapter import CircuitError, NativeAdapter
from cst_solver.tests.test_circuit_transient_settings import Task, native


def q(value, unit):
    return {'value': value, 'unit': unit}


def test_adaptive_integration_units_and_method_survive_output_sweep():
    settings = transient_settings({'mode': 'network', 'duration': q(40, 'ns'),
        'integration': {'stepping': 'adaptive', 'time_step': q(5, 'ps'),
                        'minimum_time_step': q(.5, 'ps'), 'method': 'gear', 'order': 2}})
    task = Task()
    result = native(task).configure_transient_task('T', settings)
    assert task.values['time stepping'] == 'adaptive'
    assert task.values['integration method'] == 'gear'
    assert task.values['integration order'] == '2'
    assert float(task.values['minimum time step']) == pytest.approx(5e-7)
    assert result['internal_time_step_verified'] is False


@pytest.mark.parametrize('integration', [
    {'method': 'invented'}, {'order': True}, {'order': 5},
    {'stepping': 'automatic', 'time_step': q(1, 'ps')},
    {'minimum_time_step': q(1, 'ps')},
    {'stepping': 'adaptive', 'time_step': q(1, 'ps'), 'minimum_time_step': q(2, 'ps')},
])
def test_invalid_integration_never_touches_sdk(integration):
    with pytest.raises(CircuitSpecError):
        CircuitAPI(SimpleNamespace()).configure_transient_task('T', {
            'mode': 'network', 'duration': q(1, 'ns'), 'integration': integration})


class PortTask(Task):
    def SetPortSignal(self, port, kind, values): self.calls.append(('signal', port, kind, values)); self.signal = kind
    def SetPortSourceType(self, port, kind): self.calls.append(('source', port, kind)); self.source = kind
    def SetPortInnerResistance(self, port, value): self.calls.append(('resistance', port, value)); self.resistance = value
    def SetConstPortImpedance(self, port, real, imag): self.calls.append(('impedance', port, real, imag))
    def GetPortSourceType(self, port): return self.source
    def GetPortSignalType(self, port): return self.signal
    def GetPortInnerResistance(self, port): return self.resistance


def port_api(task):
    adapter = native(task)
    units = {'Time': 'ns', 'Frequency': 'GHz', 'Voltage': 'mV', 'Current': 'mA', 'Resistance': 'kOhm'}
    adapter.schematic.Units.GetUnit = units.__getitem__
    port = SimpleNamespace(StartPortNameIteration=lambda: setattr(port, 'it', iter(['1', '2'])),
                           GetNextPortName=lambda: next(port.it, ''))
    adapter.schematic.ExternalPort = port
    return CircuitAPI(SimpleNamespace(), adapter=adapter)


def test_sine_source_converts_amplitude_frequency_delay_and_resistance():
    task = PortTask()
    report = port_api(task).configure_task_ports('T', {'1': {'source_type': 'voltage',
        'signal': {'type': 'sine', 'amplitude': q(1, 'V'), 'frequency': q(1, 'GHz'), 'delay': q(2, 'ns')},
        'resistance': q(50, 'Ohm')}})
    values = next(c[3] for c in task.calls if c[0] == 'signal')
    assert list(map(float, values)) == pytest.approx([0, 1000, 1, 2])
    assert float(task.resistance) == pytest.approx(.05)
    assert report['solver_verified'] is False
    assert report['ports']['1']['signal_parameters_readback'] == 'unsupported'


def test_import_uses_lowercase_periodic_and_records_file_digest(tmp_path):
    path = tmp_path/'signal.csv'; path.write_text('0,0\n1e-9,1\n')
    task = PortTask()
    report = port_api(task).configure_task_ports('T', {'1': {'source_type': 'voltage',
        'signal': {'type': 'import', 'file': str(path), 'periodic': False}}})
    assert ('signal', '1', 'Import', [str(path), 'false']) in task.calls
    assert len(report['files'][0]['sha256']) == 64


def test_all_ports_preflight_before_first_write(tmp_path):
    task = PortTask()
    with pytest.raises(CircuitError):
        port_api(task).configure_task_ports('T', {'1': {'source_type': 'none', 'impedance': {'real': q(50, 'Ohm')}},
            'missing': {'source_type': 'none', 'impedance': {'real': q(50, 'Ohm')}}})
    assert task.calls == []


@pytest.mark.parametrize('contents', ['0,0\n0,1\n', '0,0\n1,nan\n', '-1,0\n1,0\n', '0,0\n'])
def test_bad_waveform_rejected_without_sdk_access(tmp_path, contents):
    path = tmp_path/'bad.csv'; path.write_text(contents)
    with pytest.raises((CircuitError, CircuitSpecError)):
        CircuitAPI(SimpleNamespace()).configure_task_ports('T', {'1': {'source_type': 'voltage',
            'signal': {'type': 'import', 'file': str(path)}}})


def test_source_readback_mismatch_is_partial_and_invalidates_cache():
    task = PortTask(); task.GetPortSourceType = lambda p: 'Current'
    api = port_api(task); api._spec = {'old': True}
    with pytest.raises(CircuitError) as err:
        api.configure_task_ports('T', {'1': {'source_type': 'none', 'impedance': {'real': q(50, 'Ohm')}}})
    assert err.value.code == 'circuit_build_partial'
    assert err.value.details['stage'] == 'configure_task_ports'
    assert api._spec is None


def test_diode_normalizer_has_no_sample_defaults_and_retains_si_units():
    from cst_automation.circuit_models import nonlinear_model_settings
    data = nonlinear_model_settings({'kind': 'berkeley_diode', 'parameters': {
        'IS': q(10, 'pA'), 'N': 1.2, 'RS': q(1, 'Ohm'), 'CJO': q(0, 'pF')}})
    assert data['properties']['Saturation current'] == pytest.approx(1e-11)
    assert data['property_units']['Saturation current'] == 'A'
    assert data['properties']['Model Type'] == 2
    assert 'Transit time' not in data['properties']


@pytest.mark.parametrize('settings', [
    {'kind': 'berkeley_diode', 'parameters': {'IS': q(-1, 'A')}},
    {'kind': 'berkeley_diode', 'parameters': {'N': True}},
    {'kind': 'berkeley_diode', 'parameters': {'CJO': q(1, 'V')}},
    {'kind': 'berkeley_diode', 'parameters': {'EG': 1.1}},
    {'kind': 'spice', 'file': 'missing.cir', 'model': 'M', 'dialect': 'guessed'},
])
def test_bad_model_rejected_before_sdk(settings):
    with pytest.raises((CircuitError, CircuitSpecError)):
        CircuitAPI(SimpleNamespace()).configure_nonlinear_model('D1', settings)


def test_existing_wrong_model_type_is_never_mutated():
    from cst_automation.circuit_models import nonlinear_model_settings
    obj = SimpleNamespace(Reset=lambda: None, Name=lambda n: None, DoesExist=lambda: True, GetTypeName=lambda: 'Resistor')
    adapter = NativeAdapter(SimpleNamespace(cst_file=SimpleNamespace(schematic=SimpleNamespace(Block=obj))))
    with pytest.raises(CircuitError):
        adapter.configure_nonlinear_model('R', nonlinear_model_settings({'kind': 'berkeley_diode'}))


def test_spice_model_and_dialect_readback_are_actual_not_echoed(tmp_path):
    path = tmp_path/'model.cir'; path.write_text('.SUBCKT D A K\n.ENDS D\n')
    obj = SimpleNamespace(Reset=lambda: None, Name=lambda n: None, DoesExist=lambda: True,
        GetTypeName=lambda: 'SPICE', SetFile=lambda p: None,
        SetSpiceFilter=lambda d: None, SetSpiceModel=lambda m: None)
    adapter = NativeAdapter(SimpleNamespace(cst_file=SimpleNamespace(schematic=SimpleNamespace(Block=obj))))
    adapter.pins = lambda n: []
    adapter.spice_readback = lambda n: {'spice_model': 'PREFIX_D', 'spice_filter': 'PSPICE', 'properties': {}}
    obj.GetFile = lambda: str(path)
    api = CircuitAPI(SimpleNamespace(), adapter=adapter)
    with pytest.raises(CircuitError) as err:
        api.configure_nonlinear_model('D1', {'kind': 'spice', 'file': str(path), 'model': 'D', 'dialect': 'PSPICE'})
    assert err.value.code == 'circuit_build_partial'


def test_existing_diode_sparse_update_preserves_unspecified_model_parameters():
    from cst_solver.tests.test_circuit_diode import Block, adapter
    block = Block(); block.DoesExist = lambda: True
    def write(key, value):
        block.writes.append((key, value))
        block.rows = [r if r[0] != key else (*r[:2], value, r[3]) for r in block.rows]
    block.SetDoubleProperty = write
    block.SetLocalUnitForProperty = lambda key, unit: None
    bound = adapter(block); bound.pins = lambda name: [{'pin_name': '1'}, {'pin_name': '2'}]
    report = CircuitAPI(SimpleNamespace(), adapter=bound).configure_nonlinear_model('D1', {
        'kind': 'berkeley_diode', 'parameters': {'N': 1.5}})
    assert block.writes == [('Emission coefficient', '1.5')]
    assert report['readback']['properties']['Series resistance'] == '1'
    assert report['readback']['properties']['Emission coefficient'] == '1.5'


@pytest.mark.parametrize('create,exists', [(True, True), (False, False)])
def test_model_creation_conflict_is_rejected_before_writes(create, exists):
    obj = SimpleNamespace(Reset=lambda: None, Name=lambda n: None, DoesExist=lambda: exists)
    bound = NativeAdapter(SimpleNamespace(cst_file=SimpleNamespace(schematic=SimpleNamespace(Block=obj))))
    with pytest.raises(CircuitError) as err:
        CircuitAPI(SimpleNamespace(), adapter=bound).configure_nonlinear_model('D', {'kind': 'berkeley_diode'}, create=create)
    assert err.value.code == 'circuit_topology_invalid'


def test_spice_creation_orders_file_dialect_and_model_without_solving(tmp_path):
    path = tmp_path/'d.cir'; path.write_text('.SUBCKT D A K\n.ENDS D\n')
    calls = []
    obj = SimpleNamespace(Reset=lambda: None, Name=lambda n: None, DoesExist=lambda: False,
        Type=lambda k: calls.append(('type', k)), Create=lambda: calls.append(('create',)),
        SetFile=lambda p: calls.append(('file', p)), SetSpiceFilter=lambda d: calls.append(('dialect', d)),
        SetSpiceModel=lambda m: calls.append(('model', m)), GetFile=lambda: str(path))
    bound = NativeAdapter(SimpleNamespace(cst_file=SimpleNamespace(schematic=SimpleNamespace(Block=obj))))
    bound.pins = lambda n: [{'pin_name': 'A'}, {'pin_name': 'K'}]
    bound.spice_readback = lambda n: {'spice_model': 'D', 'spice_filter': 'PSPICE', 'properties': {}}
    report = CircuitAPI(SimpleNamespace(), adapter=bound).configure_nonlinear_model('D1', {
        'kind': 'spice', 'file': str(path), 'model': 'D', 'dialect': 'PSPICE'}, create=True)
    assert [c[0] for c in calls] == ['type', 'file', 'create', 'dialect', 'model']
    assert report['pins_after'] == [{'pin_name': 'A'}, {'pin_name': 'K'}]
    assert report['solver_verified'] is False


def test_current_source_and_passive_impedance_use_distinct_settings():
    task = PortTask()
    port_api(task).configure_task_ports('T', {'1': {'source_type': 'current', 'signal': {
        'type': 'sine', 'amplitude': q(1, 'A'), 'frequency': q(1, 'GHz')}}})
    assert float(task.calls[0][3][1]) == pytest.approx(1000.)
    assert not any(c[0] == 'resistance' for c in task.calls)
    task.calls.clear()
    port_api(task).configure_task_ports('T', {'1': {'source_type': 'none', 'impedance': {
        'real': q(50, 'Ohm'), 'imag': q(-10, 'Ohm')}}})
    assert task.calls[0] == ('source', '1', 'None')
    assert list(map(float, task.calls[1][2:])) == pytest.approx([.05, -.01])
