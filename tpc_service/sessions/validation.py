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
    if operation == 'configure_sweep':
        from cst_solver.simulation.sweep import sweep_code
        identifier(params.get('stage_id'))
        try:
            sweep_code(params.get('sequence_name'), params.get('parameters'), params.get('replace_all', False))
        except (TypeError, ValueError) as exc:
            raise ServiceError('invalid_session_argument', str(exc)) from exc
    if operation == 'inspect':
        from .inspection import validate_options
        validate_options(params)
    if operation == 'close_project':
        require(not set(params) - {'project_id', 'depends_on'}, 'close_project takes only project_id and depends_on')
    if operation in ('create_project', 'import_project'):
        require(params.get('project_type', 'MWS') in ('MWS', 'DS'), 'project_type must be MWS or DS')
        require(params.get('lifetime', 'working') in ('working', 'temporary'), 'Invalid project lifetime')
        if 'copy_reason' in params:
            require(isinstance(params['copy_reason'], str) and 0 < len(params['copy_reason'].strip()) <= 1000,
                    'Explicit nonempty copy_reason required')
        if operation == 'import_project':
            path = params.get('source_path')
            require(isinstance(path, str) and Path(path).is_absolute() and
                    Path(path).suffix.lower() in ('.cst', '.prj') and Path(path).is_file(),
                    'Existing absolute CST source_path required')
    if operation == 'history':
        code = params.get('vba')
        require(isinstance(code, str) and 0 < len(code) <= 1_000_000, 'Bounded VBA required')
        if params.get('domain', 'model3d') == 'model3d':
            import re
            require(not re.search(r'(?im)(?:^|:)\s*(?:Open\s+[^\r\n]+\s+For\s+(?:Output|Append|Binary)|(?:Print|Write|Close)\s*#)', code),
                    'File-writing probes do not belong in replay history; use inspect and write reports in Python')
        require(params.get('preview_digest') == hashlib.sha256(code.encode()).hexdigest(),
                'Reviewed preview digest required')
        identifier(params.get('stage_id'))
        require(isinstance(params.get('name'), str) and bool(params['name'].strip()), 'History name required')
    if operation == 'model_api':
        import json
        from .model_api import validate_calls
        calls = params.get('calls')
        validate_calls(calls)
        identifier(params.get('stage_id'))
        require(params.get('preview_digest') == hashlib.sha256(
            json.dumps(calls,sort_keys=True,ensure_ascii=False).encode()).hexdigest(),
            'Reviewed API call digest required')
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
