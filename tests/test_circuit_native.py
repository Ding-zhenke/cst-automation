"""Regress native pitfalls without opening CST or running a solver."""
from pathlib import Path
from types import SimpleNamespace
import pytest

from cst_solver.circuit.native import (
    configure_hb_task, replace_parameter_sweep_sequences,
    read_spectral_component, write_real_curve,
)


class NativeTask:
    def __init__(self, kind='spectral lines'):
        self.kind, self.tones, self.created = kind, [], False
    def Reset(self): pass
    def Name(self, name): self.name = name
    def DoesExist(self): return True
    def GetTypeForTask(self, name): return self.kind
    def SetDiamondScheme(self, value): self.diamond = value
    def ClearFundamentalFrequencies(self): self.tones.clear()
    def AddFundamentalFrequency(self, f, n): self.tones.append((f, n))


def test_hb_preserves_parameter_expressions_and_does_not_run():
    task = NativeTask()
    app = SimpleNamespace(SimulationTask=task)
    result = configure_hb_task(app, 'Sweep\\HB', [
        {'frequency': 'pump_freq', 'order': 'pump_order'},
        {'frequency': 'rf_freq', 'order': 1},
    ])
    assert task.tones == [('pump_freq', 'pump_order'), ('rf_freq', '1')]
    assert task.diamond is False
    assert result['solver_verified'] is False


@pytest.mark.parametrize('tones', [[], [{'frequency': 'RF', 'order': -1}],
    [{'frequency': 'RF', 'order': True}], [{'frequency': 'RF\nbad', 'order': 1}]])
def test_invalid_hb_input_leaves_existing_tones_untouched(tones):
    task = NativeTask(); task.tones = [('original', '2')]
    with pytest.raises(ValueError): configure_hb_task(SimpleNamespace(SimulationTask=task), 'HB', tones)
    assert task.tones == [('original', '2')]


def test_wrong_task_type_is_not_modified():
    task = NativeTask('transient')
    with pytest.raises(ValueError):
        configure_hb_task(SimpleNamespace(SimulationTask=task), 'HB', [{'frequency': 1, 'order': 1}])
    assert task.tones == []


def test_native_sweep_keeps_parent_and_children_and_replaces_sequences():
    calls = []
    sweep = SimpleNamespace(**{name: (lambda *args, n=name: calls.append((n, args))) for name in
        ['SetSimulationType', 'DeleteAllSequences', 'AddSequence', 'AddParameter_ArbitraryPoints']})
    app = SimpleNamespace(SimulationTask=NativeTask('parameter sweep'), ParameterSweep=sweep)
    replace_parameter_sweep_sequences(app, 'Sweep', {'FrequencyDirection': {'RF': [110, 170], 'DIR': [0, 1]}})
    assert calls[-2:] == [('AddParameter_ArbitraryPoints', ('FrequencyDirection', 'RF', '110;170')),
                          ('AddParameter_ArbitraryPoints', ('FrequencyDirection', 'DIR', '0;1'))]
    assert calls[1] == ('DeleteAllSequences', ())
    calls.clear()
    with pytest.raises(ValueError): replace_parameter_sweep_sequences(app, 'Sweep', {'s': {'RF': [float('nan')]}})
    assert calls == []


def test_spectral_read_requires_unique_frequency_and_passes_explicit_id():
    seen = []
    result = SimpleNamespace(GetArray=lambda axis: {'x': [5., 140.], 'yre': [2., 3.], 'yim': [0., -4.]}[axis])
    def read(path, rid): seen.append((path, rid)); return result
    app = SimpleNamespace(ResultTree=SimpleNamespace(GetResultFromTreeItem=read))
    assert read_spectral_component(app, 'Tasks\\HB\\Voltage Spectral Lines\\P', 140, result_id=7) == 3-4j
    assert seen[-1][1] == 7
    with pytest.raises(ValueError): read_spectral_component(app, 'P', 141, result_id=7)
    with pytest.raises(ValueError): read_spectral_component(app, 'P', 140, result_id=None)
    result.GetArray = lambda axis: {'x': [140, 140], 'yre': [1, 2], 'yim': [0, 0]}[axis]
    with pytest.raises(ValueError): read_spectral_component(app, 'P', 140, result_id=7)


class NativeTree:
    """Deleting an existing leaf also deletes its signal file, as CST does."""
    def __init__(self, path): self.path, self.items, self.events = path, {'Results\\Band', 'Results\\Band\\S21'}, []
    def DoesTreeItemExist(self, name): return name in self.items
    def GetFirstChildName(self, name):
        return next((item for item in sorted(self.items) if item.startswith(name + '\\')), '')
    def Reset(self): pass
    def Name(self, name): self.name = name
    def Delete(self):
        self.events.append('delete'); self.items.remove(self.name); self.path.unlink()
    def Add(self):
        if self.name.endswith('S21'): assert self.path.is_file()
        self.items.add(self.name); self.events.append('add')
    def __getattr__(self, name): return lambda *args: None


def test_curve_replacement_survives_associated_file_deletion_and_disables_double_log(tmp_path):
    file = tmp_path / 'S21.sig'; file.write_text('old')
    tree = NativeTree(file); points, options = [], {}
    def save(path): tree.events.append('save'); Path(path).write_text('new')
    curve = SimpleNamespace(AppendXY=lambda x, y: points.append((float(x), float(y))),
        Title=lambda x: None, SetXLabelAndUnit=lambda *a: None, SetYLabelAndUnit=lambda *a: None,
        SetLogarithmicFactor=lambda v: options.update(log=v), Save=save)
    app = SimpleNamespace(ResultTree=tree, Result1D=lambda _: curve)
    kwargs = dict(title='Transmission', x_label='RF frequency', x_unit='GHz', y_label='Magnitude',
                  y_unit='dB', values_in_db=True)
    write_real_curve(app, 'Results\\Band\\S21', file, [110, 170], [-3, -4], replace=True, **kwargs)
    assert tree.events == ['delete', 'save', 'add']
    assert file.read_text() == 'new' and options['log'] == '-1'
    assert points == [(110, -3), (170, -4)]
    tree.events.clear()
    with pytest.raises(ValueError): write_real_curve(app, 'Results\\Band\\S21', file, [1], [2], **kwargs)
    assert tree.events == [] and file.read_text() == 'new'
    with pytest.raises(ValueError): write_real_curve(app, 'Results\\Band\\S21', file, [2, 1], [1, 2], replace=True, **kwargs)
    assert tree.events == []


def test_curve_replacement_refuses_folder_without_deleting_children(tmp_path):
    file = tmp_path / 'curve.sig'
    file.write_text('original')
    tree = NativeTree(file)
    app = SimpleNamespace(ResultTree=tree,
                          Result1D=lambda _: pytest.fail('Folder must be rejected before writing'))
    with pytest.raises(ValueError, match='leaf'):
        write_real_curve(app, 'Results\\Band', file, [1, 2], [3, 4],
                         title='Example', x_label='x', x_unit='', y_label='y', y_unit='',
                         replace=True)
    assert tree.items == {'Results\\Band', 'Results\\Band\\S21'}
    assert tree.events == [] and file.read_text() == 'original'
