"""Sparse F-domain controls from the installed CST Studio Suite 2026 VBA help.

Provenance: VBA_3D/special_vbasolver/special_vbasolver_fdsolver_object.htm.
Sampling intervals append unless explicitly replaced. Configuration never
resets the solver, saves, rebuilds or solves.
"""
from collections.abc import Mapping
import math
from numbers import Integral, Real


class FDomainConfigurationError(RuntimeError):
    """A native history call failed; a command prefix may already be applied."""

    def __init__(self, code, message, **details):
        super().__init__(message)
        self.code, self.details = code, details


def _mapping(value, allowed, label):
    if not isinstance(value, Mapping) or not value:
        raise ValueError(f'{label} must be a nonempty mapping')
    if set(value) - set(allowed):
        raise ValueError(f'{label} contains unsupported keys')
    return dict(value)


def _number(value, label, *, allow_zero=False, maximum=None):
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ValueError(f'{label} must be a finite real number')
    try:
        value = float(value)
    except (OverflowError, ValueError) as exc:
        raise ValueError(f'{label} must be finite') from exc
    if not math.isfinite(value) or value < 0 or (value == 0 and not allow_zero):
        raise ValueError(f'{label} must be finite and {"nonnegative" if allow_zero else "positive"}')
    if maximum is not None and value > maximum:
        raise ValueError(f'{label} must be <= {maximum}')
    return value


def _integer(value, label, minimum=1):
    if isinstance(value, bool) or not isinstance(value, Integral):
        raise ValueError(f'{label} must be an integer')
    if not minimum <= value <= 2147483647:
        raise ValueError(f'{label} must be in [{minimum}, 2147483647]')
    return int(value)


def _boolean(value, label):
    if type(value) is not bool:
        raise ValueError(f'{label} must be boolean')
    return value


def _sequence(value, label):
    if not isinstance(value, (list, tuple)) or not value:
        raise ValueError(f'{label} must be a nonempty list')
    return value


def _enum(value, options, label):
    if not isinstance(value, str) or value not in options:
        raise ValueError(f'{label} must be one of {tuple(options)}')
    return value


def _numeric_text(value):
    return str(int(value)) if float(value).is_integer() else repr(float(value))


def normalize_fd_frequency_settings(settings):
    """Validate the complete public settings schema without accessing CST.

    Frequencies use the project's current frequency unit. Zero is allowed for
    linear/automatic interval lower bounds, but is not an actual DC solve sample.
    """
    source = _mapping(settings, (
        'sampling_intervals', 'adaptation_frequencies', 'output_samples',
        'output_spacing', 'sweep_error', 'sweep_minimum_samples',
        'sweep_error_checks', 'stop_sweep_if_converged', 'replace_intervals'), 'frequency settings')
    result = {}
    if 'replace_intervals' in source:
        result['replace_intervals'] = _boolean(source['replace_intervals'], 'replace_intervals')
    if result.get('replace_intervals') and not (
            'sampling_intervals' in source or 'adaptation_frequencies' in source):
        raise ValueError('replace_intervals=True requires sampling_intervals or adaptation_frequencies')
    if set(source) == {'replace_intervals'}:
        raise ValueError('At least one frequency control must be configured')
    if 'sampling_intervals' in source:
        intervals = []
        for item in _sequence(source['sampling_intervals'], 'sampling_intervals'):
            item = _mapping(item, ('start', 'stop', 'spacing', 'samples', 'adaptation'), 'sampling interval')
            if not {'start', 'stop', 'spacing', 'samples'} <= set(item):
                raise ValueError('Each interval requires start, stop, spacing, samples')
            adaptation = _boolean(item.get('adaptation', False), 'interval adaptation')
            spacing = _enum(item['spacing'], ('automatic', 'linear', 'logarithmic', 'single'), 'spacing')
            start = _number(item['start'], 'start', allow_zero=spacing in ('automatic', 'linear'))
            stop = _number(item['stop'], 'stop')
            if spacing == 'single':
                if start != stop or _integer(item['samples'], 'samples') != 1:
                    raise ValueError('Single intervals require equal bounds and samples=1')
                samples = 1
            else:
                if start >= stop:
                    raise ValueError('Frequency intervals require start < stop')
                if item['samples'] is None and spacing == 'automatic':
                    samples = None
                else:
                    samples = _integer(item['samples'], 'samples', 1 if spacing == 'automatic' else 2)
            intervals.append(dict(start=start, stop=stop, spacing=spacing,
                                  samples=samples, adaptation=adaptation))
        result['sampling_intervals'] = intervals
    if 'adaptation_frequencies' in source:
        result['adaptation_frequencies'] = [
            _number(value, 'adaptation frequency') for value in
            _sequence(source['adaptation_frequencies'], 'adaptation_frequencies')]
    for key in ('output_samples', 'sweep_minimum_samples', 'sweep_error_checks'):
        if key in source:
            result[key] = _integer(source[key], key, 3 if key == 'output_samples' else 1)
    if 'output_spacing' in source:
        result['output_spacing'] = _enum(source['output_spacing'],
            ('automatic', 'linear', 'logarithmic', 'log_linear'), 'output_spacing')
    if 'sweep_error' in source:
        result['sweep_error'] = _number(source['sweep_error'], 'sweep_error', maximum=1)
    if 'stop_sweep_if_converged' in source:
        result['stop_sweep_if_converged'] = _boolean(source['stop_sweep_if_converged'], 'stop_sweep_if_converged')
    return result


def normalize_fd_parallelization_settings(settings):
    """Sparse documented FDSolver CPU controls, without hardware inference."""
    source = _mapping(settings, ('enabled', 'threads', 'cpu_devices'), 'FD parallelization settings')
    result = {}
    if 'enabled' in source:
        result['enabled'] = _boolean(source['enabled'], 'enabled')
    for key in ('threads', 'cpu_devices'):
        if key in source:
            result[key] = _integer(source[key], key)
    return result


def configure_fd_parallelization(app, settings):
    requested = normalize_fd_parallelization_settings(settings)
    commands = []
    if 'enabled' in requested:
        commands.append(f'FDSolver.UseParallelization {requested["enabled"]}')
    for key, native in (('threads', 'MaxCPUs'), ('cpu_devices', 'MaximumNumberOfCPUDevices')):
        if key in requested:
            commands.append(f'FDSolver.{native} "{requested[key]}"')
    return _submit_configuration(app, requested, commands, 'Configure FD CPU parallelization',
                                 cpu_parallelization_verified=False,
                                 actual_threads=None, actual_cpu_devices=None)


def _submit_configuration(app, requested, commands, stage, *, warnings=(), **extra):
    from cst_automation.settings_history import history_caption
    code = '\n'.join(commands)
    caption = history_caption(stage, code)
    report = dict(requested=requested, native_commands=commands,
                  history_caption=caption,
                  scope='current_project_model3d', history_submitted=False,
                  readback=None, readback_status='unsupported',
                  readback_verified=False, mesh_verified=False,
                  sampling_verified=False, solver_verified=False,
                  warnings=list(warnings), **extra)
    try:
        submit = getattr(app.cst_file.model3d, 'add_to_history', None)
        if not callable(submit):
            raise RuntimeError('Current project has no model3d history interface')
    except Exception as exc:
        raise FDomainConfigurationError('fd_configuration_unavailable', str(exc),
                                       stage=stage, **report) from exc
    try:
        facade = getattr(app, '_circuit_facade', None)
        if facade is not None:
            facade._spec = None
        submit(caption, code)
    except Exception as exc:
        report['history_submitted'] = None
        raise FDomainConfigurationError('fd_configuration_partial', str(exc),
                                       stage=stage, **report) from exc
    report['history_submitted'] = True
    return report


def configure_fd_frequency(app, settings):
    requested = normalize_fd_frequency_settings(settings)
    commands, warnings = [], []
    if requested.get('replace_intervals'):
        # Explicitly replace interval definitions only, never reset FDSolver.
        commands.append('FDSolver.ResetSampleIntervals "all"')
    elif 'sampling_intervals' in requested or 'adaptation_frequencies' in requested:
        warnings.append('Sample intervals append; inherited intervals are not replaced or read back.')
    spacing_names = dict(automatic='Automatic', linear='Equidistant', logarithmic='Logarithmic', single='Single')
    for item in requested.get('sampling_intervals', ()):
        samples = '' if item['samples'] is None else str(item['samples'])
        commands.append('FDSolver.AddSampleInterval '
                        f'"{_numeric_text(item["start"])}", "{_numeric_text(item["stop"])}", '
                        f'"{samples}", "{spacing_names[item["spacing"]]}", {item["adaptation"]}')
        if item['start'] == 0:
            warnings.append('CST ignores the zero Equidistant sample or replaces the zero Automatic lower limit; this does not request a DC solve.')
    for value in requested.get('adaptation_frequencies', ()):
        text = _numeric_text(value)
        commands.append(f'FDSolver.AddSampleInterval "{text}", "{text}", "1", "Single", True')
    if 'output_samples' in requested:
        commands.append(f'FDSolver.SetNumberOfResultDataSamples "{requested["output_samples"]}"')
    if 'output_spacing' in requested:
        names = dict(automatic='Automatic', linear='Frequency (linear)',
                     logarithmic='Frequency (logarithmic)', log_linear='Frequency (log-linear)')
        commands.append(f'FDSolver.SetResultDataSamplingMode "{names[requested["output_spacing"]]}"')
    if 'sweep_error' in requested:
        commands.append(f'FDSolver.SetSweepThreshold "S-Parameters", "{_numeric_text(requested["sweep_error"])}"')
    for key, native in (('sweep_minimum_samples', 'SweepMinimumSamples'),
                        ('sweep_error_checks', 'SweepErrorChecks')):
        if key in requested:
            commands.append(f'FDSolver.{native} "{requested[key]}"')
    if 'stop_sweep_if_converged' in requested:
        commands.append(f'FDSolver.SetStopSweepIfCriterionMet {requested["stop_sweep_if_converged"]}')
    return _submit_configuration(app, requested, commands, 'Configure FD frequency',
                                 warnings=warnings,
                                 interval_update='replace_all' if requested.get('replace_intervals') else 'append')
