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


def _chain_names(parent_task, hb_task, post_task):
    for name in (parent_task, hb_task, post_task):
        _text(name)
        if any(not part or part in ('.', '..') for part in name.split('\\')):
            raise ValueError('Task paths require nonempty name components')
    if hb_task == post_task or any(
            name.rsplit('\\', 1)[0] != parent_task or '\\' not in name
            for name in (hb_task, post_task)):
        raise ValueError('HB and Post must be distinct direct children of the explicit parent')


def inspect_hb_postprocessing_chain(schematic, parent_task, hb_task, post_task):
    """Read task configuration only; never enumerate/evaluate result templates.

    ``readback_verified`` refers only to enabled task types and sibling order.
    It cannot certify template registration or persistence after a native reopen.
    Native query errors propagate rather than being replaced by requested values.
    """
    _chain_names(parent_task, hb_task, post_task)
    records = []
    for name, kind in ((parent_task, 'parameter sweep'), (hb_task, 'spectral lines'),
                       (post_task, 'template')):
        task = _task(schematic, name, kind)
        raw = str(task.GetProperty('enabled')).strip().lower()
        if raw not in ('true', 'false'):
            raise ValueError('Unrecognized native enabled value: ' + raw)
        records.append({'name': name, 'type': str(task.GetTypeForTask(name)),
                        'enabled': raw == 'true', 'generic_model_folder': str(task.GetModelFolder(True))})
    root = 'Tasks\\' + parent_task
    tree = schematic.ResultTree
    item = str(tree.GetFirstChildName(root))
    siblings, seen = [], set()
    for _ in range(10000):
        if not item:
            break
        if item in seen or not item.startswith(root + '\\'):
            raise ValueError('Native sibling enumeration is cyclic or outside the parent')
        seen.add(item)
        relative = item[len('Tasks\\'):]
        if relative.rsplit('\\', 1)[0] != parent_task:
            raise ValueError('Native query did not return direct siblings')
        # Result folders can coexist with task children. Only tasks affect order.
        task = schematic.SimulationTask
        task.Reset(); task.Name(relative)
        if task.DoesExist():
            siblings.append(relative)
        item = str(tree.GetNextItemName(item))
    else:
        raise ValueError('Native sibling enumeration did not terminate')
    ordered = hb_task in siblings and post_task in siblings and (
        siblings.index(post_task) == siblings.index(hb_task) + 1)
    return {'tasks': records, 'task_order': siblings, 'hb_then_post': ordered,
            'readback_verified': ordered and all(row['enabled'] for row in records),
            'binding_verified': False, 'reopen_verified': False, 'solver_verified': False}


def configure_hb_postprocessing_chain(schematic, parent_task, hb_task, post_task, *, create=False):
    """Configure HB -> Post scheduling only; this is NOT first-time binding.

    Uses documented SimulationTask operations. Does not save, rebuild, evaluate,
    update, generate a mesh or run a solver. Reuse the owning session's schematic.
    Native failures can leave partial configuration; inspect before retrying.
    """
    _chain_names(parent_task, hb_task, post_task)
    if type(create) is not bool:
        raise ValueError('create must be boolean')
    # Finish existence/type/conflict checks before the first mutation.
    _task(schematic, parent_task, 'parameter sweep')
    _task(schematic, hb_task, 'spectral lines')
    task = schematic.SimulationTask
    task.Reset(); task.Name(post_task)
    if create:
        if task.DoesExist():
            raise ValueError('Post task already exists; refusing to overwrite: ' + post_task)
    else:
        _task(schematic, post_task, 'template')
    _task(schematic, post_task, 'template', create=create)
    for name, kind in ((parent_task, 'parameter sweep'), (hb_task, 'spectral lines'),
                       (post_task, 'template')):
        _task(schematic, name, kind).SetProperty('enabled', 'True')
    _task(schematic, post_task, 'template').MoveInTree(parent_task, '')
    _task(schematic, hb_task, 'spectral lines').MoveInTree(parent_task, post_task.rsplit('\\', 1)[1])
    report = inspect_hb_postprocessing_chain(schematic, parent_task, hb_task, post_task)
    return dict(report, created=create, native_save_required=True)


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


def read_project_sp_impedances(project, task_name, ports, *, expected_project_path, receipt_root, confirm_idle=False):
    """Execute the documented ByRef query in an already-owned project only."""
    import json
    from cst_automation.sp_impedance_bridge import build_impedance_query, parse_impedance_receipt
    from cst_solver.native import execute_vba
    expected = Path(expected_project_path)
    if confirm_idle is not True or not expected.is_absolute() or Path(project.filename()).resolve() != expected.resolve():
        raise ValueError('Explicit idle and exact owned project required')
    request = build_impedance_query(expected, task_name, ports, receipt_root=receipt_root)
    output = Path(request['output_path'])
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        raise ValueError('Refusing existing receipt')
    manifest = output.with_suffix('.request.json')
    with manifest.open('x', encoding='utf-8') as stream:
        json.dump(request, stream, ensure_ascii=False, indent=2)
    execute_vba(project, request['vba_code'], target='schematic')
    if Path(project.filename()).resolve() != expected.resolve():
        raise ValueError('Project identity changed during query')
    report = parse_impedance_receipt(output.read_bytes(), request=request)
    report.update(artifact_path=str(output), manifest_path=str(manifest),
                  idle_asserted_by_caller=True, idle_verified=False)
    return report


def read_project_run_parameters(project, result_id, *, expected_project_path, receipt_root, confirm_idle=False):
    """Query one existing project using VBA ByRef, never a guessed Python ABI.

    Only the owning session may call this after confirming idle. This function
    does not independently detect idle, connect, save, solve, or close a project.
    """
    from cst_automation.run_parameter_bridge import prepare_run_parameter_query, parse_run_parameter_receipt
    from cst_solver.native import execute_vba
    if confirm_idle is not True:
        raise ValueError('The owning caller must first confirm the project is idle')
    expected = Path(expected_project_path)
    if not expected.is_absolute() or Path(project.filename()).resolve() != expected.resolve():
        raise ValueError('Owned native project does not match the registered path')
    request = prepare_run_parameter_query(expected, result_id, receipt_root=receipt_root)
    output = Path(request['output_path'])
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        raise ValueError('Refusing to reuse an existing query receipt')
    import json
    manifest = output.with_suffix('.request.json')
    with manifest.open('x', encoding='utf-8') as stream:
        json.dump(request, stream, ensure_ascii=False, indent=2)
    execute_vba(project, request['vba_code'], target='schematic')
    if Path(project.filename()).resolve() != expected.resolve():
        raise ValueError('Native project identity changed during the query')
    report = parse_run_parameter_receipt(output.read_bytes(), request=request)
    report.update(artifact_path=str(output), manifest_path=str(manifest),
                  idle_asserted_by_caller=True, idle_verified=False)
    return report


def resolve_schematic_result_id(schematic, tree_paths, *, read_parameters, expected_parameters,
                                requested_id=None, rtol=1e-10, atol=1e-12):
    """Read target IDs and stored combinations through a caller-verified reader.

    ``read_parameters(native_id)`` must return the actual stored combination,
    not RestoreParameter/current UI values. Its CST ByRef binding is supplied
    explicitly because wrappers differ. No last/max ID fallback is performed.
    """
    from cst_automation.result_identity import select_schematic_result_id
    if not callable(read_parameters) or not isinstance(tree_paths, (list, tuple)) or not tree_paths:
        raise ValueError('Target paths and a verified stored-parameter reader are required')
    for path in tree_paths:
        _text(path)
    available = {path: list(schematic.ResultTree.GetResultIDsFromTreeItem(path)) for path in tree_paths}
    common = set.intersection(*(set(ids) for ids in available.values()))
    # The selector validates domain/positive syntax. No parameter getter is
    # invoked for zero/current aliases or a foreign result domain.
    import re
    candidates = [rid for rid in common if isinstance(rid, str) and re.fullmatch(r'Schematic:RunID:[1-9][0-9]*', rid)]
    if requested_id not in (None, '', 'Schematic:RunID:0'):
        candidates = [rid for rid in candidates if rid == requested_id]
    parameters = {rid: read_parameters(rid) for rid in candidates}
    return select_schematic_result_id(available, parameters, expected_parameters=expected_parameters,
                                       requested_id=requested_id, rtol=rtol, atol=atol)


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


def resolve_hb_carriers(schematic, tree_paths, *, read_parameters, expected_parameters,
                        frequency_parameter, carrier_frequency, requested_id=None, parameter_rtol=1e-10,
                        parameter_atol=1e-12, frequency_rtol=1e-10, frequency_atol=1e-8):
    """Resolve one evidenced stored run, then verify carrier on every spectrum.

    The stored-parameter reader must be independently verified and safe in the
    caller's execution context. This function never calls an embedded VBA
    bridge, falls back to another run, or certifies fresh execution.
    """
    if not isinstance(tree_paths, (list, tuple)) or len(set(tree_paths)) != len(tree_paths):
        raise ValueError('Unique target spectrum paths are required')
    if any(isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value)
           for value in (carrier_frequency, frequency_rtol, frequency_atol)) or carrier_frequency <= 0 or min(frequency_rtol, frequency_atol) < 0:
        raise ValueError('Positive finite carrier frequency and nonnegative tolerances are required')
    selected = resolve_schematic_result_id(schematic, tree_paths, read_parameters=read_parameters,
        expected_parameters=expected_parameters, requested_id=requested_id,
        rtol=parameter_rtol, atol=parameter_atol)
    if (not isinstance(frequency_parameter, str) or frequency_parameter not in expected_parameters
            or not math.isclose(expected_parameters[frequency_parameter], carrier_frequency,
                                rel_tol=frequency_rtol, abs_tol=frequency_atol)
            or not math.isclose(selected['parameters'][frequency_parameter], carrier_frequency,
                                rel_tol=frequency_rtol, abs_tol=frequency_atol)):
        raise ValueError('Carrier frequency differs from the expected and stored RF parameter')
    rid = selected['result_id']
    carriers = {}
    for path in tree_paths:
        try:
            carriers[path] = read_spectral_component(schematic, path, carrier_frequency,
                result_id=rid, rtol=frequency_rtol, atol=frequency_atol)
        except ValueError as exc:
            raise ValueError(f'Carrier validation failed for {path} at {carrier_frequency:g} using {rid}: {exc}') from exc
    return {**selected, 'carrier_frequency': carrier_frequency, 'carriers': carriers,
            'carrier_unit_verified': False, 'execution_identity_verified': False, 'solver_verified': False}


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
