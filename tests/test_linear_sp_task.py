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
    def SetProperty(self, key, value): self.props[key] = value
    def GetProperty(self, key): return self.props[key]
    def SetSweepData(self, low, high, points):
        self.props['fmin'], self.props['fmax'] = low, high
        self.calls.append(('sweep', low, high, points))
    def GetTypeForTask(self, name): return self.kind
    def SetConstPortImpedance(self, port, real, imaginary):
        self.calls.append(('impedance', port, real, imaginary))


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
    assert report['port_impedances_readback'] == 'unsupported'


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
