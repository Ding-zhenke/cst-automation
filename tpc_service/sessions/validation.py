"""Pure input checks, before queue acceptance or starting a native process."""
import hashlib
from pathlib import Path

from tpc_service.errors import ServiceError
from .store import identifier


def validate(operation, params):
    def require(condition, message):
        if not condition:
            raise ServiceError('invalid_session_argument', message)
    if operation in ('start', 'close'):
        require(not params, 'start/close take no params')
        return
    identifier(params.get('project_id'))
    if operation in ('create_project', 'import_project'):
        require(params.get('project_type', 'MWS') in ('MWS', 'DS'), 'project_type must be MWS or DS')
        if operation == 'import_project':
            path = params.get('source_path')
            require(isinstance(path, str) and Path(path).is_absolute() and
                    Path(path).suffix.lower() in ('.cst', '.prj') and Path(path).is_file(),
                    'Existing absolute CST source_path required')
    if operation == 'history':
        code = params.get('vba')
        require(isinstance(code, str) and 0 < len(code) <= 1_000_000, 'Bounded VBA required')
        require(params.get('preview_digest') == hashlib.sha256(code.encode()).hexdigest(),
                'Reviewed preview digest required')
        identifier(params.get('stage_id'))
        require(isinstance(params.get('name'), str) and bool(params['name'].strip()), 'History name required')
    if operation == 'set_parameters':
        values = params.get('values')
        require(isinstance(values, dict) and bool(values), 'Nonempty values required')
        from cst_solver.expressions import validate_parameter_name
        for name, value in values.items():
            require(validate_parameter_name(name) == name, 'Invalid parameter name')
            require(type(value) in (int, float, str), 'Parameter values must be numbers or expressions')
    if operation == 'circuit':
        require(params.get('kind', 'build') in ('build', 'solve', 'study') and
                isinstance(params.get('settings'), dict), 'Explicit circuit kind/settings required')
    depends = params.get('depends_on', [])
    require(isinstance(depends, list) and all(isinstance(s, str) and s for s in depends),
            'depends_on must list predecessor operation IDs')
