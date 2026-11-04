"""Model-band expressions must reach CST as quoted, unevaluated arguments."""
from types import SimpleNamespace

import pytest

from cst_solver.parameters import ParametersMixin
from tpc_service.sessions.model_api import dispatch


class App(ParametersMixin):
    def __init__(self):
        self.history = []
        self.cst_file = SimpleNamespace(model3d=SimpleNamespace(
            add_to_history=lambda title, code: self.history.append((title, code))))


@pytest.mark.parametrize('method', ['set_frequency_range', 'freq_limit'])
@pytest.mark.parametrize('bounds, command', [
    (('fmin', 'fmax'), 'Solver.FrequencyRange "fmin", "fmax"'),
    (('f0-bw/2', 'f0+bw/2'), 'Solver.FrequencyRange "f0-bw/2", "f0+bw/2"'),
    ((0, 140.5), 'Solver.FrequencyRange "0", "140.5"'),
    ((0, 'fmax'), 'Solver.FrequencyRange "0", "fmax"'),
])
def test_model_band_preserves_expressions_and_numeric_compatibility(method, bounds, command):
    app = App()
    getattr(app, method)(*bounds)
    assert len(app.history) == 1
    assert [line.strip() for line in app.history[0][1].splitlines()
            if line.strip() and not line.strip().startswith("'")] == [command]


@pytest.mark.parametrize('arguments', [
    {'args': ['fmin', 'fmax']},
    {'kwargs': {'fmin': 'fmin', 'fmax': 'fmax'}},
])
def test_session_model_api_reaches_frequency_wrapper_without_resolving_parameters(arguments):
    app = App()
    dispatch(app, [{'method': 'set_frequency_range', **arguments}])
    assert len(app.history) == 1
    assert 'Solver.FrequencyRange "fmin", "fmax"' in app.history[0][1]
