"""Shared, SDK-free checks for configuration inputs and file snapshots."""
import hashlib
from pathlib import Path

from .circuit_schema import CircuitSpecError, evaluate_quantity


def require(ok, message):
    if not ok:
        raise CircuitSpecError(message)


def configuration_name(name):
    require(isinstance(name, str) and bool(name.strip()) and not any(c in name for c in '\r\n\x00'),
            'Explicit nonempty name without control characters required')
    return name


def quantity(data, dimension, *, minimum=0, strict=False):
    require(isinstance(data, dict) and set(data) == {'value', 'unit'}, 'Quantity requires value/unit')
    number, dims = evaluate_quantity(data['value'], data['unit'], {})
    require(dims == {dimension: 1}, f'Expected {dimension} quantity')
    if minimum is not None:
        require(number > minimum if strict else number >= minimum, f'Quantity outside allowed {dimension} range')
    return number


def file_snapshot(filename):
    require(isinstance(filename, str) and filename.strip() and '\x00' not in filename, 'Explicit file path required')
    path = Path(filename).resolve()
    require(path.is_file(), f'Model or waveform file missing: {path}')
    try:
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError as exc:
        raise CircuitSpecError(f'Cannot read configuration file: {path}') from exc
    return {'path': str(path), 'sha256': digest, 'scope': 'configuration_snapshot'}
