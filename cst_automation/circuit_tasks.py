"""Unit-explicit common transient settings. Pure data; never loads CST."""
import copy
import math

from .circuit_schema import CircuitSpecError, evaluate_quantity


def transient_settings(settings):
    def require(ok, message):
        if not ok:
            raise CircuitSpecError(message)

    def quantity(data, dimension):
        require(isinstance(data, dict) and set(data) == {'value', 'unit'}, 'Quantity needs only value/unit')
        number, dims = evaluate_quantity(data['value'], data['unit'], {})
        require(dims == {dimension: 1} and number > 0, f'Positive {dimension} quantity required')
        return number

    require(isinstance(settings, dict), 'Transient settings must be a mapping')
    require(not set(settings) - {'mode', 'duration', 'sampling', 'integration', 'max_frequency', 'accuracy'}, 'Unknown transient settings')
    require(settings.get('mode') in ('network', 'transient_cosim'), 'Explicit transient mode required')
    duration = quantity(settings.get('duration'), 'Time')
    sampling = settings.get('sampling', {})
    require(isinstance(sampling, dict) and not set(sampling) - {'method', 'points'}, 'Invalid sampling settings')
    method, points = sampling.get('method', 'simulated'), sampling.get('points', 1001)
    require(method in ('simulated', 'manual'), 'Sampling method must be simulated/manual')
    require(type(points) is int and 2 <= points <= 10000000, 'Sampling points must be integer 2..10000000')
    result = {'mode': settings['mode'], 'duration_si': duration,
              'sampling_method': 'Simulated' if method == 'simulated' else 'Manual', 'output_points': points}
    integration = settings.get('integration', {})
    require(isinstance(integration, dict) and not set(integration) - {
        'time_step', 'auto_solver', 'stepping', 'minimum_time_step', 'method', 'order'}, 'Invalid integration settings')
    stepping = integration.get('stepping', 'fixed' if 'time_step' in integration else None)
    require(stepping is None or stepping in ('automatic', 'adaptive', 'fixed'), 'Invalid time stepping mode')
    if stepping is not None:
        result['time_stepping'] = stepping
    require(stepping != 'automatic' or not {'time_step', 'minimum_time_step'} & set(integration),
            'Automatic stepping cannot have explicit time steps')
    if 'time_step' in integration:
        step = quantity(integration['time_step'], 'Time')
        require(step <= duration, 'Requested time step exceeds duration')
        result['requested_time_step_si'] = step
    if 'minimum_time_step' in integration:
        require(stepping == 'adaptive' and 'time_step' in integration, 'Minimum step requires adaptive maximum step')
        minimum = quantity(integration['minimum_time_step'], 'Time')
        require(minimum <= result['requested_time_step_si'], 'Minimum step exceeds maximum step')
        result['minimum_time_step_si'] = minimum
    if 'method' in integration:
        require(integration['method'] in ('adams', 'gear'), 'Integration method must be adams/gear')
        result['integration_method'] = integration['method']
    if 'order' in integration:
        require(type(integration['order']) is int and 1 <= integration['order'] <= 4, 'Integration order must be integer 1..4')
        result['integration_order'] = integration['order']
    if 'auto_solver' in integration:
        require(type(integration['auto_solver']) is bool, 'auto_solver must be boolean')
        result['auto_solver'] = integration['auto_solver']
    if 'max_frequency' in settings:
        result['max_frequency_si'] = quantity(settings['max_frequency'], 'Frequency')
    if 'accuracy' in settings:
        value = settings['accuracy']
        require(type(value) in (float, int) and math.isfinite(value) and 0 < value < 1, 'Accuracy must be finite and between 0 and 1')
        result['accuracy'] = value
    return copy.deepcopy(result)
