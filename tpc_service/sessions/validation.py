"""Pure input checks, before queue acceptance or starting a native process."""
import hashlib
from pathlib import Path

from tpc_service.errors import ServiceError
from .store import identifier
from .schematic_recovery import OPERATION as SCHEMATIC_RECOVERY


def validate(operation, params):
    def require(condition, message):
        if not condition:
            raise ServiceError('invalid_session_argument', message)
    if operation in ('start', 'close'):
        require(not params, 'start/close take no params')
        return
    if operation == SCHEMATIC_RECOVERY:
        from .schematic_recovery import validate_options
        validate_options(params)
        return
    if operation == 'accept_saved_baseline':
        from .saved_baseline import validate as validate_baseline
        try:
            validate_baseline(params)
        except (ValueError, TypeError, KeyError, OSError) as exc:
            raise ServiceError('invalid_session_argument', str(exc)) from exc
        return
    identifier(params.get('project_id'))
    if operation == 'capture_failed_static':
        from .static_fenced_recovery import validate as validate_static_capture
        try:
            validate_static_capture(params)
        except (ValueError, TypeError, KeyError) as exc:
            raise ServiceError('invalid_session_argument', str(exc)) from exc
    if operation in ('complete_failed_static_task', 'inspect_failed_static_task'):
        from .static_fenced_recovery import validate_completion
        try:
            validate_completion(params)
            if operation == 'inspect_failed_static_task' and params['expected_task'] != {}:
                raise ValueError('Inspection requires an empty expected task')
        except (ValueError, TypeError, KeyError) as exc:
            raise ServiceError('invalid_session_argument', str(exc)) from exc
    if operation == 'prepare_static_sp':
        require(set(params) == {'project_id', 'expected_digest', 'confirm_idle', 'spec'} and params.get('confirm_idle') is True,
                'Exact saved identity, static specification and idle assertion required')
        digest = params.get('expected_digest')
        require(isinstance(digest, str) and len(digest) == 64 and all(c in '0123456789abcdef' for c in digest),
                'Expected saved SHA256 required')
        from cst_solver.circuit.static_sp import validate_prepare_spec
        try:
            validate_prepare_spec(params['spec'])
        except (ValueError, TypeError, KeyError) as exc:
            raise ServiceError('invalid_session_argument', str(exc)) from exc
    if operation in ('configure_exploratory_linear_sp', 'run_exploratory_linear_sp'):
        from .linear_sp import validate_setup, validate_solve
        try:
            (validate_setup if operation == 'configure_exploratory_linear_sp' else validate_solve)(params)
        except (ValueError, TypeError, KeyError, OSError) as exc:
            raise ServiceError('invalid_session_argument', str(exc)) from exc
    if operation == 'prepare_exploratory_sp_network':
        from .linear_sp import network_options
        try:
            network_options(params)
        except (ValueError, TypeError, KeyError, OSError) as exc:
            raise ServiceError('invalid_session_argument', str(exc)) from exc
    if operation == 'prepare_hb_embedded_network':
        from cst_automation.embedded_network import validate as validate_embedded
        try:
            validate_embedded(params)
        except (ValueError, TypeError, KeyError, OSError) as exc:
            raise ServiceError('invalid_session_argument', str(exc)) from exc
    if operation == 'qualify_saved_em':
        from cst_automation.em_qualification import validate as validate_qualification
        try:
            validate_qualification(params)
        except (ValueError, TypeError, KeyError) as exc:
            raise ServiceError('invalid_session_argument', str(exc)) from exc
    if operation == 'qualify_exploratory_em':
        from cst_automation.em_qualification import validate_exploratory
        try:
            validate_exploratory(params)
        except (ValueError, TypeError, KeyError) as exc:
            raise ServiceError('invalid_session_argument', str(exc)) from exc
    if operation in ('fit_em_network', 'update_hb_network'):
        from cst_automation.em_network import validate as validate_network
        try:
            validate_network(operation, params)
        except (ValueError, TypeError, KeyError, OSError) as exc:
            raise ServiceError('invalid_session_argument', str(exc)) from exc
    if operation == 'accept_workflow_evidence':
        require(set(params) == {'project_id', 'em_job_id', 'report_path'}, 'Exact evidence arguments required')
        identifier(params.get('em_job_id'))
        require(isinstance(params.get('report_path'), str) and Path(params['report_path']).is_absolute(),
                'Absolute evidence report path required')
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
        require(not set(params) - {'project_id', 'depends_on', 'retire', 'expected_digest', 'confirm_idle', 'review_note'},
                'Unsupported close_project option')
        require(type(params.get('retire', False)) is bool, 'retire must be boolean')
        if params.get('retire'):
            value = params.get('expected_digest')
            require(isinstance(value, str) and len(value) == 64 and all(c in '0123456789abcdef' for c in value),
                    'Explicit saved expected_digest required for retirement')
            require(params.get('confirm_idle') is True, 'Retirement requires caller-confirmed idle')
            require(isinstance(params.get('review_note'), str) and 0 < len(params['review_note'].strip()) <= 1000,
                    'Explicit bounded retirement review_note required')
        else:
            require(not set(params) & {'expected_digest', 'confirm_idle', 'review_note'},
                    'Retirement review fields require retire=true')
    if operation in ('create_project', 'import_project', 'adopt_project'):
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
        if 'working_path' in params or 'authorize_working_path' in params:
            from .formal_paths import working_path
            working_path(Path.cwd(), params)
        if operation == 'adopt_project':
            require('working_path' in params, 'Explicit working_path required for adoption')
            value = params.get('expected_digest')
            require(isinstance(value, str) and len(value) == 64 and all(c in '0123456789abcdef' for c in value),
                    'Explicit saved expected_digest required')
            require(isinstance(params.get('review_note'), str) and 0 < len(params['review_note'].strip()) <= 1000,
                    'Explicit bounded review_note required for adoption')
    if operation == 'reload_project':
        value = params.get('expected_digest')
        require(isinstance(value, str) and len(value) == 64 and all(c in '0123456789abcdef' for c in value), 'Explicit saved expected_digest required')
    if operation == 'history':
        require(params.get('domain', 'model3d') in ('model3d', 'schematic'), 'history domain must be model3d or schematic')
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
        if params['settings'].get('operation') == 'read_sp_impedances':
            settings = params['settings']
            require(params.get('kind') == 'build' and set(settings) == {'operation', 'task_name', 'ports', 'confirm_idle'}
                    and settings.get('confirm_idle') is True, 'Explicit owned idle SP query required')
            name, ports = settings.get('task_name'), settings.get('ports')
            require(isinstance(name, str) and bool(name.strip()) and len(name) <= 512
                    and not any(c in name for c in '\r\n\x00'), 'Invalid SP task')
            require(isinstance(ports, list) and 1 <= len(ports) <= 128
                    and all(isinstance(p, str) and p.strip() and len(p) <= 512 and
                            not any(c in p for c in '\r\n\x00') for p in ports)
                    and len(set(ports)) == len(ports), 'Unique bounded SP ports required')
        from cst_automation.task_disable import is_request, normalize
        if is_request(operation, params):
            require(params.get('kind') == 'build', 'Task disable requires explicit build kind')
            try:
                normalize(params['settings'])
            except (ValueError, TypeError) as exc:
                raise ServiceError('invalid_session_argument', str(exc)) from exc
    depends = params.get('depends_on', [])
    require(isinstance(depends, list) and all(isinstance(s, str) and s for s in depends),
            'depends_on must list predecessor operation IDs')
