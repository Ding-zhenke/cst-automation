from types import SimpleNamespace

import pytest

from cst_solver.simulation.solver import SolverMixin


def test_discrete_points_configure_without_start_or_reset():
    seen = []
    app = SolverMixin()
    app.cst_file = SimpleNamespace(model3d=SimpleNamespace(add_to_history=lambda name, code: seen.append(code)))
    app.add_sweep_parameter_arbitrary_points('scan', 'sigma', [0, 100, 10000])
    assert '.AddParameter_ArbitraryPoints "scan", "sigma", "0;100;10000"' in seen[0]
    assert '.Start' not in seen[0] and '.Reset' not in seen[0]


@pytest.mark.parametrize('points', [[], [True], [float('nan')], [float('inf')], '0;10', ['0: Stop']])
def test_bad_points_fail_before_history(points):
    app = SolverMixin()
    app.cst_file = SimpleNamespace(model3d=SimpleNamespace(add_to_history=lambda *a: pytest.fail('mutation')))
    with pytest.raises((TypeError, ValueError)):
        app.add_sweep_parameter_arbitrary_points('scan', 'sigma', points)


def test_complete_sweep_validates_all_axes_before_mutation():
    seen = []
    app = SolverMixin()
    app.cst_file = SimpleNamespace(model3d=SimpleNamespace(add_to_history=lambda name, code: seen.append(code)))
    with pytest.raises(ValueError):
        app.configure_discrete_sweep('scan', {'gap': [1, 3], 'sigma': [float('nan')]})
    assert not seen
    app.configure_discrete_sweep('scan', {'gap': [1, 3], 'sigma': [0, 100]}, replace_all=True)
    assert len(seen) == 1
    assert '.DeleteAllSequences' in seen[0] and '.AddSequence "scan"' in seen[0]
    assert seen[0].count('.AddParameter_ArbitraryPoints') == 2
    assert '.Start' not in seen[0] and '.Reset' not in seen[0]
