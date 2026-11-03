"""Pure validation and official CST commands for a discrete sweep definition."""
import math

from cst_solver.expressions import validate_parameter_name


def points_command(sequence, parameter, points):
    if (not isinstance(sequence, str) or not sequence.strip() or len(sequence) > 128
            or any(c in sequence for c in ('"', '\r', '\n'))):
        raise ValueError('Invalid sweep sequence name')
    validate_parameter_name(parameter)
    if not isinstance(points, (list, tuple)) or not 1 <= len(points) <= 10000:
        raise ValueError('A nonempty bounded list of numeric points is required')
    if any(type(p) not in (int, float) or not math.isfinite(p) for p in points):
        raise ValueError('Sweep points must be finite numbers, not expressions or booleans')
    values = ';'.join(str(p) for p in points)
    return f'     .AddParameter_ArbitraryPoints "{sequence}", "{parameter}", "{values}"'


def discrete_sweep_code(sequence, parameters, replace_all=False):
    if type(replace_all) is not bool:
        raise ValueError('replace_all must be boolean')
    if not isinstance(parameters, dict) or not 1 <= len(parameters) <= 100:
        raise ValueError('A bounded nonempty parameter mapping is required')
    commands = [points_command(sequence, name, points) for name, points in parameters.items()]
    lines = ['With ParameterSweep']
    if replace_all:
        lines.append('     .DeleteAllSequences')
    lines.append(f'     .AddSequence "{sequence}"')
    return '\n'.join(lines + commands + ['End With'])
