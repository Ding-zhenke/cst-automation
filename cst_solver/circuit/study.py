"""Fixed-topology point sequence; all solver acceptance remains in existing APIs."""
import hashlib
import json
import math
from pathlib import Path

from cst_automation.circuit_studies import normalize_parameter_study
from cst_automation.circuit_schema import BLOCK_TYPES, validate_circuit_spec, evaluate_quantity
from .adapter import CircuitError, validate_property_write
from .native import write_real_curve
from .results import CircuitResult
from .study_results import (create_archive, store_case, finish_archive, component_values, COMPONENTS)


def read_em_curve(app, result):
    from cst_solver import Result
    reader = Result(app.cst_file.filename())
    item = reader.get_result_item(result['tree_path'], run_id=result['run_id'])
    from .results import quantity_values, axis_unit
    x, xu = quantity_values(item.get_xdata(), axis_unit(item, 'x', result['tree_path']))
    y, yu = quantity_values(item.get_ydata(), axis_unit(item, 'y', result['tree_path']))
    if len(x) != len(y) or any(v.imag for v in x):
        raise ValueError('EM result axes are inconsistent')
    return {'x': [v.real for v in x], 'y': y, 'x_unit': xu, 'y_unit': yu,
            'tree_path': result['tree_path'], 'run_id': result['run_id'], 'domain': '3d',
            'parameters':dict(reader.result_module.get_parameter_combination(result['run_id']))}


def em_result_probe(app, results):
    """Fingerprint only native files bound to the requested result tree leaves.

    No fallback to logs or the whole Result directory. Missing/unavailable file
    mappings remain explicit; the post-solve verifier refuses them.
    """
    items = []
    for requested in results:
        row = {'tree_path':requested['tree_path'], 'run_id':requested['run_id'], 'exists':False}
        try:
            native_path = str(app.cst_file.model3d.ResultTree.GetFileFromTreeItem(requested['tree_path']))
            file = Path(native_path)
            if not native_path or not file.is_absolute():
                raise ValueError('Native result file is absent or its absolute path is unavailable')
            row['file_path'] = str(file.resolve())
            if file.is_file():
                digest = hashlib.sha256()
                with file.open('rb') as handle:
                    for chunk in iter(lambda: handle.read(1024 * 1024), b''):
                        digest.update(chunk)
                stat = file.stat()
                row.update(exists=True, size=stat.st_size, mtime_ns=stat.st_mtime_ns, sha256=digest.hexdigest())
        except Exception as exc:
            row['error'] = str(exc)
        items.append(row)
    return {'kind':'selected_em_results', 'items':items}


def _check_source_parameters(curve, spec, values, *, domain):
    actual = curve.get('parameters', {})
    for name, definition in spec['parameters'].items():
        # A block binding's logical alias is not a native global parameter.
        if 'block' in definition or (domain == '3d' and definition['scope'] != 'em'):
            continue
        # Geometry is checked directly on the EM result. Some schematic result
        # databases omit those globals; if present they must still agree.
        if domain == 'schematic' and definition['scope'] == 'em' and name not in actual:
            continue
        try:
            value = float(actual[name])
            matches = math.isfinite(value) and math.isclose(value, values[name], rel_tol=1e-10, abs_tol=0.)
        except (KeyError, TypeError, ValueError):
            matches = False
        if not matches:
            raise CircuitError('circuit_result_unverified', 'Source result global parameter is missing or differs from the requested native value', parameter=name, domain=domain)


def _snapshot(curve):
    data = {k: v for k,v in curve.items() if k not in ('x','y')}
    data.update(x=list(curve['x']), y=[[v.real,v.imag] for v in curve['y']])
    encoded = json.dumps({'x':data['x'], 'y':data['y']}, allow_nan=False, sort_keys=True)
    data['archive_sample_digest'] = hashlib.sha256(encoded.encode()).hexdigest()
    return data


def _preflight(api, spec):
    project = Path(api.app.cst_file.filename()).resolve()
    if not project.is_file():
        raise CircuitError('circuit_unavailable', 'An existing saved project is required')
    task = api.adapter.task(spec['task']['name'])
    if task['type'] not in ('s-parameter', 's-parameters', 'ac', 'dc', 'operating point', 'spectral lines', 'transient'):
        raise CircuitError('circuit_mode_unsupported', 'Select one leaf circuit task, not a sweep or sequence')
    if task['type'] == 'transient' and task.get('properties', {}).get('circuit simulator', '').lower() == 'cosimulation':
        raise CircuitError('circuit_mode_unsupported', 'Bidirectional transient cosimulation is not a study backend')
    requested = spec['task']['results'] + spec.get('em', {}).get('results', [])
    if any(r['run_id'] != 0 for r in requested):
        raise CircuitError('circuit_spec_invalid', 'Execution uses explicit current run 0; immutable snapshots preserve each case')
    snapshot = api.inspect()
    blocks = {b['name']:b for b in snapshot['blocks']}
    linked = [b for b in snapshot['blocks'] if b['type'].lower() in
              ('cstmws', 'cstmwsfile', 'cst microwave studio', 'cst microwave studio schematic block')]
    if linked and 'em' not in spec:
        raise CircuitError('circuit_dependency_missing', 'Linked EM data require an explicit EM dependency')
    if 'em' in spec:
        candidates = [b for b in linked if len(b.get('files', [])) == 1
                      and Path(b['files'][0]).resolve() == project]
        if len(candidates) != 1 or len(linked) != 1:
            raise CircuitError('circuit_mode_unsupported', 'Only one associated self EM block is supported; external EM mapping is not inferred')
    for name, definition in spec['parameters'].items():
        if 'block' in definition:
            block = blocks.get(definition['block'])
            if block is None:
                raise CircuitError('circuit_topology_invalid', 'Study block is missing', block_name=definition['block'])
            kind = next((t for t in BLOCK_TYPES if t.rsplit('\\',1)[-1].lower() == block['type'].rsplit('\\',1)[-1].lower()), block['type'])
            for point in spec['points']:
                validate_property_write({definition['property']:point['values'][name]},
                    {definition['property']:definition['unit']}, intrinsic_diode=block['type'].rsplit('\\',1)[-1].lower() == 'diode')
                validate_circuit_spec({'schema_version':1,'blocks':[{'name':definition['block'], 'type':kind,
                    'properties':{definition['property']:point['values'][name]},
                    'property_units':{definition['property']:definition['unit']}}]})
        else:
            owner = api.app.cst_file.model3d if definition['scope'] == 'em' else api.app.cst_file.schematic
            if not owner.DoesParameterExist(name):
                raise CircuitError('circuit_topology_invalid', 'Study parameter must already exist', parameter=name)
    return project


def run_parameter_study(api, spec):
    spec = normalize_parameter_study(spec)
    project = _preflight(api, spec)
    batch = create_archive(project, spec)
    report = {'status':'running', 'batch_path':str(batch), 'manifest_path':str(batch/'study.json'),
              'saved':False, 'reopen_verified':False, 'saved_readback_verified':False, 'cases':[], 'errors':[]}
    for index, point in enumerate(spec['points'], 1):
        case_id = 'p' + format(index, '04d')
        case = {'case_id':case_id, 'parameters':point['values'], 'status':'running',
                'curves':{}, 'native_curves':[], 'errors':[], 'em':None, 'circuit':None, 'parameter_readback':{}}
        try:
            api._spec = None
            for name, definition in spec['parameters'].items():
                value = point['values'][name]
                if 'block' in definition:
                    change = api.set_properties(definition['block'], {definition['property']:value}, units={definition['property']:definition['unit']})
                    actual = float(change['readback'][definition['property']])
                    expected = evaluate_quantity(value, definition['unit'], {})[0]
                    convention = 'SI'
                elif definition['scope'] == 'em':
                    api.app.para(name, value)
                    actual = float(api.app.cst_file.model3d.RestoreDoubleParameter(name))
                    expected, convention = value, 'native'
                else:
                    api.app.cst_file.schematic.StoreParameter(name, format(value, '.17g'))
                    actual = float(api.app.cst_file.schematic.RestoreDoubleParameter(name))
                    expected, convention = value, 'native'
                if not math.isfinite(actual) or not math.isclose(actual, expected, rel_tol=1e-10, abs_tol=0.):
                    raise CircuitError('circuit_result_unverified', 'Study parameter readback differs from requested value', parameter=name)
                case['parameter_readback'][name] = {'value':actual, 'convention':convention, 'requested_unit':definition['unit']}
            if 'em' in spec:
                api.app.update()
            api.app.save()
            report['saved'] = True
            if 'em' in spec:
                requests = spec['em']['results']
                source_before = em_result_probe(api.app, requests)
                proof = api.app.run_checked(note='Parameter study ' + spec['name'] + '/' + case_id,
                    probe=lambda path: em_result_probe(api.app, requests))
                source_after = em_result_probe(api.app, requests)
                case['em'] = {'execution':proof, 'reused':False, 'results':[],
                              'sources_before':source_before, 'sources_after':source_after}
                if proof.get('status') != 'succeeded':
                    raise CircuitError('circuit_result_unverified', 'EM execution was not verified')
                state = api.app.cst_file.model3d.get_solver_run_info()
                case['em']['native_state'] = state
                before_rows, after_rows = source_before['items'], source_after['items']
                fresh = (len(after_rows) == len(requests) and all(
                    after.get('exists') and not after.get('error') and after != before
                    for before, after in zip(before_rows, after_rows)))
                if state.get('state') != 'SUCCESS' or not fresh:
                    raise CircuitError('circuit_result_unverified', 'Specified EM data files were not refreshed by a completed solver run')
                api.app.save()
                for result in requests:
                    raw = read_em_curve(api.app, result)
                    case['em']['results'].append(_snapshot(raw))
                    _check_source_parameters(raw, spec, point['values'], domain='3d')
            result = api.run_checked(spec['task']['name'], mode=spec['task']['mode'],
                expected_results=[{k:v for k,v in item.items() if k != 'name'} for item in spec['task']['results']],
                reuse='never', note='Parameter study ' + spec['name'] + '/' + case_id)
            case['circuit'] = result
            if result.get('status') != 'succeeded':
                raise CircuitError('circuit_result_unverified', 'Circuit execution was not verified')
            reader = CircuitResult(str(project))
            # Capture every source before any native result-tree mutation.
            for item in spec['task']['results']:
                raw = reader.read_curve(item['tree_path'], run_id=item['run_id'])
                case['curves'][item['name']] = _snapshot(raw)
                _check_source_parameters(raw, spec, point['values'], domain='schematic')
            # A durable source checkpoint precedes any native result-tree write.
            with (batch / (case_id + '.sources.json')).open('x', encoding='utf-8') as checkpoint:
                json.dump(case, checkpoint, ensure_ascii=False, allow_nan=False, indent=2)
            for name, raw in case['curves'].items():
                source = {**raw, 'y':[complex(*v) for v in raw['y']]}
                for component in COMPONENTS:
                    ys, unit = component_values(source, component)
                    tree = '\\'.join(('Results','Studies',spec['name'],batch.name,name,component,case_id))
                    file = batch / 'signals' / name / component / (case_id + '.sig')
                    native = write_real_curve(api.app.cst_file.schematic, tree, file, raw['x'], ys,
                        title=name + ' ' + component + ' ' + json.dumps(point['values'],ensure_ascii=False),
                        x_label='Source axis', x_unit=raw['x_unit'], y_label=component, y_unit=unit)
                    case['native_curves'].append({**native, 'result_name':name, 'component':component})
            api.app.save()
            case['status'] = 'succeeded'
        except Exception as exc:
            code = getattr(exc, 'code', 'circuit_study_failed')
            case['status'] = 'unverified' if code == 'circuit_result_unverified' else 'failed'
            case['errors'].append({'code':code, 'message':str(exc)})
            # Keep any native partial writes when possible; never rerun a solver.
            try:
                api.app.save()
            except Exception as save_error:
                case['errors'].append({'code':'circuit_study_save_failed', 'message':str(save_error)})
        store_case(batch, case)
        report['cases'].append({'case_id':case_id, 'status':case['status'], 'parameters':case['parameters']})
        if case['status'] != 'succeeded':
            report['status'] = case['status']
            report['errors'].extend(case['errors'])
            break
    else:
        report['status'] = 'succeeded'
    finish_archive(batch, report['status'])
    return report
