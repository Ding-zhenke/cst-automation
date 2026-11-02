"""Pure validation for current-project EM transient time controls."""
import math


def normalize_em_time_settings(settings):
    """Return detached settings; no SDK, project, or unit-system access."""
    if not isinstance(settings, dict) or not settings:
        raise ValueError('EM time settings must be a nonempty mapping')
    if set(settings) - {'stability_factor', 'output_sampling'}:
        raise ValueError('Unknown EM time settings')
    result = {}
    if 'stability_factor' in settings:
        factor = settings['stability_factor']
        if type(factor) not in (float, int) or not 0 < factor <= 1 or not math.isfinite(factor):
            raise ValueError('stability_factor must be a finite number in (0, 1]')
        result['stability_factor'] = float(factor)
    if 'output_sampling' in settings:
        sampling = settings['output_sampling']
        if sampling not in ('every_step', 'automatic'):
            raise ValueError('output_sampling must be every_step or automatic')
        result['output_sampling'] = sampling
    return result
