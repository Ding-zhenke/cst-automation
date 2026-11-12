"""Bounded native S-parameter task configuration; this module never solves."""
import math

from .adapter import CircuitError, iterate


def inspect_existing_linear_sp(schematic, task_name, ports):
    """Read supported task getters; no configuration, execution, or connection."""
    if (not isinstance(task_name, str) or not task_name.strip() or
            any(c in task_name for c in '\r\n\x00') or not isinstance(ports, list) or
            not 1 <= len(ports) <= 128 or any(not isinstance(p, str) or not p.strip() or
            any(c in p for c in '\r\n\x00') for p in ports) or len(set(ports)) != len(ports)):
        raise ValueError('Explicit task and unique bounded port names required')
    actual_ports = list(iterate(schematic.ExternalPort, 'StartPortNameIteration', 'GetNextPortName'))
    if len(set(actual_ports)) != len(actual_ports) or set(actual_ports) != set(ports):
        raise ValueError('Native external ports differ from requested inventory')
    task = schematic.SimulationTask
    task.Reset(); task.Name(task_name)
    if not task.DoesExist() or str(task.GetTypeForTask(task_name)).casefold() != 's-parameters':
        raise ValueError('Requested task is not an existing S-parameters task')
    properties = {key: str(task.GetProperty(key)) for key in
                  ('maximum frequency range', 'circuit simulator', 'broadband sweep',
                   'logarithmic sweep', 'fmin', 'fmax')}
    modes = {name: {'impedance_type': str(task.GetPortImpedanceType(name)),
                    'source_type': 'unsupported'} for name in ports}
    return {'task_name': task_name, 'properties': properties, 'ports': modes,
            'frequency_unit': str(task.GetUnit('Frequency')), 'resistance_unit': str(task.GetUnit('Resistance')),
            'sample_count_readback': 'unsupported', 'port_impedances_readback': 'unsupported',
            'zero_external_sources_verified': False, 'schematic_identity_verified': False,
            'native_bridge_verified': False, 'solver_verified': False}


def complete_existing_linear_sp_task(schematic, task_name, *, expected, frequency_unit,
                                     fmin, fmax, samples, port_impedances):
    """Complete a reviewed existing task only; caller owns the session fence."""
    if (not isinstance(port_impedances, dict) or not port_impedances
            or frequency_unit not in ('Hz', 'kHz', 'MHz', 'GHz')
            or any(type(v) not in (int, float) or not math.isfinite(v) for v in (fmin, fmax))
            or not 0 <= fmin < fmax or type(samples) is not int or not 2 <= samples <= 100000
            or any(not isinstance(k, str) or not k or type(v) not in (int, float)
                   or not math.isfinite(v) or v <= 0 for k, v in port_impedances.items())):
        raise ValueError('Explicit task settings required')
    before = inspect_existing_linear_sp(schematic, task_name, list(port_impedances))
    if before != expected:
        raise ValueError('Native task changed after review')
    if (before['frequency_unit'] != frequency_unit or before['resistance_unit'] != 'Ohm'
            or before['properties']['circuit simulator'].casefold() != 'cst'):
        raise ValueError('Reviewed units or simulator differ')
    task = schematic.SimulationTask
    task.Reset(); task.Name(task_name)
    completed, unchanged, stage, attempted = [], [], 'set_maximum_frequency_range', None
    def write(stage_name, fn, *args):
        nonlocal stage, attempted
        stage = stage_name
        attempted = {'stage': stage_name, 'arguments': list(args)}
        fn(*args)
        completed.append(attempted)
    def set_false_if_needed(key, stage_name):
        nonlocal stage, attempted
        stage, attempted = 'read_' + stage_name, None
        actual = str(task.GetProperty(key))
        if actual.casefold() == 'false':
            unchanged.append({'property': key, 'native_value': actual})
        else:
            write(stage_name, task.SetProperty, key, 'False')
    try:
        set_false_if_needed('maximum frequency range', 'set_maximum_frequency_range')
        set_false_if_needed('broadband sweep', 'set_broadband_sweep')
        write('set_sweep_data', task.SetSweepData, format(fmin, '.17g'), format(fmax, '.17g'), str(samples))
        set_false_if_needed('logarithmic sweep', 'set_logarithmic_sweep')
        for name, value in port_impedances.items():
            write('set_port_impedance:' + name, task.SetConstPortImpedance, name, format(value, '.17g'), '0')
        stage = 'read_task_settings'
        attempted = None
        after = inspect_existing_linear_sp(schematic, task_name, list(port_impedances))
        props = after['properties']
        if (after['frequency_unit'] != frequency_unit or after['resistance_unit'] != 'Ohm'
                or props['circuit simulator'].casefold() != 'cst'
                or any(props[k].casefold() != 'false' for k in ('maximum frequency range', 'broadband sweep', 'logarithmic sweep'))
                or not math.isclose(float(props['fmin']), fmin, rel_tol=1e-10, abs_tol=0)
                or not math.isclose(float(props['fmax']), fmax, rel_tol=1e-10, abs_tol=0)
                or any(v['impedance_type'].casefold() != 'constant' for v in after['ports'].values())):
            raise ValueError('Native task readback differs')
    except Exception as exc:
        raise CircuitError('circuit_build_partial', 'Existing S-parameter task may be partially updated',
                           failure_stage=stage, original_type=type(exc).__name__, original_message=str(exc),
                           attempted=attempted, completed=completed, unchanged=unchanged) from exc
    return {'before': before, 'after': after, 'completed': completed, 'unchanged': unchanged, 'solver_verified': False}


def configure_linear_sp_task(schematic, task_name, *, frequency_unit, fmin, fmax,
                             samples, port_impedances):
    if (not isinstance(task_name, str) or not task_name.strip()
            or any(c in task_name for c in '\r\n\x00\\')
            or frequency_unit not in ('Hz', 'kHz', 'MHz', 'GHz')
            or any(type(v) not in (int, float) or not math.isfinite(v) for v in (fmin, fmax))
            or fmin < 0 or fmax <= fmin or type(samples) is not int or not 2 <= samples <= 100000
            or not isinstance(port_impedances, dict) or not port_impedances):
        raise ValueError('Explicit task, frequency range, unit, sample count and ports required')
    for name, impedance in port_impedances.items():
        if (not isinstance(name, str) or not name.strip() or any(c in name for c in '\r\n\x00')
                or type(impedance) not in (int, float) or not math.isfinite(impedance) or impedance <= 0):
            raise ValueError('Port names and finite positive real impedances required')
    ports = list(iterate(schematic.ExternalPort, 'StartPortNameIteration', 'GetNextPortName'))
    if len(ports) != len(set(ports)) or set(port_impedances) != set(ports):
        raise ValueError('Every existing external port needs an explicit impedance')
    task = schematic.SimulationTask
    task.Reset(); task.Name(task_name)
    if task.DoesExist():
        raise ValueError('Task already exists; refusing overwrite')
    stage = 'create_task'
    try:
        task.Type('S-Parameters'); task.Name(task_name); task.Create()
        stage = 'set_frequency_unit'
        task.SetLocalUnit('Frequency', frequency_unit)
        stage = 'set_resistance_unit'
        task.SetLocalUnit('Resistance', 'Ohm')
        stage = 'set_maximum_frequency_range'
        task.SetProperty('maximum frequency range', 'False')
        stage = 'set_circuit_simulator'
        task.SetProperty('circuit simulator', 'cst')
        stage = 'set_broadband_sweep'
        task.SetProperty('broadband sweep', 'False')
        stage = 'set_sweep_data'
        task.SetSweepData(format(fmin, '.17g'), format(fmax, '.17g'), str(samples))
        stage = 'set_logarithmic_sweep'
        task.SetProperty('logarithmic sweep', 'False')
        for name, impedance in port_impedances.items():
            stage = 'set_port_impedance:' + name
            task.SetConstPortImpedance(name, format(impedance, '.17g'), '0')
        stage = 'read_task_settings'
        actual_type = str(task.GetTypeForTask(task_name)).casefold()
        frequency_unit_actual = str(task.GetUnit('Frequency'))
        resistance_unit_actual = str(task.GetUnit('Resistance'))
        port_modes = {name: {'impedance_type': str(task.GetPortImpedanceType(name)),
                             'source_type': 'unsupported'} for name in port_impedances}
        actual = {key: str(task.GetProperty(key)) for key in ('maximum frequency range', 'circuit simulator',
                  'broadband sweep', 'logarithmic sweep', 'fmin', 'fmax')}
        if (actual_type != 's-parameters' or frequency_unit_actual != frequency_unit
                or resistance_unit_actual != 'Ohm' or actual['circuit simulator'].casefold() != 'cst'
                or any(row['impedance_type'].casefold() != 'constant' for row in port_modes.values())
                or any(actual[k].casefold() != 'false' for k in ('maximum frequency range', 'broadband sweep', 'logarithmic sweep'))
                or not math.isclose(float(actual['fmin']), fmin, rel_tol=1e-10, abs_tol=0)
                or not math.isclose(float(actual['fmax']), fmax, rel_tol=1e-10, abs_tol=0)):
            raise ValueError('Native task readback differs')
    except Exception as exc:
        raise CircuitError('circuit_build_partial', 'S-parameter task may be partially created', task_name=task_name,
                           failure_stage=stage, original_type=type(exc).__name__, original_message=str(exc)) from exc
    return {'task_name': task_name, 'properties_readback': actual, 'frequency_unit_requested': frequency_unit,
            'resistance_unit_requested': 'Ohm',
            'frequency_unit_readback': frequency_unit_actual, 'resistance_unit_readback': resistance_unit_actual,
            'port_modes': port_modes,
            'sample_count_readback': 'unsupported',
            'port_impedances_readback': 'unsupported', 'solver_verified': False}
