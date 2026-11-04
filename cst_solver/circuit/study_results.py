"""Append-only per-case snapshots, parameter queries and native readback checks."""
import cmath
import csv
import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from cst_automation.circuit_studies import segment
from .results import CircuitResult

COMPONENTS = ('magnitude', 'real', 'imag', 'phase')


def _json(data):
    return json.dumps(data, ensure_ascii=False, allow_nan=False, sort_keys=True, indent=2)


def _write_manifest(batch, manifest):
    temporary = batch / ('manifest-' + uuid4().hex + '.tmp')
    temporary.write_text(_json(manifest), encoding='utf-8')
    temporary.replace(batch / 'study.json')


def create_archive(project_path, spec):
    project = Path(project_path).resolve()
    batch_id = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S') + '_' + uuid4().hex
    batch = project.with_suffix('') / 'Result' / 'DS' / 'Studies' / segment(spec['name']) / batch_id
    batch.mkdir(parents=True, exist_ok=False)
    _write_manifest(batch, {'schema_version': 1, 'project_path': str(project), 'batch_id': batch_id,
        'spec': spec, 'status': 'running', 'cases': [], 'reopen_verified': False})
    return batch


def store_case(batch_path, case):
    """Write a case once, then publish its digest in this batch's manifest."""
    batch = Path(batch_path).resolve()
    cid = segment(case['case_id'])
    payload = _json(case)  # Validate serializability before creating anything.
    manifest = json.loads((batch / 'study.json').read_text(encoding='utf-8'))
    folder = batch / cid
    folder.mkdir(exist_ok=False)
    (folder / 'case.json').write_text(payload, encoding='utf-8')
    for name, curve in case.get('curves', {}).items():
        segment(name)
        with (folder / (name + '.csv')).open('x', encoding='utf-8-sig', newline='') as handle:
            writer = csv.writer(handle)
            writer.writerow(['x [' + curve['x_unit'] + ']', 'y_real [' + curve['y_unit'] + ']', 'y_imag [' + curve['y_unit'] + ']'])
            writer.writerows((x, y[0], y[1]) for x, y in zip(curve['x'], curve['y']))
    manifest['cases'].append({'case_id': cid, 'parameters': case['parameters'], 'status': case['status'],
        'sha256': hashlib.sha256((folder / 'case.json').read_bytes()).hexdigest()})
    _write_manifest(batch, manifest)


def finish_archive(batch_path, status):
    batch = Path(batch_path)
    manifest = json.loads((batch / 'study.json').read_text(encoding='utf-8'))
    manifest['status'] = status
    _write_manifest(batch, manifest)


def component_values(curve, component):
    if component not in COMPONENTS:
        raise ValueError('Unsupported component: ' + str(component))
    ys = curve['y']
    if component == 'magnitude':
        return [abs(y) for y in ys], curve['y_unit']
    if component == 'real':
        return [y.real for y in ys], curve['y_unit']
    if component == 'imag':
        return [y.imag for y in ys], curve['y_unit']
    return [math.degrees(cmath.phase(y)) for y in ys], 'deg'


class StudyResult:
    """Read archived history; source run 0 is metadata, never dereferenced here."""
    def __init__(self, batch_path):
        self.path = Path(batch_path).resolve()
        self.manifest = json.loads((self.path / 'study.json').read_text(encoding='utf-8'))

    def list_cases(self, parameters=None):
        parameters = {} if parameters is None else parameters
        if not isinstance(parameters, dict) or parameters.keys() - self.manifest['spec']['parameters'].keys():
            raise ValueError('Unknown parameter filter')
        return [dict(row) for row in self.manifest['cases']
                if all(row['parameters'].get(k) == v for k, v in parameters.items())]

    def case(self, case_id):
        segment(case_id)
        rows = [r for r in self.manifest['cases'] if r['case_id'] == case_id]
        if len(rows) != 1:
            raise ValueError('Case is missing or ambiguous: ' + case_id)
        path = self.path / case_id / 'case.json'
        if self.path not in path.resolve().parents:
            raise ValueError('Case path escaped its archive')
        payload = path.read_bytes()
        if hashlib.sha256(payload).hexdigest() != rows[0]['sha256']:
            raise ValueError('Case digest mismatch')
        return json.loads(payload)

    def read_curve(self, case_id, result_name):
        segment(result_name)
        case = self.case(case_id)
        if result_name not in case.get('curves', {}):
            raise ValueError('Result is missing from case: ' + result_name)
        curve = dict(case['curves'][result_name])
        curve['y'] = [complex(*y) for y in curve['y']]
        return curve

    def compare(self, result_name, *, parameters=None, component='magnitude'):
        if component not in COMPONENTS:
            raise ValueError('Unsupported component')
        curves, units = [], None
        for row in self.list_cases(parameters):
            if row['status'] != 'succeeded':
                continue
            raw = self.read_curve(row['case_id'], result_name)
            y, unit = component_values(raw, component)
            # Source units must agree even when converting phases to degrees.
            current = (raw['x_unit'], raw['y_unit'])
            if units is not None and units != current:
                raise ValueError('Cannot compare results with different source units')
            units = current
            curves.append({'case_id': row['case_id'], 'parameters': row['parameters'],
                'x': raw['x'], 'y': y, 'x_unit': raw['x_unit'], 'y_unit': unit})
        return {'result_name': result_name, 'component': component, 'curves': curves}

    def verify_project(self):
        """Read saved native summary leaves; does not close/reopen an owning session."""
        report = {'saved_readback_verified': False, 'reopen_verified': False, 'errors': [], 'checked': 0}
        try:
            reader = CircuitResult(self.manifest['project_path'])
            for row in self.list_cases():
                if row['status'] != 'succeeded':
                    continue
                case = self.case(row['case_id'])
                expected_count = len(case['curves']) * len(COMPONENTS)
                if len(case['native_curves']) != expected_count:
                    raise ValueError('Native summary leaves are incomplete')
                for native in case['native_curves']:
                    raw = self.read_curve(row['case_id'], native['result_name'])
                    ys, unit = component_values(raw, native['component'])
                    actual = reader.read_curve(native['tree_path'], run_id=0)
                    if actual['x_unit'] != raw['x_unit'] or actual['y_unit'] != unit:
                        raise ValueError('Native summary unit mismatch')
                    if len(actual['x']) != len(raw['x']) or len(actual['y']) != len(ys):
                        raise ValueError('Native summary sample count mismatch')
                    if (not all(math.isclose(a, b, rel_tol=1e-10, abs_tol=1e-12) for a,b in zip(actual['x'], raw['x']))
                        or not all(abs(a-complex(b)) <= 1e-12 + 1e-10*abs(b) for a,b in zip(actual['y'], ys))):
                        raise ValueError('Native summary sample mismatch')
                    report['checked'] += 1
            report['saved_readback_verified'] = report['checked'] > 0
        except Exception as exc:
            report['errors'].append(str(exc))
        return report
