"""Small native schematic primitives; no SDK import, saving, or solver calls.

Accept an opened project's ``schematic`` or a result template's ``calling_app``.
HB frequency values use the selected task's active units (including local units).
Sweep points use native parameter units. These functions do not replace
the evidence and scheduling contract of ``CircuitAPI.run_checked``.
"""
import math
from pathlib import Path


def _text(value):
    if not isinstance(value, str) or not value.strip() or any(c in value for c in '\r\n\x00'):
        raise ValueError('Expected nonempty text without control characters')
    return value


def _expression(value, *, order=False):
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        raise ValueError('Expected a number or CST parameter expression')
    text = _text(value) if isinstance(value, str) else format(value, '.17g')
    try:
        number = float(text)
    except ValueError:
        return text
    if not math.isfinite(number) or number <= 0 or (order and not number.is_integer()):
        raise ValueError('Frequency must be positive; harmonic order must be a positive integer')
    return text


def _task(schematic, name, kind, *, create=False):
    task = schematic.SimulationTask
    task.Reset(); task.Name(name)
    exists = bool(task.DoesExist())
    if create:
        if exists:
            raise ValueError('Task already exists; refusing to overwrite: ' + name)
        task.Type(kind); task.Name(name); task.Create()
        task.Reset(); task.Name(name)
    elif not exists or str(task.GetTypeForTask(name)).lower() != kind:
        raise ValueError('An existing ' + kind + ' task is required: ' + name)
    return task


def configure_hb_task(schematic, task_name, tones, *, diamond=False, create=False):
    """Replace tone definitions only; preserve expressions and other settings.

    Each tone has exactly ``frequency`` and ``order``. Numeric frequencies use
    the selected task's active frequency units, which may be local rather than
    project units. Units are not switched. Verify them before supplying numbers;
    expression semantics/coverage also require native verification.
    ``create=True`` creates a new task and refuses existing names.
    """
    _text(task_name)
    if type(diamond) is not bool or type(create) is not bool:
        raise ValueError('diamond and create must be boolean')
    if not isinstance(tones, (list, tuple)) or not tones:
        raise ValueError('At least one explicit HB tone is required')
    normalized = []
    for tone in tones:
        if not isinstance(tone, dict) or set(tone) != {'frequency', 'order'}:
            raise ValueError('Each HB tone requires only frequency and order')
        normalized.append((_expression(tone['frequency']), _expression(tone['order'], order=True)))
    task = _task(schematic, task_name, 'spectral lines', create=create)
    task.SetDiamondScheme(diamond)
    task.ClearFundamentalFrequencies()
    for frequency, order in normalized:
        task.AddFundamentalFrequency(frequency, order)
    return {'task_name': task_name, 'tones': normalized, 'diamond': diamond,
            'created': create, 'readback_verified': False, 'solver_verified': False}


def replace_parameter_sweep_sequences(schematic, task_name, sequences):
    """Replace all sequences of an existing native sweep, retaining its children.

    ``sequences`` maps sequence names to parameter-name -> explicit point lists.
    Values may be finite real numbers or CST expressions without semicolons.
    This configures native sweep sequences; it does not run a Python sweep loop.
    """
    _text(task_name)
    if not isinstance(sequences, dict) or not sequences:
        raise ValueError('At least one explicit sequence is required')
    normalized = []
    for sequence, parameters in sequences.items():
        _text(sequence)
        if not isinstance(parameters, dict) or not parameters:
            raise ValueError('Each sequence requires parameters')
        for parameter, values in parameters.items():
            _text(parameter)
            if not isinstance(values, (list, tuple)) or not values:
                raise ValueError('Each parameter requires an explicit point list')
            points = []
            for value in values:
                if isinstance(value, bool) or not isinstance(value, (str, int, float)):
                    raise ValueError('Invalid sweep point')
                if isinstance(value, str):
                    point = _text(value)
                    if ';' in point:
                        raise ValueError('A point cannot contain the list delimiter')
                    try:
                        numeric = float(point)
                    except ValueError:
                        numeric = None
                    if numeric is not None and not math.isfinite(numeric):
                        raise ValueError('Non-finite sweep point')
                else:
                    if not math.isfinite(value):
                        raise ValueError('Non-finite sweep point')
                    point = format(value, '.17g')
                points.append(point)
            normalized.append((sequence, parameter, ';'.join(points)))
    _task(schematic, task_name, 'parameter sweep')
    sweep = schematic.ParameterSweep
    sweep.SetSimulationType(task_name)
    sweep.DeleteAllSequences()
    for sequence in sequences:
        sweep.AddSequence(sequence)
        for seq, parameter, points in normalized:
            if seq == sequence:
                sweep.AddParameter_ArbitraryPoints(sequence, parameter, points)
    return {'task_name': task_name, 'sequences': normalized,
            'readback_verified': False, 'solver_verified': False}


def read_spectral_component(schematic, tree_path, frequency, *, result_id, rtol=1e-10, atol=1e-8):
    """Read one complex spectral component using an explicit native result ID."""
    _text(tree_path)
    if result_id is None or result_id == '' or isinstance(result_id, bool):
        raise ValueError('An explicit native result_id is required')
    if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v)
           for v in (frequency, rtol, atol)) or frequency < 0 or min(rtol, atol) < 0:
        raise ValueError('Frequency and tolerances must be finite and nonnegative')
    result = schematic.ResultTree.GetResultFromTreeItem(tree_path, result_id)
    if result is None:
        raise ValueError('Native spectral result is missing: ' + tree_path)
    xs, reals, imags = [list(result.GetArray(axis)) for axis in ('x', 'yre', 'yim')]
    if not xs or len(xs) != len(reals) or len(xs) != len(imags):
        raise ValueError('Native spectral arrays are empty or inconsistent')
    matches = [i for i, x in enumerate(xs) if math.isclose(float(x), frequency, rel_tol=rtol, abs_tol=atol)]
    if len(matches) != 1:
        raise ValueError('Requested spectral frequency is absent or ambiguous')
    index = matches[0]
    value = complex(reals[index], imags[index])
    if not math.isfinite(value.real) or not math.isfinite(value.imag):
        raise ValueError('Non-finite spectral component')
    return value


def write_real_curve(schematic, tree_path, signal_file, x, y, *, title,
                     x_label, x_unit, y_label, y_unit, values_in_db=False, replace=False):
    """Write a real Result1D beneath Results; explicitly opt into replacement.

    Validate first, then delete the old leaf BEFORE saving its replacement:
    CST may remove the associated signal file when deleting a tree leaf.
    The caller owns the supplied result leaf and output signal path.
    """
    _text(tree_path)
    parts = tree_path.split('\\')
    if len(parts) < 2 or parts[0] != 'Results' or any(p in ('', '.', '..') for p in parts):
        raise ValueError('A leaf below Results is required')
    for text in (title, x_label, y_label):
        _text(text)
    for unit in (x_unit, y_unit):
        if not isinstance(unit, str) or any(c in unit for c in '\r\n\x00'):
            raise ValueError('Axis units must be text')
    if type(values_in_db) is not bool or type(replace) is not bool:
        raise ValueError('values_in_db and replace must be boolean')
    xs, ys = list(x), list(y)
    if not xs or len(xs) != len(ys) or any(isinstance(v, bool) or not isinstance(v, (int, float))
        or not math.isfinite(v) for v in xs + ys) or any(b <= a for a, b in zip(xs, xs[1:])):
        raise ValueError('Curve needs finite real equal-length arrays and strictly increasing x')
    destination = Path(signal_file).resolve()
    if destination.suffix.lower() != '.sig':
        raise ValueError('Expected a .sig destination')
    tree = schematic.ResultTree
    exists = bool(tree.DoesTreeItemExist(tree_path))
    if not replace and (exists or destination.exists()):
        raise ValueError('Curve or signal exists; explicit replace=True is required')
    if exists and tree.GetFirstChildName(tree_path):
        raise ValueError('Only an existing result leaf may be replaced; folders with children are refused')
    curve = schematic.Result1D('')
    for a, b in zip(xs, ys):
        curve.AppendXY(str(a), str(b))
    curve.Title(title)
    curve.SetXLabelAndUnit(x_label, x_unit)
    curve.SetYLabelAndUnit(y_label, y_unit)
    if values_in_db:
        curve.SetLogarithmicFactor('-1')
    destination.parent.mkdir(parents=True, exist_ok=True)
    for index in range(2, len(parts)):
        folder = '\\'.join(parts[:index])
        if not tree.DoesTreeItemExist(folder):
            tree.Reset(); tree.Name(folder); tree.Type('folder'); tree.DeleteAt('never'); tree.Add()
    if exists:
        tree.Reset(); tree.Name(tree_path); tree.Delete()
    curve.Save(str(destination))
    tree.Reset(); tree.Name(tree_path); tree.Type('xysignal'); tree.Subtype('real')
    tree.File(str(destination)); tree.Title(title)
    tree.Xlabel(x_label + (' / ' + x_unit if x_unit else ''))
    tree.Ylabel(y_label + (' / ' + y_unit if y_unit else ''))
    tree.DeleteAt('never'); tree.Add()
    return {'tree_path': tree_path, 'signal_file': str(destination), 'points': len(xs),
            'replaced': exists, 'readback_verified': False, 'solver_verified': False}
