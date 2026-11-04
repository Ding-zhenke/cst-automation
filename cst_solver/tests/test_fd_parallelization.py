"""F-domain CPU controls must never change the transient Solver settings."""
from types import SimpleNamespace

import pytest

from cst_solver.simulation.solver import SolverMixin
from tpc_service.sessions.model_api import dispatch


class App(SolverMixin):
    def __init__(self, submit=None):
        self.history = []
        self.cst_file = SimpleNamespace(model3d=SimpleNamespace(
            add_to_history=submit or (lambda title, code: self.history.append((title, code)))))


def test_fd_cpu_configuration_uses_documented_namespace_and_preserves_evidence():
    app = App()
    settings = dict(enabled=True, threads=12, cpu_devices=2)
    report = app.configure_fd_parallelization(settings)
    assert app.history[0][1].splitlines() == [
        'FDSolver.UseParallelization True',
        'FDSolver.MaxCPUs "12"',
        'FDSolver.MaximumNumberOfCPUDevices "2"',
    ]
    assert report['requested'] == settings and report['history_submitted'] is True
    assert not report['readback_verified'] and not report['solver_verified']
    assert not report['cpu_parallelization_verified'] and report['actual_threads'] is None
    assert settings == dict(enabled=True, threads=12, cpu_devices=2)


@pytest.mark.parametrize('settings,command', [
    ({'enabled': False}, 'FDSolver.UseParallelization False'),
    ({'enabled': True}, 'FDSolver.UseParallelization True'),
    ({'threads': 4}, 'FDSolver.MaxCPUs "4"'),
    ({'cpu_devices': 1}, 'FDSolver.MaximumNumberOfCPUDevices "1"'),
])
def test_sparse_controls_preserve_omitted_settings(settings, command):
    app = App()
    app.configure_fd_parallelization(settings)
    assert app.history == [('Configure FD CPU parallelization', command)]


@pytest.mark.parametrize('settings', [None, {}, [], {'gpu': True}, {'enabled': 'True'},
    {'threads': True}, {'threads': 0}, {'threads': -1}, {'threads': 2.5},
    {'threads': '8'}, {'cpu_devices': False}, {'cpu_devices': 0},
    {'threads': 2147483648}, {'enabled': True, 'cpu_devices': 'bad'}])
def test_invalid_configuration_never_touches_the_project(settings):
    class Unopened(SolverMixin):
        @property
        def cst_file(self):
            pytest.fail('Invalid configuration accessed CST')
    with pytest.raises(ValueError):
        Unopened().configure_fd_parallelization(settings)


def test_session_preflights_invalid_last_call_before_prior_geometry():
    seen = []
    app = SimpleNamespace(new_component=lambda name: seen.append(name))
    with pytest.raises(Exception):
        dispatch(app, [{'method': 'new_component', 'args': ['never-created']},
            {'method': 'configure_fd_parallelization', 'args': [{'threads': 0}]}])
    assert not seen


def test_existing_session_route_returns_unverified_configuration_receipt():
    app = App()
    result = dispatch(app, [{'method': 'configure_fd_parallelization',
                            'args': [{'enabled': True, 'threads': 6}]}])
    assert len(app.history) == 1
    assert result['configuration_receipts'][0]['method'] == 'configure_fd_parallelization'
    assert not result['configuration_receipts'][0]['receipt']['cpu_parallelization_verified']


def test_partial_native_failure_preserves_evidence_and_does_not_retry():
    from cst_solver.simulation.frequency import FDomainConfigurationError
    calls = []
    def broken(title, code):
        calls.append(code)
        raise RuntimeError('Native write interrupted')
    app = App(broken)
    app._circuit_facade = SimpleNamespace(_spec={'old': True})
    with pytest.raises(FDomainConfigurationError) as error:
        app.configure_fd_parallelization({'enabled': True})
    assert len(calls) == 1 and app._circuit_facade._spec is None
    assert error.value.details['history_submitted'] is None
    assert not error.value.details['cpu_parallelization_verified']
