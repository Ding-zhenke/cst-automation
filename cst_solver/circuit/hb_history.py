"""Automatic HB history on a borrowed schematic; importing does not load CST."""

from hashlib import sha256
from importlib import import_module
import json
import math
import os
from pathlib import Path
import re
from tempfile import NamedTemporaryFile
from uuid import uuid4

from .native import resolve_schematic_result_id, write_real_curve


_TOKEN = re.compile(r'[a-zA-Z0-9][a-zA-Z0-9_-]{0,63}')
_TEMPLATE = '''\
def define(settings):
    from cst.tbpp import TemplateSettings
    from cst_solver.circuit.hb_history import validate_hb_history_settings
    validate_hb_history_settings(settings)
    return TemplateSettings(result_type="0D", eval_type="single_run")


def evaluate(eval_params, calling_app, prj, settings):
    from cst_solver.circuit.hb_history import evaluate_hb_history
    report = evaluate_hb_history(eval_params, calling_app, prj, settings)
    result = calling_app.Result0D("")
    result.SetData(int(report["status"] == "published"))
    return result
'''


def _json(data):
    return json.dumps(data, ensure_ascii=False, allow_nan=False, sort_keys=True)


def _digest(data):
    return sha256(_json(data).encode('utf-8')).hexdigest()


def _read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def _write(path, data):
    # A callback may be killed; never expose half of a point or receipt.
    payload = _json(data)
    stream = NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent, delete=False)
    temp = Path(stream.name)
    try:
        with stream:
            stream.write(payload)
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


def _number(value):
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError('HB values must be finite real numbers')
    return float(value) if value else 0.0


def _text(value, *, empty=False):
    if not isinstance(value, str) or (not empty and not value.strip()) or any(ord(c) < 32 for c in value):
        raise ValueError('Invalid HB history text')
    return value


def _token(value):
    if not isinstance(value, str) or not _TOKEN.fullmatch(value):
        raise ValueError('Expected an explicit safe HB execution or namespace identifier')
    return value


def _sha(value):
    if not isinstance(value, str) or not re.fullmatch(r'[0-9a-f]{64}', value):
        raise ValueError('A SHA-256 observation is required')
    return value


def validate_hb_history_settings(settings):
    """Check the explicit grid, parameter/EM mapping and spectrum units without CST."""
    data = json.loads(_json(settings))
    _token(data['namespace'])
    _text(data['task_name'])
    _text(data['revision'])
    if not all(part.isidentifier() for part in _text(data['adapter']).split('.')):
        raise ValueError('Expected an importable project adapter module name')
    units = data['parameter_units']
    rf, direction = data['frequency_parameter'], data['direction_parameter']
    if rf == direction or rf not in units or direction not in units:
        raise ValueError('Distinct frequency and direction parameters need units')
    for name, unit in units.items():
        _text(name)
        _text(unit, empty=True)
    _text(units[rf])
    for key in ('frequencies', 'directions'):
        values = [_number(value) for value in data[key]]
        ordered = sorted(values)
        if not values or any(_close(a, b) for a, b in zip(ordered, ordered[1:])) or (key == 'frequencies' and
                (values != sorted(values) or values[0] <= 0)):
            raise ValueError('Expected unique grid coordinates and increasing positive RF frequencies')
        data[key] = values
    em_map = data['em_parameter_map']
    if not em_map or not set(em_map.values()) <= (set(units) - {rf, direction}):
        raise ValueError('EM parameter mapping must reference non-grid case parameters')
    for name in em_map:
        _text(name)
    if not data['spectra'] or not data['normalization']:
        raise ValueError('Spectrum inputs and normalization are required')
    for path, axes in data['spectra'].items():
        if not _text(path).startswith('Tasks\\'):
            raise ValueError('Expected a native Tasks spectrum path')
        _text(axes['x_unit'])
        _text(axes['y_unit'], empty=True)
    return data


def write_hb_history_template(destination):
    """Create the registerable 0D/single_run Post callback without executing it."""
    path = Path(destination)
    if path.suffix.lower() != '.rtpy':
        raise ValueError('Expected an .rtpy destination')
    with path.open('x', encoding='utf-8', newline='\n') as stream:
        stream.write(_TEMPLATE)
    return path


def _project_root(prj, settings):
    project = Path(prj.filename())
    if not project.is_absolute():
        project = Path(prj.folder()) / project
    project = project.resolve()
    if project.suffix.lower() != '.cst' or not project.is_file():
        raise ValueError('A saved owned .cst is required for HB history')
    root = project.with_name(project.name + '.hb-history') / settings['namespace']
    if root.resolve() != root:
        raise ValueError('HB history archive must stay beside the owned project')
    return project, root


def _report(status, **fields):
    return dict(status=status, representation='static_results_snapshot',
                native_parametric_storage_verified=False, native_navigator_overlay_verified=False,
                native_parametric_storage_enabled=None, saved_readback_verified=False,
                reopen_verified=False, solver_verified=False, **fields)


def _close(a, b):
    return math.isclose(a, b, rel_tol=1e-10, abs_tol=1e-12)


def _grid_index(grid, value):
    indexes = [i for i, candidate in enumerate(grid) if _close(candidate, value)]
    if len(indexes) != 1:
        raise ValueError('Actual HB point is outside or ambiguous on the configured grid')
    return indexes[0]


def _read_spectra(schematic, paths, result_id):
    spectra = {}
    tree = schematic.ResultTree
    for path, axes in paths.items():
        result = tree.GetResultFromTreeItem(path, result_id)
        if result is None:
            raise ValueError('HB spectrum missing: ' + path)
        arrays = {axis: [_number(v) for v in result.GetArray(axis)] for axis in ('x', 'yre', 'yim')}
        if not arrays['x'] or len({len(values) for values in arrays.values()}) != 1:
            raise ValueError('Incomplete complex HB spectrum: ' + path)
        spectra[path] = {**arrays, 'x_unit': axes['x_unit'], 'y_unit': axes['y_unit']}
    return spectra


def _publish(schematic, adapter, settings, folder, context, points, execution):
    case = context['case_parameters']
    label = ', '.join(f'{k}={v:g} {settings["parameter_units"][k]}'.strip() for k, v in sorted(case.items()))
    slug = re.sub(r'[^a-zA-Z0-9_.=-]+', '_', label)[:52].rstrip('.')
    case_id = 'Case_' + (slug + '_' if slug else '') + _digest(context['case_identity'])[:20]
    root = '\\'.join(('Results', 'HBHistory', settings['namespace'], case_id, 'Run_' + execution))
    output = adapter.derive(points=points, settings=settings)
    if not isinstance(output, dict) or not output:
        raise ValueError('HB derive must return at least one real frequency curve')
    # Use the actual stored RF frequency, not the requested grid or spectrum axis.
    xs = [points[i]['rf'] for i in range(0, len(points), len(settings['directions']))]
    if any(b <= a for a, b in zip(xs, xs[1:])):
        raise ValueError('Stored RF coordinates are not strictly increasing')
    curves = []
    for index, (quantity, curve) in enumerate(output.items()):
        _token(quantity)
        if quantity.casefold() in {c['quantity'].casefold() for c in curves}:
            raise ValueError('Duplicate native curve name')
        ys = [_number(v) for v in curve['y']]
        if len(xs) != len(ys):
            raise ValueError('Derived HB curve does not cover the complete RF grid')
        db = curve.get('values_in_db', False)
        if type(db) is not bool:
            raise ValueError('values_in_db must be boolean')
        title = _text(curve.get('title', quantity)) + ' | ' + label
        path = root + '\\' + quantity
        signal = folder / f'curve-{index}.sig'
        if schematic.ResultTree.DoesTreeItemExist(path) or signal.exists():
            raise ValueError('HB publication would overwrite an existing curve')
        curves.append(dict(quantity=quantity, tree_path=path, signal_file=str(signal),
                           x=xs, y=ys, title=title, x_label='RF frequency',
                           x_unit=settings['parameter_units'][settings['frequency_parameter']],
                           y_label=_text(curve['y_label']), y_unit=_text(curve['y_unit'], empty=True), values_in_db=db))
    receipt = folder / 'publication.json'
    fields = dict(execution_id=execution, case_id=case_id, label=label, context=context, curves=curves,
                  publication_path=str(receipt), point_count=len(points))
    _write(receipt, _report('publishing', **fields))
    try:
        for curve in curves:
            write_real_curve(schematic, **{k: v for k, v in curve.items() if k != 'quantity'})
    except Exception as exc:
        _write(receipt, _report('publication_failed', error=f'{type(exc).__name__}: {exc}', **fields))
        raise
    report = _report('published', **fields)
    _write(receipt, report)
    return report


def _collect(eval_params, schematic, prj, settings, adapter, observation, project, folder, execution):
    if observation.get('point_verified') is not True or not observation.get('evidence'):
        raise ValueError('Current HB completion and input evidence is required')
    names = settings['parameter_units']
    expected = {k: _number(v) for k, v in observation['expected_parameters'].items()}
    if set(expected) != set(names):
        raise ValueError('Requested HB parameters differ from the declared parameter set')
    em = observation['em_source']
    _text(em['path'])
    _sha(em['sha256'])
    config = _sha(observation['configuration_sha256'])
    mapping = settings['em_parameter_map']
    if any(name not in em['parameters'] or not _close(_number(em['parameters'][name]), expected[target])
           for name, target in mapping.items()):
        raise ValueError('Linked EM source parameters do not match the current HB request')
    native_id = observation.get('result_id')
    if not isinstance(native_id, str) or not re.fullmatch(r'Schematic:RunID:[1-9][0-9]*', native_id):
        raise ValueError('HB completion evidence must identify an explicit positive Schematic Run ID')
    selected = resolve_schematic_result_id(schematic, list(settings['spectra']),
        read_parameters=lambda rid: adapter.read_parameters(prj=prj, calling_app=schematic, result_id=rid),
        expected_parameters=expected, requested_id=native_id)
    if set(selected['parameters']) != set(names):
        raise ValueError('Stored HB parameters differ from the declared parameter set')
    actual = {k: _number(v) for k, v in selected['parameters'].items()}
    rf, direction = settings['frequency_parameter'], settings['direction_parameter']
    if any(not _close(_number(em['parameters'][name]), actual[target]) for name, target in mapping.items()):
        raise ValueError('Linked EM parameters do not match the stored HB result')
    i = _grid_index(settings['frequencies'], actual[rf])
    j = _grid_index(settings['directions'], actual[direction])
    case = {k: v for k, v in actual.items() if k not in (rf, direction)}
    case_identity = dict(parameters=case, parameter_units=names, em_sha256=em['sha256'],
                         configuration_sha256=config, settings_sha256=_digest(settings))
    context = dict(project=str(project), task=settings['task_name'], settings=settings, case_parameters=case,
                   case_identity=case_identity, em_source=em, execution_id=execution)
    context_path = folder / 'context.json'
    if context_path.exists():
        if _digest(_read(context_path)) != _digest(context):
            raise ValueError('Conflicting parameters, EM provenance or settings within one HB execution')
    else:
        _write(context_path, context)
    paths = [folder / f'point-{f}-{d}.json' for f in range(len(settings['frequencies']))
             for d in range(len(settings['directions']))]
    current = paths[i * len(settings['directions']) + j]
    point = dict(parameters=actual, expected_parameters=expected, result_id=selected['result_id'],
                 rf=actual[rf], direction=actual[direction], execution_id=execution,
                 callback_result_id=eval_params.result_id, evidence=observation['evidence'],
                 spectra=_read_spectra(schematic, settings['spectra'], selected['result_id']))
    if current.exists():
        previous = _read(current)
        # Invocation/log metadata can change on a repeat; raw observations cannot.
        fields = ('parameters', 'result_id', 'spectra')
        if any(point[k] != previous[k] for k in fields):
            raise ValueError('Conflicting repeated HB point within one execution')
    else:
        _write(current, point)
    receipt = folder / 'publication.json'
    if receipt.exists():
        report = _read(receipt)
        if report['status'] != 'published':
            raise ValueError('HB publication was interrupted; preserve outputs and review before a new run')
        return report
    coordinates = [(f, d) for f in settings['frequencies'] for d in settings['directions']]
    missing = [list(coordinate) for coordinate, path in zip(coordinates, paths) if not path.is_file()]
    if missing:
        return _report('collecting', execution_id=execution, missing=missing)
    points = [_read(path) for path in paths]
    for start in range(0, len(points), len(settings['directions'])):
        group = points[start:start + len(settings['directions'])]
        if any(not _close(point['rf'], group[0]['rf']) for point in group):
            raise ValueError('Stored RF coordinates disagree between directions')
    return _publish(schematic, adapter, settings, folder, context, points, execution)


def evaluate_hb_history(eval_params, calling_app, prj, settings):
    """Archive one verified native HB point and publish automatically at complete coverage."""
    settings = validate_hb_history_settings(settings)
    project, root = _project_root(prj, settings)
    marker = root / 'active.json'
    active = _read(marker) if marker.exists() else None
    if active and (active['project'] != str(project) or active['settings_sha256'] != _digest(settings)):
        raise ValueError('Active HB history execution belongs to different settings or project')
    adapter = import_module(settings['adapter'])
    observation = adapter.observe(eval_params=eval_params, calling_app=calling_app, prj=prj, settings=settings)
    token = active['execution_id'] if active else observation.get('execution_id')
    # Hash the adapter token for a Windows-safe filename and case-insensitive uniqueness.
    execution = _digest(_token(token))[:32]
    folder = root / ('run-' + execution)
    if folder.resolve() != folder:
        raise ValueError('HB execution archive must stay in its owned namespace')
    folder.mkdir(parents=True, exist_ok=True)
    lock = folder / 'collecting.lock'
    # Native serial callbacks are required; don't race a second writer or retry
    # a callback interrupted during a previous write.
    try:
        lock.touch(exist_ok=False)
    except FileExistsError as exc:
        raise ValueError('Concurrent or interrupted HB callback; use an owned serial task') from exc
    failure = folder / 'failure.json'
    try:
        if failure.exists():
            raise ValueError('Earlier HB point failed; preserve this execution for review')
        try:
            return _collect(eval_params, calling_app, prj, settings, adapter, observation, project, folder, execution)
        except Exception as exc:
            _write(failure, {'execution_id': execution, 'error': f'{type(exc).__name__}: {exc}'})
            raise
    finally:
        lock.unlink()


def run_hb_history(api, task_name, *, settings, expected_results, note=''):
    """Invoke the owned HB parent once with an isolated callback execution token."""
    settings = validate_hb_history_settings(settings)
    if task_name != settings['task_name']:
        raise ValueError('Run the exact HB history parent configured in the Post template')
    project, root = _project_root(api.app.cst_file, settings)
    root.mkdir(parents=True, exist_ok=True)
    token = uuid4().hex
    execution = _digest(token)[:32]
    marker = root / 'active.json'
    folder = root / ('run-' + execution)
    with marker.open('x', encoding='utf-8') as stream:
        stream.write(_json(dict(project=str(project), execution_id=token, settings_sha256=_digest(settings))))
    try:
        result = api.run_checked(task_name, mode='network', expected_results=expected_results, reuse='never', note=note)
    finally:
        marker.unlink()
    publication = folder / 'publication.json'
    failure = folder / 'failure.json'
    report = _read(publication) if publication.is_file() else _report(
        'failed' if failure.is_file() else ('incomplete' if folder.is_dir() else 'callback_not_observed'),
        execution_id=execution)
    if failure.is_file():
        report['failure_path'] = str(failure)
        if report['status'] == 'published':
            report['status'] = 'published_with_callback_failure'
    report.update(project_save_reported=result.get('saved') is True, saved_digest=result.get('saved_digest'),
                  parent_status=result.get('status'), parent_run_token=result.get('run_token'),
                  execution_returned=result.get('execution_returned') is True)
    folder.mkdir(exist_ok=True)
    report['owner_receipt_path'] = str(folder / 'owner-run.json')
    _write(Path(report['owner_receipt_path']), report)
    return {**result, 'hb_history': report}
