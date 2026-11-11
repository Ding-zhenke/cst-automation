"""Offline command contracts for documented CST 2026 tetrahedral controls."""
from types import SimpleNamespace

import pytest

from cst_solver.mesh.mesh import MeshMixin
from cst_solver.simulation.solver import SolverMixin


class App(SolverMixin, MeshMixin):
    def __init__(self, submit=None):
        self.history = []
        self.cst_file = SimpleNamespace(model3d=SimpleNamespace(
            add_to_history=submit or (lambda title, code: self.history.append((title, code)))))


def test_frequency_settings_keep_solve_sampling_adaptation_and_output_separate():
    app = App()
    request = {
        'sampling_intervals': [
            {'start': 1, 'stop': 100, 'spacing': 'logarithmic', 'samples': 5},
            {'start': 1, 'stop': 100, 'spacing': 'automatic', 'samples': None},
        ],
        'adaptation_frequencies': [1, 50], 'output_samples': 1001,
        'output_spacing': 'linear', 'sweep_error': .01,
        'sweep_minimum_samples': 3, 'sweep_error_checks': 2,
        'stop_sweep_if_converged': True,
    }
    report = app.configure_fd_frequency(request)
    assert app.history[0][1].splitlines() == [
        'FDSolver.AddSampleInterval "1", "100", "5", "Logarithmic", False',
        'FDSolver.AddSampleInterval "1", "100", "", "Automatic", False',
        'FDSolver.AddSampleInterval "1", "1", "1", "Single", True',
        'FDSolver.AddSampleInterval "50", "50", "1", "Single", True',
        'FDSolver.SetNumberOfResultDataSamples "1001"',
        'FDSolver.SetResultDataSamplingMode "Frequency (linear)"',
        'FDSolver.SetSweepThreshold "S-Parameters", "0.01"',
        'FDSolver.SweepMinimumSamples "3"',
        'FDSolver.SweepErrorChecks "2"',
        'FDSolver.SetStopSweepIfCriterionMet True',
    ]
    assert report['interval_update'] == 'append'
    assert report['history_submitted'] is True
    assert report['readback_verified'] is False
    assert report['solver_verified'] is False
    request['adaptation_frequencies'].append(90)
    assert report['requested']['adaptation_frequencies'] == [1., 50.]


@pytest.mark.parametrize('method,settings,expected', [
    ('configure_fd_frequency', {'output_samples': 20},
     ['FDSolver.SetNumberOfResultDataSamples "20"']),
    ('configure_fd_frequency', {'sampling_intervals': [
        {'start': 10, 'stop': 10, 'spacing': 'single', 'samples': 1}]},
     ['FDSolver.AddSampleInterval "10", "10", "1", "Single", False']),
    ('configure_tetrahedral_mesh', {'steps_per_wavelength': 6},
     ['Mesh.StepsPerWavelengthTet "6"']),
    ('configure_tetrahedral_mesh', {'material_refinement': False},
     ['Mesh.MaterialRefinementTet False']),
])
def test_sparse_settings_only_submit_requested_controls(method, settings, expected):
    app = App()
    report = getattr(app, method)(settings)
    assert len(app.history) == 1
    assert app.history[0][1].splitlines() == expected
    assert report['readback_status'] == 'unsupported'
    assert report['mesh_verified'] is False


def test_tetrahedral_mesh_uses_local_solid_edge_limits_and_separate_adaptation():
    app = App()
    report = app.configure_tetrahedral_mesh({
        'steps_per_wavelength': 6, 'minimum_steps': 10,
        'material_refinement': True,
        'local_solids': [{'solid': 'device:gap', 'max_step': .005}],
        'adaptation': {'enabled': True, 'min_passes': 2, 'max_passes': 6,
                       'max_delta_s': .02, 'delta_s_checks': 2,
                       'refinement_percentage': 30},
    })
    assert app.history[0][1].splitlines() == [
        'Mesh.StepsPerWavelengthTet "6"',
        'Mesh.MinimumStepNumberTet "10"',
        'Mesh.MaterialRefinementTet True',
        'Solid.SetMeshStepwidthTet "device:gap", "0.005"',
        'FDSolver.MeshAdaptionTet True',
        'MeshAdaption3D.SetType "HighFrequencyTet"',
        'MeshAdaption3D.MinPasses "2"',
        'MeshAdaption3D.MaxPasses "6"',
        'MeshAdaption3D.MaxDeltaS "0.02"',
        'MeshAdaption3D.NumberOfDeltaSChecks "2"',
        'MeshAdaption3D.RefThetaFactor "30"',
    ]
    assert report['solver_verified'] is False
    assert report['mesh_verified'] is False


def test_global_tet_controls_identify_legacy_backend_without_claiming_active_group():
    app = App()
    report = app.configure_tetrahedral_mesh({'steps_per_wavelength': 12})
    assert report['global_controls_backend'] == 'legacy_mesh'
    assert report['active_mesh_settings_group'] is None
    assert report['readback'] is None and not report['mesh_verified']
    assert report['warnings']


def test_local_and_adaptive_configuration_does_not_claim_global_density_submission():
    app = App()
    report = app.configure_tetrahedral_mesh({'adaptation': {'max_passes': 3}})
    assert report['global_controls_backend'] is None
    assert report['active_mesh_settings_group'] is None
    assert report['warnings'] == []


def test_explicit_replacement_configures_three_adaptation_points_and_one_sweep():
    app = App()
    report = app.configure_fd_frequency({
        'replace_intervals': True,
        'sampling_intervals': [
            {'start': 300, 'stop': 320, 'spacing': 'automatic', 'samples': None}],
        'adaptation_frequencies': [300, 310, 320],
    })
    assert app.history[0][1].splitlines() == [
        'FDSolver.ResetSampleIntervals "all"',
        'FDSolver.AddSampleInterval "300", "320", "", "Automatic", False',
        'FDSolver.AddSampleInterval "300", "300", "1", "Single", True',
        'FDSolver.AddSampleInterval "310", "310", "1", "Single", True',
        'FDSolver.AddSampleInterval "320", "320", "1", "Single", True',
    ]
    assert report['interval_update'] == 'replace_all'
    assert report['readback_verified'] is False


def test_zero_lower_bound_reports_native_dc_sample_limitation():
    app = App()
    report = app.configure_fd_frequency({'sampling_intervals': [
        {'start': 0, 'stop': 1, 'spacing': 'linear', 'samples': 3}]})
    assert report['warnings']
    assert report['requested']['sampling_intervals'][0]['start'] == 0
    assert report['sampling_verified'] is False


def test_append_receipt_identifies_inherited_intervals_are_not_replaced():
    report = App().configure_fd_frequency({'adaptation_frequencies': [300, 310, 320]})
    assert report['interval_update'] == 'append'
    assert any('inherited' in warning for warning in report['warnings'])


def test_explicit_automatic_adaptation_is_available_for_affordable_meshes():
    app = App()
    report = app.configure_fd_frequency({'sampling_intervals': [
        {'start': 300, 'stop': 320, 'spacing': 'automatic', 'samples': None,
         'adaptation': True}]})
    assert app.history[0][1] == 'FDSolver.AddSampleInterval "300", "320", "", "Automatic", True'
    assert report['requested']['sampling_intervals'][0]['adaptation'] is True


@pytest.mark.parametrize('adaptation', [1, 'True', None])
def test_interval_adaptation_requires_a_boolean_before_project_access(adaptation):
    class Unopened(SolverMixin):
        @property
        def cst_file(self):
            pytest.fail('Invalid interval adaptation accessed the project')
    with pytest.raises(ValueError):
        Unopened().configure_fd_frequency({'sampling_intervals': [
            {'start': 300, 'stop': 320, 'spacing': 'automatic', 'samples': None,
             'adaptation': adaptation}]})


BAD_FREQUENCY = [
    None, {}, [], {'typo': 1}, {'output_samples': True}, {'output_samples': 1},
    {'output_samples': 2}, {'output_samples': 2.5}, {'output_samples': '1001'},
    {'output_spacing': 'linear\nFDSolver.Start'},
    {'sweep_error': float('nan')}, {'sweep_error': float('inf')},
    {'sweep_error': 0}, {'sweep_error': True}, {'sweep_error': '0.1'},
    {'stop_sweep_if_converged': 1}, {'sweep_error_checks': 0},
    {'replace_intervals': True}, {'replace_intervals': False}, {'replace_intervals': 'True'},
    {'replace_intervals': True, 'output_samples': 20},
    {'output_samples': 2147483648},
    {'adaptation_frequencies': []}, {'adaptation_frequencies': [0]},
    {'adaptation_frequencies': [True]}, {'adaptation_frequencies': [float('inf')]},
    {'sampling_intervals': []}, {'sampling_intervals': ['1-10']},
    {'sampling_intervals': [{'start': 10, 'stop': 1, 'spacing': 'linear', 'samples': 3}]},
    {'sampling_intervals': [{'start': 0, 'stop': 10, 'spacing': 'logarithmic', 'samples': 3}]},
    {'sampling_intervals': [{'start': 1, 'stop': 10, 'spacing': 'single', 'samples': 1}]},
    {'sampling_intervals': [{'start': 1, 'stop': 10, 'spacing': 'linear', 'samples': None}]},
    {'sampling_intervals': [{'start': 1, 'stop': 10, 'spacing': 'linear', 'samples': True}]},
    {'sampling_intervals': [{'start': 1, 'stop': 10, 'spacing': 'linear', 'samples': 3,
                             'typo': True}]},
]
BAD_MESH = [
    None, {}, [], {'StepsPerWavelengthTet': 6}, {'steps_per_wavelength': True},
    {'steps_per_wavelength': '6'}, {'minimum_steps': 0},
    {'minimum_steps': float('nan')}, {'material_refinement': 'True'},
    {'local_solids': []}, {'local_solids': [{'solid': 'gap', 'max_step': .1}]},
    {'local_solids': [{'solid': 'c:gap\"\nSolver.Start', 'max_step': .1}]},
    {'local_solids': [{'solid': 'c:gap', 'max_step': -1}]},
    {'local_solids': [{'solid': 'c:gap', 'max_step': float('inf')}]},
    {'local_solids': [{'solid': 'c:gap', 'max_step': True}]},
    {'adaptation': {}}, {'adaptation': {'min_passes': True}},
    {'adaptation': {'min_passes': 5, 'max_passes': 4}},
    {'adaptation': {'max_delta_s': 0}}, {'adaptation': {'max_delta_s': 1.1}},
    {'adaptation': {'refinement_percentage': 101}},
    {'adaptation': {'reuse_mesh': True}},
]


@pytest.mark.parametrize('settings', BAD_FREQUENCY)
def test_bad_frequency_inputs_never_access_project(settings):
    class Unopened(SolverMixin):
        @property
        def cst_file(self):
            pytest.fail('Invalid frequency input accessed the project')
    with pytest.raises(ValueError):
        Unopened().configure_fd_frequency(settings)


@pytest.mark.parametrize('settings', BAD_MESH)
def test_bad_mesh_inputs_never_access_project(settings):
    class Unopened(MeshMixin):
        @property
        def cst_file(self):
            pytest.fail('Invalid mesh input accessed the project')
    with pytest.raises(ValueError):
        Unopened().configure_tetrahedral_mesh(settings)


def test_invalid_last_local_item_does_not_submit_valid_prefix():
    app = App()
    with pytest.raises(ValueError):
        app.configure_tetrahedral_mesh({'local_solids': [
            {'solid': 'c:valid', 'max_step': 1},
            {'solid': 'c:invalid', 'max_step': 'injection'},
        ]})
    assert app.history == []


@pytest.mark.parametrize('method,settings', [
    ('configure_fd_frequency', {'output_samples': 20}),
    ('configure_tetrahedral_mesh', {'minimum_steps': 6}),
])
def test_history_failure_is_not_retried_or_reported_as_atomic_success(method, settings):
    from cst_solver.simulation.frequency import FDomainConfigurationError
    calls = []
    def broken(title, code):
        calls.append(code)
        raise RuntimeError('native error after partial application')
    app = App(broken)
    app._circuit_facade = SimpleNamespace(_spec={'cached': True})
    with pytest.raises(FDomainConfigurationError) as error:
        getattr(app, method)(settings)
    assert error.value.details['history_submitted'] is None
    assert error.value.details['readback_verified'] is False
    assert len(calls) == 1
    assert app._circuit_facade._spec is None
