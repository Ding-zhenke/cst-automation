import pytest

from cst_solver.circuit.linear_sp import configure_linear_sp_task


class FakeTask:
    def __init__(self, exists=False):
        self.exists = exists
        self.props = {}
        self.calls = []

    def Reset(self): pass
    def Name(self, value): self.name = value
    def DoesExist(self): return self.exists
    def Type(self, value): self.kind = value
    def Create(self): self.exists = True
    def SetLocalUnit(self, dimension, unit):
        if not hasattr(self, 'units'): self.units = {}
        self.units[dimension] = unit
    def GetUnit(self, dimension): return self.units[dimension]
    def SetProperty(self, key, value): self.props[key] = value
    def GetProperty(self, key): return self.props[key]
    def SetSweepData(self, low, high, points):
        self.props['fmin'], self.props['fmax'] = low, high
        self.calls.append(('sweep', low, high, points))
    def GetTypeForTask(self, name): return self.kind
    def SetConstPortImpedance(self, port, real, imaginary):
        self.calls.append(('impedance', port, real, imaginary))
    def GetPortImpedanceType(self, port): return 'Constant'
    def GetPortSourceType(self, port): return 'None'


class FakeSchematic:
    def __init__(self, exists=False):
        self.SimulationTask = FakeTask(exists)
        self.ExternalPort = FakePorts()


class FakePorts:
    def StartPortNameIteration(self): self.names = iter(['P1', 'P2'])
    def GetNextPortName(self): return next(self.names, '')


def test_creates_explicit_independent_task_with_requested_sweep_and_ports():
    schematic = FakeSchematic()
    report = configure_linear_sp_task(schematic, 'LinearSP', frequency_unit='GHz',
                                      fmin=2, fmax=5, samples=4,
                                      port_impedances={'P1': 50, 'P2': 75})
    task = schematic.SimulationTask
    assert task.kind == 'S-Parameters' and task.units == {'Frequency': 'GHz', 'Resistance': 'Ohm'}
    assert ('sweep', '2', '5', '4') in task.calls
    assert ('impedance', 'P2', '75', '0') in task.calls
    assert report['solver_verified'] is False
    assert report['frequency_unit_readback'] == 'GHz'
    assert report['port_modes']['P1'] == {'impedance_type': 'Constant', 'source_type': 'unsupported'}
    assert report['port_impedances_readback'] == 'unsupported'


def test_rejects_wrong_native_frequency_unit_after_task_creation():
    schematic = FakeSchematic()
    schematic.SimulationTask.GetUnit = lambda dimension: 'MHz'
    from cst_solver.circuit.adapter import CircuitError
    with pytest.raises(CircuitError) as caught:
        configure_linear_sp_task(schematic, 'LinearSP', frequency_unit='GHz',
                                 fmin=2, fmax=5, samples=4, port_impedances={'P1': 50, 'P2': 50})
    assert caught.value.code == 'circuit_build_partial'


def test_partial_task_failure_retains_native_stage_and_error():
    from cst_solver.circuit.adapter import CircuitError
    schematic = FakeSchematic()
    def fail(key, value):
        if key == 'broadband sweep': raise RuntimeError('native broadband error')
    schematic.SimulationTask.SetProperty = fail
    with pytest.raises(CircuitError) as caught:
        configure_linear_sp_task(schematic, 'LinearSP', frequency_unit='GHz',
                                 fmin=2, fmax=5, samples=4, port_impedances={'P1':50,'P2':50})
    assert caught.value.details['failure_stage'] == 'set_broadband_sweep'
    assert caught.value.details['original_message'] == 'native broadband error'


def test_sp_never_calls_unsupported_port_source_getter():
    schematic = FakeSchematic()
    schematic.SimulationTask.GetPortSourceType = lambda port: pytest.fail('not supported for SP')
    report = configure_linear_sp_task(schematic, 'LinearSP', frequency_unit='GHz',
                                      fmin=2, fmax=5, samples=4, port_impedances={'P1':50,'P2':50})
    assert report['port_modes']['P1']['source_type'] == 'unsupported'


def test_rejects_port_whose_native_impedance_type_is_not_constant():
    schematic = FakeSchematic()
    schematic.SimulationTask.GetPortImpedanceType = lambda port: 'Block_Dependent'
    from cst_solver.circuit.adapter import CircuitError
    with pytest.raises(CircuitError):
        configure_linear_sp_task(schematic, 'LinearSP', frequency_unit='GHz',
                                 fmin=2, fmax=5, samples=4, port_impedances={'P1': 50, 'P2': 50})


@pytest.mark.parametrize('bad', [0, -1, float('nan')])
def test_rejects_invalid_port_impedance_before_creating_task(bad):
    schematic = FakeSchematic()
    with pytest.raises(ValueError):
        configure_linear_sp_task(schematic, 'LinearSP', frequency_unit='GHz',
                                 fmin=2, fmax=5, samples=4, port_impedances={'P1': bad})
    assert not schematic.SimulationTask.exists


def test_refuses_to_replace_existing_task():
    schematic = FakeSchematic(exists=True)
    with pytest.raises(ValueError):
        configure_linear_sp_task(schematic, 'LinearSP', frequency_unit='GHz',
                                 fmin=2, fmax=5, samples=4, port_impedances={'P1': 50})
    assert not schematic.SimulationTask.calls


def test_inspect_existing_is_read_only_and_does_not_certify_sources():
    from cst_solver.circuit.linear_sp import inspect_existing_linear_sp
    schematic = FakeSchematic()
    configure_linear_sp_task(schematic, 'LinearSP', frequency_unit='GHz',
                             fmin=2, fmax=5, samples=4, port_impedances={'P1': 50, 'P2': 75})
    before = list(schematic.SimulationTask.calls)
    report = inspect_existing_linear_sp(schematic, 'LinearSP', ['P1', 'P2'])
    assert schematic.SimulationTask.calls == before
    assert report['frequency_unit'] == 'GHz' and report['properties']['fmin'] == '2'
    assert report['port_impedances_readback'] == report['sample_count_readback'] == 'unsupported'
    assert not report['zero_external_sources_verified'] and not report['solver_verified']


def test_completes_existing_reviewed_task_without_recreation():
    from cst_solver.circuit.linear_sp import inspect_existing_linear_sp, complete_existing_linear_sp_task
    schematic = FakeSchematic()
    task = schematic.SimulationTask
    task.Type('S-Parameters'); task.Create(); task.units = {'Frequency':'GHz', 'Resistance':'Ohm'}
    task.props = {'maximum frequency range':'false', 'circuit simulator':'cst', 'broadband sweep':'true',
                  'logarithmic sweep':'false', 'fmin':'0', 'fmax':'1000'}
    expected = inspect_existing_linear_sp(schematic, 'LinearSP', ['P1', 'P2'])
    report = complete_existing_linear_sp_task(schematic, 'LinearSP', expected=expected,
        frequency_unit='GHz', fmin=2, fmax=5, samples=4, port_impedances={'P1':50, 'P2':75})
    assert report['solver_verified'] is False and task.exists
    assert ('sweep', '2', '5', '4') in task.calls
    assert ('impedance', 'P2', '75', '0') in task.calls


def test_existing_task_changed_since_review_is_rejected_before_writes():
    from cst_solver.circuit.linear_sp import inspect_existing_linear_sp, complete_existing_linear_sp_task
    schematic = FakeSchematic()
    task = schematic.SimulationTask
    task.Type('S-Parameters'); task.Create(); task.units = {'Frequency':'GHz', 'Resistance':'Ohm'}
    task.props = {'maximum frequency range':'false', 'circuit simulator':'cst', 'broadband sweep':'true',
                  'logarithmic sweep':'false', 'fmin':'0', 'fmax':'1000'}
    expected = inspect_existing_linear_sp(schematic, 'LinearSP', ['P1', 'P2'])
    task.props['fmax'] = '999'
    with pytest.raises(ValueError, match='changed'):
        complete_existing_linear_sp_task(schematic, 'LinearSP', expected=expected,
            frequency_unit='GHz', fmin=2, fmax=5, samples=4, port_impedances={'P1':50, 'P2':75})
    assert not task.calls


def test_existing_task_failure_records_attempt_and_completed_steps():
    from cst_solver.circuit.adapter import CircuitError
    from cst_solver.circuit.linear_sp import inspect_existing_linear_sp, complete_existing_linear_sp_task
    schematic = FakeSchematic()
    task = schematic.SimulationTask
    task.Type('S-Parameters'); task.Create(); task.units = {'Frequency':'GHz', 'Resistance':'Ohm'}
    task.props = {'maximum frequency range':'false', 'circuit simulator':'cst', 'broadband sweep':'true',
                  'logarithmic sweep':'false', 'fmin':'0', 'fmax':'1000'}
    expected = inspect_existing_linear_sp(schematic, 'LinearSP', ['P1', 'P2'])
    original = task.SetProperty
    def set_property(key, value):
        if key == 'broadband sweep': raise RuntimeError('native setter failed')
        original(key, value)
    task.SetProperty = set_property
    with pytest.raises(CircuitError) as caught:
        complete_existing_linear_sp_task(schematic, 'LinearSP', expected=expected,
            frequency_unit='GHz', fmin=2, fmax=5, samples=4, port_impedances={'P1':50, 'P2':75})
    detail = caught.value.details
    assert detail['attempted'] == {'stage':'set_broadband_sweep', 'arguments':['broadband sweep', 'False']}
    assert detail['completed'] == []
    assert detail['unchanged'] == [{'property': 'maximum frequency range', 'native_value': 'false'}]
    assert detail['original_message'] == 'native setter failed'


def test_existing_task_does_not_write_reviewed_matching_properties():
    from cst_solver.circuit.linear_sp import inspect_existing_linear_sp, complete_existing_linear_sp_task
    schematic = FakeSchematic()
    task = schematic.SimulationTask
    task.Type('S-Parameters'); task.Create(); task.units = {'Frequency':'GHz', 'Resistance':'Ohm'}
    task.props = {'maximum frequency range':'false', 'circuit simulator':'cst', 'broadband sweep':'true',
                  'logarithmic sweep':'false', 'fmin':'0', 'fmax':'1000'}
    expected = inspect_existing_linear_sp(schematic, 'LinearSP', ['P1', 'P2'])
    original = task.SetProperty
    def set_property(key, value):
        if key in ('maximum frequency range', 'logarithmic sweep', 'circuit simulator'):
            pytest.fail('Matching property should not be rewritten')
        original(key, value)
    task.SetProperty = set_property
    report = complete_existing_linear_sp_task(schematic, 'LinearSP', expected=expected,
        frequency_unit='GHz', fmin=2, fmax=5, samples=4, port_impedances={'P1':50, 'P2':75})
    assert {row['property'] for row in report['unchanged']} == {'maximum frequency range', 'logarithmic sweep'}


@pytest.mark.parametrize('ports', [[], ['P1'], ['P1', 'P1'], [True]])
def test_inspect_rejects_bad_ports(ports):
    from cst_solver.circuit.linear_sp import inspect_existing_linear_sp
    with pytest.raises(ValueError):
        inspect_existing_linear_sp(FakeSchematic(exists=True), 'LinearSP', ports)
