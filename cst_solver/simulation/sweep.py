"""Pure validation and official CST commands for parameter sweep definitions."""
import math
import re
from typing import Dict, List, Literal, Tuple, TypedDict, Union

from cst_solver.expressions import validate_parameter_name


SweepNumber = Union[int, float]


class SweepRange(TypedDict):
    """A native, endpoint-inclusive range; samples counts points, not intervals."""

    mode: Literal['linear', 'logarithmic']
    start: SweepNumber
    stop: SweepNumber
    samples: int


SweepAxis = Union[List[SweepNumber], Tuple[SweepNumber, ...], SweepRange]
SweepParameters = Dict[str, SweepAxis]
MAX_SWEEP_AXES = 100
MAX_SWEEP_SAMPLES = 10000
MAX_SWEEP_CASES = 1000000
_NUMERIC_LITERAL = re.compile(r'[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?\Z')


def validate_sequence_name(sequence: str) -> None:
    """Reject empty or unsafe VBA string literals without changing valid names."""
    if (not isinstance(sequence, str) or not sequence.strip() or len(sequence) > 128
            or any(c == '"' or ord(c) < 32 or ord(c) == 127 for c in sequence)):
        raise ValueError('Invalid sweep sequence name')


def _names(sequence, parameter):
    validate_sequence_name(sequence)
    validate_parameter_name(parameter)


def _finite_number(value):
    if type(value) not in (int, float):
        return False
    try:
        return math.isfinite(value)
    except OverflowError:
        return False


def points_command(sequence, parameter, points):
    _names(sequence, parameter)
    if not isinstance(points, (list, tuple)) or not 1 <= len(points) <= MAX_SWEEP_SAMPLES:
        raise ValueError('A nonempty bounded list of numeric points is required')
    if any(not _finite_number(p) for p in points):
        raise ValueError('Sweep points must be finite numbers, not expressions or booleans')
    values = ';'.join(str(p) for p in points)
    return f'     .AddParameter_ArbitraryPoints "{sequence}", "{parameter}", "{values}"'


def discrete_sweep_code(sequence, parameters, replace_all=False):
    """Retain the legacy point-list-only contract and the same case budget."""
    return _sweep_code(sequence, parameters, replace_all, discrete_only=True)

def samples_command(sequence, parameter, lower, upper, count, logarithmic=False,
                    *, allow_numeric_strings=False):
    """Validate a native sampled range without touching a project."""
    _names(sequence, parameter)
    if type(logarithmic) is not bool:
        raise ValueError('logarithmic must be boolean')
    if allow_numeric_strings:
        lower, upper = (_legacy_bound(v) for v in (lower, upper))
    if any(not _finite_number(v) for v in (lower, upper)):
        raise ValueError('Sweep bounds must be finite numeric values')
    if lower >= upper:
        raise ValueError('Sweep start must be less than stop')
    if type(count) is not int or not 2 <= count <= MAX_SWEEP_SAMPLES:
        raise ValueError('Sweep samples must be an integer in [2, 10000]')
    if logarithmic and lower <= 0:
        raise ValueError('Logarithmic sweep bounds must be positive; use a separate discrete point for zero')
    return (f'     .AddParameter_Samples "{sequence}", "{parameter}", '
            f'"{lower}", "{upper}", "{count}", "{logarithmic}"')


def _legacy_bound(value):
    """Normalize safe historical numeric strings, never CST/VBA expressions."""
    if isinstance(value, str):
        if not _NUMERIC_LITERAL.fullmatch(value):
            raise ValueError('Sweep bounds must be finite numeric literals')
        return float(value)
    return value


def sweep_code(sequence: str, parameters: SweepParameters, replace_all: bool = False) -> str:
    """Build a mixed sweep only after every axis has passed validation."""
    return _sweep_code(sequence, parameters, replace_all, discrete_only=False)


def _sweep_code(sequence, parameters, replace_all, *, discrete_only):
    if type(replace_all) is not bool:
        raise ValueError('replace_all must be boolean')
    if not isinstance(parameters, dict) or not 1 <= len(parameters) <= MAX_SWEEP_AXES:
        raise ValueError('A bounded nonempty parameter mapping is required')
    commands = []
    cases = 1
    for parameter, axis in parameters.items():
        if isinstance(axis, dict) and not discrete_only:
            if set(axis) != {'mode', 'start', 'stop', 'samples'}:
                raise ValueError('A range needs exactly mode, start, stop and samples')
            if axis['mode'] not in ('linear', 'logarithmic'):
                raise ValueError('Sweep mode must be linear or logarithmic')
            commands.append(samples_command(sequence, parameter, axis['start'], axis['stop'],
                                            axis['samples'], axis['mode'] == 'logarithmic'))
            cases *= axis['samples']
        else:
            commands.append(points_command(sequence, parameter, axis))
            cases *= len(axis)
        if cases > MAX_SWEEP_CASES:
            raise ValueError(f'Cartesian sweep exceeds {MAX_SWEEP_CASES} cases')
    lines = ['With ParameterSweep']
    if replace_all:
        lines.append('     .DeleteAllSequences')
    lines.append(f'     .AddSequence "{sequence}"')
    return '\n'.join(lines + commands + ['End With'])
