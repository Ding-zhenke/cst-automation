"""History-only EM time controls. No inferred native readback or solver proof."""
from cst_automation.em_time import normalize_em_time_settings


class EMTimeConfigurationError(RuntimeError):
    def __init__(self, code, message, **details):
        super().__init__(message)
        self.code, self.details = code, details


def configure_em_time_settings(app, settings):
    requested = normalize_em_time_settings(settings)
    commands = []
    if 'stability_factor' in requested:
        commands.append('Solver.TimeStepStabilityFactor ' + format(requested['stability_factor'], '.17g'))
    if 'output_sampling' in requested:
        commands.append('Solver.AutomaticTimeSignalSampling ' +
                        ('False' if requested['output_sampling'] == 'every_step' else 'True'))
    report = {
        'requested': requested, 'native_commands': commands, 'scope': 'current_project_model3d',
        'history_submitted': False, 'readback': None, 'readback_status': 'unsupported',
        'readback_verified': False, 'internal_time_step_verified': False,
        'output_sampling_verified': False, 'solver_verified': False,
    }
    try:
        model = app.cst_file.model3d
        submit = getattr(model, 'add_to_history', None)
        if not callable(submit):
            raise RuntimeError('Current project has no model3d history interface')
    except Exception as exc:
        raise EMTimeConfigurationError('em_time_unavailable', str(exc),
                                       stage='configure_em_time_settings', **report) from exc
    try:
        # Cache invalidation is local only; do not instantiate a DS facade for an EM operation.
        facade = getattr(app, '_circuit_facade', None)
        if facade is not None:
            facade._spec = None
        submit('Configure EM time settings', '\n'.join(commands))
    except Exception as exc:
        # A multi-command history failure may have applied a prefix. No rollback/retry.
        report['history_submitted'] = None
        raise EMTimeConfigurationError('em_time_configuration_partial', str(exc),
                                       stage='configure_em_time_settings', **report) from exc
    report['history_submitted'] = True
    return report
