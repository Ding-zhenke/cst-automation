"""Offline native sweep contract checks; history submission does not run CST."""
from types import SimpleNamespace

import pytest

from cst_solver.simulation.solver import SolverMixin


def sweep_app():
    history = []
    app = SolverMixin()
    app.cst_file = SimpleNamespace(model3d=SimpleNamespace(
        add_to_history=lambda title, code: history.append((title, code))))
    return app, history


def test_mixed_native_axes_are_one_cartesian_configuration_without_solving():
    app, history = sweep_app()
    app.configure_sweep('native', {
        'gap': {'mode': 'linear', 'start': -1, 'stop': 1, 'samples': 3},
        'sigma': {'mode': 'logarithmic', 'start': 10, 'stop': 1000, 'samples': 4},
        'state': [0, 1],
    }, replace_all=True)
    assert len(history) == 1
    code = history[0][1]
    assert '.AddParameter_Samples "native", "gap", "-1", "1", "3", "False"' in code
    assert '.AddParameter_Samples "native", "sigma", "10", "1000", "4", "True"' in code
    assert '.AddParameter_ArbitraryPoints "native", "state", "0;1"' in code
    assert code.index('.DeleteAllSequences') < code.index('.AddSequence')
    assert all(word not in code for word in ('.Start', '.Reset', '.Save', '.Rebuild'))


@pytest.mark.parametrize('method', ['configure_sweep', 'configure_discrete_sweep'])
def test_cartesian_product_limit_rejected_before_replacement(method):
    app, history = sweep_app()
    with pytest.raises(ValueError, match='1000000|1,000,000|Cartesian'):
        getattr(app, method)('native', {'first': list(range(1001)), 'last': list(range(1000))},
                             replace_all=True)
    assert history == []


def test_mixed_cartesian_product_limit_counts_native_ranges():
    app, history = sweep_app()
    with pytest.raises(ValueError, match='1000000|1,000,000|Cartesian'):
        app.configure_sweep('native', {
            'gap': {'mode': 'linear', 'start': 1, 'stop': 2, 'samples': 10000},
            'state': list(range(101)),
        })
    assert history == []


def test_cartesian_limit_is_inclusive_without_materializing_the_product():
    app, history = sweep_app()
    app.configure_sweep('native', {
        'gap': {'mode': 'linear', 'start': 1, 'stop': 2, 'samples': 10000},
        'state': list(range(100)),
    })
    assert len(history) == 1
    assert len(history[0][1]) < 1000


@pytest.mark.parametrize('sequence', ['bad\x00name', 'bad\tname', 'bad\x1fname', 'bad\x7fname',
                                       'bad"\n.Start\n\''])
def test_sequence_control_characters_and_injection_rejected(sequence):
    app, history = sweep_app()
    with pytest.raises(ValueError):
        app.configure_sweep(sequence, {'gap': [1, 2]}, replace_all=True)
    assert history == []


@pytest.mark.parametrize('sequence', ['', ' ', 'x' * 129, 'bad\x00name', 'bad\tname',
                                       'bad"\n.Start\n\''])
def test_standalone_sequence_creation_validates_before_history(sequence):
    app, history = sweep_app()
    with pytest.raises(ValueError):
        app.add_parameter_sweep_sequence(sequence)
    assert history == []


def test_standalone_sequence_creation_preserves_names_with_spaces():
    app, history = sweep_app()
    app.add_parameter_sweep_sequence('Material states')
    assert '.AddSequence "Material states"' in history[0][1]
    assert '.Start' not in history[0][1] and '.Reset' not in history[0][1]


@pytest.mark.parametrize('value', [True, float('nan'), float('inf'), '1', '1: Stop', 10**400])
def test_points_reject_invalid_native_double_values(value):
    app, history = sweep_app()
    with pytest.raises(ValueError):
        app.configure_sweep('native', {'valid': [1], 'invalid': [value]}, replace_all=True)
    assert history == []


@pytest.mark.parametrize('axis', [
    {'mode': 'linear', 'start': '1', 'stop': 2, 'samples': 2},
    {'mode': 'linear', 'start': 1, 'stop': 10**400, 'samples': 2},
    {'mode': 'logarithmic', 'start': 0, 'stop': 10, 'samples': 2},
    {'mode': 'logarithmic', 'start': -10, 'stop': -1, 'samples': 2},
    {'mode': 'log', 'start': 1, 'stop': 10, 'samples': 2},
    {'mode': 'linear', 'start': 1, 'stop': 2, 'samples': 10001},
    {'mode': 'linear', 'start': 1, 'stop': 2, 'samples': True},
    {'mode': 'linear', 'start': 1, 'stop': 2, 'samples': 2, 'step': 1},
])
def test_range_rejection_is_atomic(axis):
    app, history = sweep_app()
    with pytest.raises(ValueError):
        app.configure_sweep('native', {'valid': [1], 'invalid': axis}, replace_all=True)
    assert history == []


def test_legacy_sample_helper_preserves_safe_numeric_string_bounds():
    app, history = sweep_app()
    app.add_sweep_parameter_samples('native', 'gap', '-.4', '.4', 3)
    assert '"-0.4", "0.4", "3", "False"' in history[0][1]


@pytest.mark.parametrize('lower', ['a/2', '1"\n.Start\n\'', 'nan', 'inf', '1_000'])
def test_legacy_sample_helper_rejects_expressions_and_injection(lower):
    app, history = sweep_app()
    with pytest.raises(ValueError):
        app.add_sweep_parameter_samples('native', 'gap', lower, '2', 3)
    assert history == []
