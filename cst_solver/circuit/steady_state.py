"""Documented CST transient-shooting properties, without save or solve calls."""
import math

from cst_automation.circuit_schema import unit_info
from .adapter import CircuitError


def configure_steady_state_task(adapter, name, settings, *, create=False):
    task = adapter.select('SimulationTask', name)
    exists = bool(task.DoesExist())
    if create and exists:
        raise CircuitError('circuit_topology_invalid', 'Task name conflict; refusing overwrite', task_name=name)
    if not create and (not exists or str(task.GetTypeForTask(name)).lower() != 'transient'):
        raise CircuitError('circuit_topology_invalid', 'An existing transient task is required', task_name=name)
    properties = {'circuit simulator': 'cst - steady state',
                  'steady state period detection': 'true' if settings['automatic_period'] else 'false'}
    units = {}
    numeric = set()
    if 'period_si' in settings:
        # Existing tasks may use local units that differ from project units.
        unit = str(adapter.schematic.Units.GetUnit('Time') if create else task.GetUnit('Time'))
        try:
            dimension, factor = unit_info(unit)
        except ValueError as exc:
            raise CircuitError('circuit_result_read_failed', 'Native time unit is unknown', task_name=name) from exc
        if dimension != 'Time':
            raise CircuitError('circuit_result_read_failed', 'Native time unit has wrong dimension', task_name=name)
        period = settings['period_si'] / factor
        if not math.isfinite(period) or period <= 0:
            raise CircuitError('circuit_spec_invalid', 'Period cannot be represented in task units', task_name=name)
        units['Time'] = unit
        properties['steady state period'] = format(period, '.17g')
        numeric.add('steady state period')
    if 'tolerance' in settings:
        properties['steady state tolerance'] = format(settings['tolerance'], '.17g')
        numeric.add('steady state tolerance')
    try:
        if create:
            task.Reset(); task.Type('transient'); task.Name(name); task.Create()
        for key, value in properties.items():
            task.SetProperty(key, value)
        actual = {key: str(task.GetProperty(key)) for key in properties}
        for key, expected in properties.items():
            if key in numeric:
                value = float(actual[key])
                valid = math.isfinite(value) and value > 0 and math.isclose(value, float(expected), rel_tol=1e-10, abs_tol=0.)
            else:
                valid = actual[key].casefold() == expected.casefold()
            if not valid:
                raise RuntimeError('Native steady-state property mismatch: ' + key)
        if units and str(task.GetUnit('Time')) != units['Time']:
            raise RuntimeError('Native task time unit changed during configuration')
    except Exception as exc:
        raise CircuitError('circuit_build_partial', 'Steady-state configuration write/readback failed: ' + str(exc),
                           stage='configure_steady_state_task', task_name=name, requested=settings) from exc
    return {'task_name': name, 'created': create, 'analysis': 'steady_state_shooting',
            'readback': {'properties': actual, 'units': units},
            'requested_period_si': settings.get('period_si'),
            'period_commensurability_verified': False, 'steady_state_convergence_verified': False,
            'internal_time_step_verified': False, 'readback_verified': False, 'solver_verified': False}
