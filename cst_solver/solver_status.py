"""Small SDK-only native status queries on an already-owned 3D project."""
import json
from datetime import datetime, timezone
from pathlib import Path

CAPABILITY = 'native-solver-status-v1'


def _json_safe(value):
    try:
        json.dumps(value, allow_nan=False)
    except (TypeError, ValueError, OverflowError):
        return {'unserializable_type': type(value).__name__, 'repr': repr(value)}
    return value


def read_native_solver_status(app, *, expected_project):
    """Read three documented SDK methods without opening or changing a project.

    The owning caller must supply the actual open project and SDK thread. No
    result proves all engines idle, Direct selection, or a completed solve.
    """
    expected = Path(expected_project)
    if not expected.is_absolute() or Path(app.cst_file.filename()).resolve() != expected.resolve():
        raise ValueError('Owned native project identity differs')
    project = str(expected.resolve())
    model = app.cst_file.model3d
    checks = {
        'active_solver_name': ('get_active_solver_name', lambda v: isinstance(v, str) and bool(v.strip())),
        'solver_running': ('is_solver_running', lambda v: type(v) is bool),
        'solver_run_info': ('get_solver_run_info', lambda v: isinstance(v, dict) and bool(v)),
    }
    fields = {}
    for key, (method, valid) in checks.items():
        row = {'source': 'cst.interface.Model3D.' + method, 'project': project, 'object': 'model3d',
               'observed_at': datetime.now(timezone.utc).isoformat(), 'status': 'unsupported',
               'raw': None, 'value': None, 'error': None}
        try:
            getter = getattr(model, method, None)
            if not callable(getter):
                row['error'] = 'Native SDK method unavailable'
            else:
                value = getter(timeout=5)
                row['raw'] = _json_safe(value)
                if value is None or value == '' or value == {}:
                    row['status'] = 'empty'
                elif not valid(value) or row['raw'] != value:
                    row['status'] = 'invalid'
                    row['error'] = 'Unexpected native return type or non-serializable value'
                else:
                    row.update(status='read', value=value)
        except Exception as exc:
            row.update(status='error', error=f'{type(exc).__name__}: {exc}')
        row['finished_at'] = datetime.now(timezone.utc).isoformat()
        fields[key] = row
    if Path(app.cst_file.filename()).resolve() != expected.resolve():
        raise ValueError('Owned project identity changed during native status read')
    missing = {key: {'status': 'unsupported', 'source': None, 'project': project,
                     'object': 'model3d', 'observed_at': None, 'raw': None, 'value': None,
                     'error': 'No independently verified getter or complete enumeration'}
               for key in ('active_mesh_type', 'direct_solver', 'residual_accuracy', 'local_mesh',
                           'adaptation_settings', 'complete_frequency_table')}
    return {'project': project, 'fields': fields, 'unavailable_settings': missing,
            'direct_solver_verified': False, 'whole_sequence_idle': 'unknown',
            'run_identity_verified': False, 'solver_verified': False}
