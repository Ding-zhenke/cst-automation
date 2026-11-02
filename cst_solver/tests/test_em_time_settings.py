from types import SimpleNamespace

import pytest

from cst_solver.simulation.solver import SolverMixin


class App(SolverMixin):
    def __init__(self, model):
        self.cst_file = SimpleNamespace(model3d=model)


@pytest.mark.parametrize('settings', [
    None, {}, [], {'unknown': 1}, {'stability_factor': True},
    {'stability_factor': '0.5'}, {'stability_factor': 0},
    {'stability_factor': -0.1}, {'stability_factor': 1.01},
    {'stability_factor': float('inf')}, {'stability_factor': float('nan')},
    {'output_sampling': False}, {'output_sampling': 'Every Step'},
    {'stability_factor': .5, 'output_sampling': 'False\nSolver.Start'},
])
def test_invalid_settings_never_access_project(settings):
    class Unopened(SolverMixin):
        @property
        def cst_file(self):
            pytest.fail('Invalid input must be rejected before project access')
    with pytest.raises(ValueError):
        Unopened().configure_em_time_settings(settings)


def test_settings_submit_only_one_history_without_run_reset_or_ds_access():
    submitted = []
    app = App(SimpleNamespace(add_to_history=lambda title, text: submitted.append((title, text))))
    request = {'stability_factor': .25, 'output_sampling': 'every_step'}
    report = app.configure_em_time_settings(request)
    assert len(submitted) == 1
    assert submitted[0][1].splitlines() == [
        'Solver.TimeStepStabilityFactor 0.25', 'Solver.AutomaticTimeSignalSampling False']
    assert report['scope'] == 'current_project_model3d'
    assert report['history_submitted'] is True
    assert report['readback'] is None and report['readback_status'] == 'unsupported'
    for key in ('readback_verified', 'internal_time_step_verified', 'output_sampling_verified', 'solver_verified'):
        assert report[key] is False
    request['stability_factor'] = .75
    assert report['requested']['stability_factor'] == .25


@pytest.mark.parametrize('settings,expected', [
    ({'output_sampling': 'automatic'}, 'Solver.AutomaticTimeSignalSampling True'),
    ({'output_sampling': 'every_step'}, 'Solver.AutomaticTimeSignalSampling False'),
    ({'stability_factor': 1}, 'Solver.TimeStepStabilityFactor 1'),
])
def test_sparse_settings_do_not_reset_omitted_controls(settings, expected):
    submitted = []
    app = App(SimpleNamespace(add_to_history=lambda title, text: submitted.append(text)))
    app.configure_em_time_settings(settings)
    assert submitted == [expected]


def test_history_error_keeps_uncertain_partial_submission_and_request():
    from cst_solver.simulation.em_time import EMTimeConfigurationError
    def broken(title, text):
        raise RuntimeError('native failure after first command')
    app = App(SimpleNamespace(add_to_history=broken))
    with pytest.raises(EMTimeConfigurationError) as error:
        app.configure_em_time_settings({'stability_factor': .5, 'output_sampling': 'every_step'})
    assert error.value.code == 'em_time_configuration_partial'
    assert error.value.details['stage'] == 'configure_em_time_settings'
    assert error.value.details['requested']['stability_factor'] == .5
    assert error.value.details['history_submitted'] is None
    assert len(error.value.details['native_commands']) == 2


def test_missing_3d_domain_fails_without_schematic_fallback():
    from cst_solver.simulation.em_time import EMTimeConfigurationError
    with pytest.raises(EMTimeConfigurationError) as error:
        App(None).configure_em_time_settings({'stability_factor': .5})
    assert error.value.code == 'em_time_unavailable'
    assert error.value.details['history_submitted'] is False


@pytest.mark.parametrize('fails', [False, True])
def test_attempted_em_mutation_invalidates_existing_circuit_cache(fails):
    from cst_solver.simulation.em_time import EMTimeConfigurationError
    def submit(title, text):
        if fails:
            raise RuntimeError('interrupted')
    app = App(SimpleNamespace(add_to_history=submit))
    app._circuit_facade = SimpleNamespace(_spec={'cached': True})
    if fails:
        with pytest.raises(EMTimeConfigurationError):
            app.configure_em_time_settings({'stability_factor': .5})
    else:
        app.configure_em_time_settings({'stability_factor': .5})
    assert app._circuit_facade._spec is None
