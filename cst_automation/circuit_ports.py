"""Unit-explicit source and termination profiles, with SI waveform files."""
import copy
import csv
import math

from .circuit_configuration import require, configuration_name, quantity, file_snapshot
from .circuit_schema import CircuitSpecError


def task_port_settings(ports):
    require(isinstance(ports, dict) and bool(ports), 'Nonempty ports mapping required')
    result, files = {}, []
    for name, data in ports.items():
        configuration_name(name)
        require(isinstance(data, dict) and not set(data) - {'source_type', 'signal', 'resistance', 'impedance'}, 'Unknown port settings')
        kind = data.get('source_type')
        require(kind in ('voltage', 'current', 'none'), 'Source type must be voltage/current/none')
        row = {'source_type': kind.title()}
        if kind == 'none':
            require('signal' not in data and 'resistance' not in data, 'Termination cannot have an excitation')
            impedance = data.get('impedance')
            require(isinstance(impedance, dict) and set(impedance) <= {'real', 'imag'} and 'real' in impedance,
                    'Termination needs real and optional imaginary impedance')
            row['impedance_si'] = [quantity(impedance['real'], 'Resistance'),
                quantity(impedance['imag'], 'Resistance', minimum=None) if 'imag' in impedance else 0.]
        else:
            require('impedance' not in data, 'Excited ports cannot use termination impedance')
            if 'resistance' in data:
                require(kind == 'voltage', 'Inner resistance is only supported for voltage sources')
                row['resistance_si'] = quantity(data['resistance'], 'Resistance')
            signal = data.get('signal')
            require(isinstance(signal, dict), 'Excited port needs signal settings')
            stype = signal.get('type')
            require(stype in ('sine', 'import'), 'Signal type must be sine/import')
            row['signal_type'] = stype.title()
            if stype == 'sine':
                require(not set(signal) - {'type', 'amplitude', 'offset', 'frequency', 'delay'}, 'Unknown sine settings')
                dim = 'Voltage' if kind == 'voltage' else 'Current'
                row['signal_si'] = {
                    'amplitude': quantity(signal.get('amplitude'), dim),
                    'offset': quantity(signal['offset'], dim, minimum=None) if 'offset' in signal else 0.,
                    'frequency': quantity(signal.get('frequency'), 'Frequency', strict=True),
                    'delay': quantity(signal['delay'], 'Time') if 'delay' in signal else 0.}
            else:
                require(not set(signal) - {'type', 'file', 'periodic'}, 'Unknown imported signal settings')
                periodic = signal.get('periodic', False)
                require(type(periodic) is bool, 'Periodic must be boolean')
                source = file_snapshot(signal.get('file'))
                previous, count = None, 0
                try:
                    with open(source['path'], encoding='utf-8-sig', newline='') as handle:
                        for values in csv.reader(handle):
                            require(len(values) == 2, 'Imported waveform requires two CSV columns')
                            time, amplitude = map(float, values)
                            require(math.isfinite(time) and math.isfinite(amplitude) and time >= 0,
                                    'Waveform time/amplitude must be finite and time nonnegative')
                            require(previous is None or time > previous, 'Waveform time must strictly increase')
                            previous, count = time, count + 1
                except (OSError, UnicodeError, ValueError) as exc:
                    raise CircuitSpecError(f'Invalid imported waveform: {exc}') from exc
                require(count >= 2, 'Imported waveform requires at least two samples')
                row.update(file=source['path'], periodic=periodic)
                files.append({**source, 'time_unit': 's', 'amplitude_unit': 'V' if kind == 'voltage' else 'A'})
        result[name] = row
    return {'ports': copy.deepcopy(result), 'files': files}
