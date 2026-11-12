"""Verify already-read two-port static SP curves without claiming a solver run."""
import math
from pathlib import Path


def verify_curves(curves, *, task_name, run_id, project_path, parameters,
                  frequency_unit, fmin, fmax, samples, allow_current=False):
    if (not isinstance(curves, dict) or set(curves) != {'11', '12', '21', '22'}
            or not isinstance(task_name, str) or not task_name or '\\' in task_name
            or type(run_id) is not int or run_id < 0 or (run_id == 0 and allow_current is not True)
            or not isinstance(parameters, dict)
            or frequency_unit not in ('Hz', 'kHz', 'MHz', 'GHz')
            or type(samples) is not int or samples < 2
            or any(type(v) not in (int, float) or not math.isfinite(v) for v in (fmin, fmax))
            or not 0 <= fmin < fmax):
        raise ValueError('Explicit four-curve identity and finite grid required')
    project = Path(project_path).resolve()
    normalized = {}
    for key, curve in curves.items():
        if not isinstance(curve, dict):
            raise ValueError('Each curve must include native identity and data')
        prefix = (task_name + '\\', 'Tasks\\' + task_name + '\\')
        path = curve.get('tree_path', '')
        if (not isinstance(path, str) or not path.startswith(prefix)
                or not path.endswith('\\S-Parameters\\S' + key[0] + ',' + key[1])
                or curve.get('run_id') != run_id or curve.get('domain') != 'schematic'
                or Path(curve.get('project_path', '')).resolve() != project
                or curve.get('parameters') != parameters or curve.get('x_unit') != frequency_unit
                or curve.get('y_unit') != '1'):
            raise ValueError('Curve identity, quantity or units differ')
        x, y = curve.get('x'), curve.get('y')
        if not isinstance(x, (list, tuple)) or not isinstance(y, (list, tuple)) or len(x) != samples or len(y) != samples:
            raise ValueError('Sample coverage differs')
        values = []
        for i, (frequency, value) in enumerate(zip(x, y)):
            if type(frequency) not in (int, float) or not math.isfinite(frequency):
                raise ValueError('Invalid frequency')
            target = fmin + (fmax - fmin) * i / (samples - 1)
            if not math.isclose(frequency, target, rel_tol=1e-10, abs_tol=1e-12):
                raise ValueError('Frequency grid differs')
            try:
                value = complex(value)
            except (TypeError, ValueError, OverflowError) as exc:
                raise ValueError('Invalid complex value') from exc
            if not math.isfinite(value.real) or not math.isfinite(value.imag):
                raise ValueError('Nonfinite complex value')
            values.append(value)
        normalized[key] = values
    return {'run_id': run_id, 'project_path': str(project), 'task_name': task_name,
            'frequency_unit': frequency_unit, 'samples': samples,
            'max_s12_s21_difference': max(abs(a-b) for a, b in zip(normalized['12'], normalized['21'])),
            'fresh_execution_verified': False}
