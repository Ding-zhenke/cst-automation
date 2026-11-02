"""Native writes for reusable source/model settings, separate from execution."""
import math
from pathlib import Path

from cst_automation.circuit_schema import unit_info
from cst_automation.circuit_configuration import file_snapshot
from .adapter import CircuitError, iterate


def matches_number(actual, expected):
    value = float(actual)
    return math.isfinite(value) and math.isclose(value, expected, rel_tol=1e-10, abs_tol=0.)


def check_files(files):
    for source in files:
        if file_snapshot(source['path'])['sha256'] != source['sha256']:
            raise CircuitError('circuit_spec_invalid', 'Configuration source changed during preparation', path=source['path'])


def configure_task_ports(adapter, name, settings):
    task = adapter.select('SimulationTask', name)
    if not task.DoesExist() or str(task.GetTypeForTask(name)).lower() != 'transient':
        raise CircuitError('circuit_topology_invalid', 'Existing transient task required', task_name=name)
    ports = set(iterate(adapter.schematic.ExternalPort, 'StartPortNameIteration', 'GetNextPortName'))
    if not set(settings['ports']) <= ports:
        raise CircuitError('circuit_topology_invalid', 'Unknown external port', ports=sorted(set(settings['ports']) - ports))
    check_files(settings['files'])
    dimensions = set()
    for row in settings['ports'].values():
        if row.get('signal_type') == 'Sine':
            dimensions.update(('Time', 'Frequency', 'Voltage' if row['source_type'] == 'Voltage' else 'Current'))
        if 'resistance_si' in row or 'impedance_si' in row:
            dimensions.add('Resistance')
    units = {d: str(adapter.schematic.Units.GetUnit(d)) for d in dimensions}
    factors = {}
    for dimension, unit in units.items():
        actual, factor = unit_info(unit)
        if actual != dimension:
            raise CircuitError('circuit_result_read_failed', 'Wrong native source unit', dimension=dimension)
        factors[dimension] = factor
    readback = {}
    try:
        for port, row in settings['ports'].items():
            if row['source_type'] == 'None':
                task.SetPortSourceType(port, 'None')
                task.SetConstPortImpedance(port, *(format(v / factors['Resistance'], '.17g') for v in row['impedance_si']))
            else:
                if row['signal_type'] == 'Import':
                    values = [row['file'], str(row['periodic']).lower()]
                else:
                    data = row['signal_si']
                    dim = 'Voltage' if row['source_type'] == 'Voltage' else 'Current'
                    values = [format(v / factors[d], '.17g') for v, d in (
                        (data['offset'], dim), (data['amplitude'], dim),
                        (data['frequency'], 'Frequency'), (data['delay'], 'Time'))]
                task.SetPortSignal(port, row['signal_type'], values)
                task.SetPortSourceType(port, row['source_type'])
                if 'resistance_si' in row:
                    task.SetPortInnerResistance(port, format(row['resistance_si'] / factors['Resistance'], '.17g'))
            actual = {'source_type': str(task.GetPortSourceType(port)),
                      'signal_parameters_readback': 'unsupported', 'impedance_readback': 'unsupported'}
            if actual['source_type'].casefold() != row['source_type'].casefold():
                raise RuntimeError(f'Native source type mismatch for {port}')
            if row['source_type'] != 'None':
                actual['signal_type'] = str(task.GetPortSignalType(port))
                if actual['signal_type'].casefold() != row['signal_type'].casefold():
                    raise RuntimeError(f'Native signal type mismatch for {port}')
            if 'resistance_si' in row:
                actual['resistance'] = str(task.GetPortInnerResistance(port))
                if not matches_number(actual['resistance'], row['resistance_si'] / factors['Resistance']):
                    raise RuntimeError(f'Native source resistance mismatch for {port}')
            readback[port] = actual
        if any(str(adapter.schematic.Units.GetUnit(d)) != unit for d, unit in units.items()):
            raise RuntimeError('Native units changed during port configuration')
        check_files(settings['files'])
    except Exception as exc:
        raise CircuitError('circuit_build_partial', f'Port configuration write/readback failed: {exc}',
                           stage='configure_task_ports', task_name=name, requested=settings, readback=readback) from exc
    return {'task_name': name, 'requested': settings, 'ports': readback, 'readback': readback, 'units': units,
            'files': settings['files'], 'readback_verified': False, 'solver_verified': False}


def configure_nonlinear_model(adapter, name, settings, *, create=False):
    obj = adapter.select('Block', name)
    exists = bool(obj.DoesExist())
    if create == exists:
        raise CircuitError('circuit_topology_invalid', 'Model creation conflict or missing existing block', block_name=name)
    expected_types = ('diode',) if settings['kind'] == 'berkeley_diode' else ('spice', 'spice block', 'spice file block')
    if exists and str(obj.GetTypeName()).rsplit('\\', 1)[-1].lower() not in expected_types:
        raise CircuitError('circuit_topology_invalid', 'Block type is incompatible with requested model', block_name=name)
    check_files(settings['files'])
    before_pins = adapter.pins(name) if exists else []
    if exists and settings['kind'] == 'berkeley_diode':
        # Re-selecting Model Type can reset native values. Require a readable
        # compatible model and update only the requested parameters in-place.
        adapter.diode_readback(name)
    actual = None
    try:
        if create:
            obj.Type(settings['type']); obj.Name(name)
            if settings['kind'] == 'spice':
                obj.SetFile(settings['file'])
            obj.Create()
        if settings['kind'] == 'berkeley_diode':
            props = {k: v for k, v in settings['properties'].items() if create or k != 'Model Type'}
            adapter.properties(name, props, settings['property_units'])
            actual = adapter.diode_readback(name)
            for key, expected in settings['properties'].items():
                if key == 'Model Type':
                    continue
                unit = actual['property_metadata'][key]['unit']
                dimension, factor = unit_info(unit or '1')
                if dimension != unit_info(settings['property_units'][key])[0]:
                    raise RuntimeError(f'Native diode unit mismatch for {key}')
                if not matches_number(float(actual['properties'][key]) * factor, expected):
                    raise RuntimeError(f'Native diode parameter mismatch for {key}')
        else:
            obj = adapter.select('Block', name)
            if not create:
                obj.SetFile(settings['file'])
            if settings['spice_filter'] is not None:
                obj.SetSpiceFilter(settings['spice_filter'])
            obj.SetSpiceModel(settings['spice_model'])
            actual = adapter.spice_readback(name)
            actual['file'] = str(adapter.select('Block', name).GetFile())
            if Path(actual['file']).resolve() != Path(settings['file']) or actual['spice_model'] != settings['spice_model']:
                raise RuntimeError('Native SPICE file/model mismatch')
            if settings['spice_filter'] is not None and actual['spice_filter'].casefold() != settings['spice_filter'].casefold():
                raise RuntimeError('Native SPICE dialect mismatch')
        after_pins = adapter.pins(name)
        check_files(settings['files'])
    except Exception as exc:
        raise CircuitError('circuit_build_partial', f'Model configuration write/readback failed: {exc}',
                           stage='configure_nonlinear_model', block_name=name, requested=settings, readback=actual) from exc
    return {'block_name': name, 'created': create, 'requested': settings, 'readback': actual,
            'pins_before': before_pins, 'pins_after': after_pins, 'pins_changed': before_pins != after_pins,
            'files': settings['files'], 'readback_verified': False, 'solver_verified': False}
