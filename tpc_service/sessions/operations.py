"""Bounded operation registry. No eval, dynamic imports, Python scripts or shell."""
import hashlib
from pathlib import Path

from tpc_service.errors import ServiceError
from .native import file_digest
from .store import contained, identifier, lock, write
from .diagnostics import exception_diagnostics, exception_repr, mark_stage
from .schematic_recovery import OPERATION as SCHEMATIC_RECOVERY, is_native_vba_response


def execute(runtime, job):
    mark_stage(runtime, 'operation.dispatch')
    operation, params = job['operation'], job['params']
    from . import workflow
    try:
        if operation == 'model_api':
            from .model_api import validate_calls, uses_hf_tet_order_controls, HF_TET_ORDER_CAPABILITY
            validate_calls(params['calls'])
            from cst_automation.settings_history import CAPABILITY as HISTORY_CAPABILITY, uses_settings_history
            if (uses_settings_history(params['calls'])
                    and HISTORY_CAPABILITY not in runtime.state().get('worker_capabilities', [])):
                raise ServiceError('workflow_worker_upgrade_required', 'Content-bound settings history requires a compatible execution worker')
            from .model_api import uses_hf_tet_lf_controls
            from cst_automation.fd_linear import LF_CAPABILITY
            if (uses_hf_tet_lf_controls(params['calls'])
                    and LF_CAPABILITY not in runtime.state().get('worker_capabilities', [])):
                raise ServiceError('workflow_worker_upgrade_required', 'HF Tet LF controls require a compatible execution worker')
            from cst_automation.discrete_face_port import CAPABILITY as FACE_CAPABILITY, METHOD as FACE_METHOD
            if (any(c['method'] == FACE_METHOD for c in params['calls'])
                    and FACE_CAPABILITY not in runtime.state().get('worker_capabilities', [])):
                raise ServiceError('workflow_worker_upgrade_required', 'Picked face ports require compatible execution worker')
            if (uses_hf_tet_order_controls(params['calls'])
                    and HF_TET_ORDER_CAPABILITY not in runtime.state().get('worker_capabilities', [])):
                raise ServiceError('workflow_worker_upgrade_required', 'HF Tet order controls require compatible execution worker')
        workflow.preflight(runtime.folder, runtime.state(), operation, params, job=job)
    except ServiceError:
        job['workflow_preflight_rejected'] = True
        raise
    return _execute_operation(runtime, job)


def _execute_operation(runtime, job):
    """Native dispatch implementation; callers must use the guarded execute entry."""
    from . import workflow
    operation, params = job['operation'], job['params']
    if operation == 'accept_saved_baseline':
        from .saved_baseline import execute as accept_baseline
        return accept_baseline(runtime, job)
    if operation == 'qualify_saved_em':
        from .em_qualification import execute as qualify_saved
        return qualify_saved(runtime, job)
    if operation == 'qualify_exploratory_em':
        from .exploratory_em import execute as qualify_exploratory
        return qualify_exploratory(runtime, job)
    if operation == 'accept_workflow_evidence':
        state = runtime.state()
        project = state['projects'][params['project_id']]
        evidence = workflow.evidence_report(runtime.folder, project, params)
        project['workflow']['evidence'] = evidence
        runtime.update(projects=state['projects'])
        return {'accepted': True, 'revision': project['workflow']['revision'], 'started_cst': False}
    if operation == SCHEMATIC_RECOVERY:
        from .schematic_recovery import recover
        return recover(runtime, job)
    if params.get('depends_on'):
        from .job_index import JobIndex
        with lock(runtime.folder / 'state.lock'):
            index = JobIndex.load(runtime.folder)
            for predecessor in params['depends_on']:
                receipt = index.match(operation_id=predecessor)
                if not receipt or receipt['status'] != 'succeeded':
                    raise ServiceError('session_dependency_incomplete', 'Required predecessor stage is not confirmed', predecessor=predecessor)
    if operation == 'close':
        # If a worker was lost during a mutation, closing must not silently discard that state.
        if runtime.state().get('uncertain_jobs') or runtime.state()['launch_intent'] or runtime.state()['status'] == 'needs_reconcile':
            raise ServiceError('session_needs_reconcile', 'Resolve unknown work before closing its environment')
        state = runtime.state()
        if state['environment'] is not None:
            if runtime.backend == 'cst':
                from .store import alive
                if not alive(state['environment']):
                    return {'closed': True, 'saved': False, 'already_exited': True, 'backend': 'cst'}
            app = runtime.environment()
            for project_id, record in state['projects'].items():
                if record.get('tab_closed'):
                    continue
                app, _ = runtime.project(project_id)
                runtime.save(app, project_id)
            # Session layer owns this recorded DE even after exact attach; low-level attach.close is borrowed.
            if runtime.backend == 'cst':
                from .store import alive
                if not alive(runtime.state()['environment']):
                    raise ServiceError('session_environment_mismatch', 'Cannot close unverified DE')
            app.project.close()
        return {'closed': True, 'saved': True, 'backend': runtime.backend}
    if operation == 'inspect':
        state = runtime.state()
        if params.get('read_only_review') is True:
            from .read_review import inspect_saved_geometry
            return inspect_saved_geometry(runtime, job)
        if state['status'] == 'needs_reconcile':
            return {'backend': runtime.backend, 'state': 'needs_reconcile', 'projects': state['projects'],
                    'uncertain_jobs': state.get('uncertain_jobs', []), 'readback_verified': False}
        app, record = runtime.project(params['project_id'])
        result = {'project': record, 'backend': runtime.backend, 'readback_verified': False, 'solver_verified': False}
        if runtime.backend == 'cst':
            result['messages'] = [str(m) for m in app.get_messages()]
            if params.get('native_readback'):
                from .inspection import inspect_native
                result['native_readback'] = inspect_native(app, params)
                result['messages'].extend(str(m) for m in app.get_messages())
                result['readback_verified'] = not result['native_readback']['errors'] and not result['messages']
        else:
            result['offline_model'] = app.cst_file
            if params.get('native_readback'):
                result['native_readback'] = {'native_executed': False, 'errors': ['Native queries require CST']}
        return result
    if operation == 'close_project':
        from .validation import validate
        validate(operation, params)
        if params.get('retire') is True:
            from .retirement import retire_closed_project
            return retire_closed_project(runtime, job)
        project_id = params['project_id']
        state = runtime.state()
        record = state['projects'].get(project_id) or state.get('retired_projects', {}).get(project_id)
        if not record:
            raise ServiceError('project_not_registered', 'Cannot close an unregistered project')
        if record.get('tab_closed'):
            return dict(project_id=project_id, tab_closed=True, already_closed=True,
                        retired=project_id in state.get('retired_projects', {}),
                        saved=record.get('saved', False), environment_closed=False, backend=runtime.backend)
        app, record = runtime.project(project_id)
        record = runtime.save(app, project_id)
        if runtime.backend == 'cst':
            app.cst_file.close()
            from .project_lifecycle import path_key
            if path_key(record['path']) in {path_key(p) for p in app.project.list_open_projects()}:
                raise ServiceError('session_project_close_unverified', 'Owned project is still open after close', project_id=project_id)
        runtime.handles.pop(project_id, None)
        state = runtime.state()
        state['projects'][project_id].update(tab_closed=True)
        retired = record.get('lifetime') == 'temporary'
        if retired:
            state.setdefault('retired_projects', {})[project_id] = state['projects'].pop(project_id)
        runtime.update(projects=state['projects'], retired_projects=state.get('retired_projects', {}))
        return dict(project_id=project_id, tab_closed=True, saved=True,
                    retired=retired, environment_closed=False, backend=runtime.backend)
    if operation == 'start':
        runtime.environment()
        return {'environment': runtime.state()['environment'], 'backend': runtime.backend}
    if operation in ('create_project', 'import_project', 'adopt_project'):
        project_id = identifier(params['project_id'])
        state = runtime.state()
        if project_id in state['projects']:
            raise ServiceError('project_exists', 'Project already registered; use the original stage/request')
        project_type = params.get('project_type', 'MWS')
        if project_type not in ('MWS', 'DS'):
            raise ServiceError('invalid_session_argument', 'project_type must be MWS or DS')
        from .formal_paths import check_destination
        path = check_destination(runtime.folder, operation, params)
        if operation == 'adopt_project':
            # Open the reviewed saved file before registering it, without save/copy.
            # A lost native-open receipt is reconciled through the original job.
            app = runtime.environment()
            app.open(str(path))
            if file_digest(path) != params['expected_digest']:
                raise ServiceError('session_digest_mismatch', 'Saved baseline changed during adoption')
            record = {'project_id': project_id, 'path': str(path), 'source_path': None,
                      'saved': True, 'saved_digest': params['expected_digest'],
                      'lifetime': params.get('lifetime', 'working'), 'copy_reason': None,
                      'path_authorization': {'working_path': str(path), 'operation': operation},
                      'adoption_review': {'review_note': params['review_note'],
                                          'expected_digest': params['expected_digest']}}
            state = runtime.state()
            state['projects'][project_id] = record
            runtime.update(projects=state['projects'])
            runtime.handles[project_id] = app.cst_file
            return {'project': record, 'adopted': True, 'saved': False, 'backend': runtime.backend,
                    'readback_verified': False, 'solver_verified': False}
        source = None
        if operation == 'import_project':
            source = str(Path(params['source_path']).resolve())
            if not Path(source).is_file():
                raise ServiceError('project_not_found', 'Source project missing')
            from tpc_service.registry import copy_project
            source_folder = Path(source).with_suffix('').resolve()
            if source_folder == path.parent or source_folder in path.parents:
                raise ServiceError('workdir_escape', 'Import destination cannot be inside source results directory')
            copy_project(source, str(path))
        # Restore only the pre-existing projects. The just-copied import is an
        # initial intent, not a missing saved tab requiring historical review.
        app = runtime.environment()
        state = runtime.state()
        state['projects'][project_id] = {'project_id': project_id, 'path': str(path),
                                          'source_path': source, 'saved': False,
                                          'lifetime': params.get('lifetime', 'working'),
                                          'copy_reason': params.get('copy_reason')}
        if 'working_path' in params:
            state['projects'][project_id]['path_authorization'] = {
                'working_path': str(path), 'operation': operation}
        runtime.update(projects=state['projects'])
        path.parent.mkdir(parents=True, exist_ok=True)
        if source:
            app.open(str(path))
        elif project_type == 'DS':
            app.new_circuit_project()
        else:
            app.new_project()
        runtime.handles[project_id] = app.cst_file
        record = runtime.save(app, project_id)
        return {'project': record, 'saved': True, 'backend': runtime.backend,
                'readback_verified': False, 'solver_verified': False}
    if operation == 'circuit' and params.get('settings', {}).get('operation') == 'read_run_parameters':
        # A read probe must not trigger Runtime.project/environment recovery,
        # opening a closed tab, attaching, or creating another environment.
        from .store import alive
        state = runtime.state()
        record = state.get('projects', {}).get(params['project_id'])
        app = getattr(runtime, 'app', None)
        handle = getattr(runtime, 'handles', {}).get(params['project_id'])
        if (runtime.backend != 'cst' or not record or record.get('tab_closed')
                or app is None or handle is None or not alive(state.get('environment'))):
            raise ServiceError('session_query_requires_open_project',
                               'Read query requires the existing live environment and cached owned project')
        runtime.check_saved(record)
        app.cst_file = handle
        return circuit(runtime, app, record, params)
    mark_stage(runtime, 'project.acquire')
    app, record = runtime.project(params['project_id'])
    contract = record.get('workflow')
    if operation == 'prepare_exploratory_sp_network':
        from .linear_sp import execute_network
        return execute_network(runtime, job, app)
    if operation == 'configure_exploratory_linear_sp':
        from .linear_sp import execute_setup
        return execute_setup(runtime, job, app)
    if operation == 'run_exploratory_linear_sp':
        from .linear_sp import execute_sp_solve
        return execute_sp_solve(runtime, job, app)
    if operation == 'prepare_hb_embedded_network':
        from .embedded_network import execute as execute_embedded
        return execute_embedded(runtime, job, app)
    if operation in ('fit_em_network', 'update_hb_network'):
        from .em_network import execute as execute_network
        return execute_network(runtime, job, app)
    if contract and operation == 'circuit' and params.get('kind') == 'solve':
        from .em_network import check_hb
        check_hb(runtime.folder, record, app)
    if contract and (operation == 'solve' or (operation == 'circuit' and params.get('kind') == 'solve')):
        workflow.live_checks(app, contract, 'em' if operation == 'solve' else 'hb')
    if contract:
        workflow.invalidate(runtime, job)
    mark_stage(runtime, 'operation.' + operation)
    if operation == 'reload_project':
        reviewed = runtime.state().get('last_resolution', {})
        expected = params.get('expected_digest')
        project_id = params['project_id']
        if (not reviewed.get('human_reviewed') or not expected
                or reviewed.get('project_digests', {}).get(project_id) != expected
                or record.get('saved_digest') != expected or file_digest(record['path']) != expected):
            raise ServiceError('session_review_required', 'Reload requires a matching reviewed saved baseline')
        if runtime.backend != 'cst':
            raise ServiceError('offline_reload_unavailable', 'Native project reload requires CST')
        app.cst_file.close()
        runtime.handles.pop(project_id, None)
        app.open(record['path'])
        runtime.handles[project_id] = app.cst_file
        if file_digest(record['path']) != expected:
            raise ServiceError('session_digest_mismatch', 'Saved baseline changed during native reload')
        return {'reloaded': True, 'saved': False, 'project_id': project_id,
                'saved_digest': expected, 'backend': 'cst', 'solver_verified': False,
                'readback_verified': False}
    api_result = {}
    if operation == 'configure_sweep':
        if runtime.backend == 'fake':
            app.cst_file['sweep'] = {k: params[k] for k in ('sequence_name', 'parameters')}
        else:
            app.configure_sweep(params['sequence_name'], params['parameters'], params.get('replace_all', False))
    elif operation == 'model_api':
        from .model_api import dispatch, validate_calls
        validate_calls(params['calls'])
        for call in params['calls']:
            if call['method'] == 'import_step':
                from inspect import signature
                from cst_solver import setup as CstSetup
                bound = signature(CstSetup.import_step).bind(None, *call.get('args', []), **call.get('kwargs', {}))
                source = Path(bound.arguments['filename']).resolve(strict=True)
                project = runtime.state()['projects'][params['project_id']]
                parent = Path(project['path']).resolve().parent
                if source.parent != parent:
                    raise ServiceError('invalid_session_argument', 'STEP source must be in the registered project directory')
        if runtime.backend == 'fake':
            app.cst_file.setdefault('api_calls', []).extend(params['calls'])
            api_result = {'python_api_calls':len(params['calls']), 'native_executed':False}
        else:
            api_result = dispatch(app, params['calls'])
    elif operation == 'history':
        mark_stage(runtime, 'history.validate_request')
        domain = params.get('domain', 'model3d')
        if domain not in ('model3d', 'schematic'):
            raise ServiceError('invalid_session_argument', 'history domain must be model3d or schematic')
        code = params['vba']
        if not isinstance(code, str) or not code.strip() or len(code) > 1_000_000:
            raise ServiceError('invalid_session_argument', 'Explicit bounded VBA history required')
        checksum = hashlib.sha256(code.encode()).hexdigest()
        if params.get('preview_digest') != checksum or not params.get('stage_id') or not params.get('name'):
            raise ServiceError('session_preview_required', 'Supply reviewed VBA digest, stage_id and history name')
        if runtime.backend == 'fake':
            key = 'schematic_macros' if domain == 'schematic' else 'history'
            app.cst_file.setdefault(key, []).append({'name': params['name'], 'vba': code})
        elif domain == 'schematic':
            mark_stage(runtime, 'history.submit_schematic')
            try:
                app.cst_file.schematic.execute_vba_code('Sub Main\n' + code + '\nEnd Sub', timeout=None)
            except RuntimeError as exc:
                if not is_native_vba_response(str(exc)):
                    raise
                # Classify before the echoed macro is truncated in the bounded diagnostic.
                raise ServiceError('session_operation_failed', exception_repr(exc),
                                   schematic_call_state='returned_native_vba_error',
                                   diagnostics=exception_diagnostics(exc, runtime, job)) from exc
        else:
            mark_stage(runtime, 'history.submit_model3d')
            app.cst_file.model3d.add_to_history(params['name'], code)
        api_result['domain'] = domain
    elif operation == 'set_parameters':
        values = params['values']
        if not isinstance(values, dict) or not values:
            raise ServiceError('invalid_session_argument', 'Nonempty parameter values required')
        expressions = params.get('expressions', {})
        if (not isinstance(expressions, dict)
                or any(name not in values or not isinstance(text, str)
                       for name, text in expressions.items())):
            raise ServiceError('invalid_session_argument',
                               'expressions must map value keys to description strings')
        if runtime.backend == 'fake':
            app.cst_file['parameters'].update(values)
            app.cst_file.setdefault('parameter_descriptions', {}).update(expressions)
        else:
            for name, value in values.items():
                if name in expressions:
                    app.para(name, value, expression=expressions[name])
                else:
                    app.para(name, value)
    elif operation == 'solve':
        if runtime.backend == 'fake':
            raise ServiceError('offline_solver_unavailable', 'Fake sessions cannot certify a solve')
        result = app.run_checked(project_path=record['path'], note=str(params.get('note', '')))
        saved = runtime.save(app, params['project_id'])
        if result.get('status') != 'succeeded':
            raise ServiceError('session_solve_unverified', 'Solver outcome requires review', outcome=result,
                               project_id=params['project_id'], saved=True, saved_digest=saved.get('saved_digest'),
                               execution_returned=result.get('execution_returned') is True)
        return {'saved': True, 'solver_outcome': result, 'backend': 'cst'}
    elif operation == 'circuit':
        return circuit(runtime, app, record, params)
    else:
        raise ServiceError('unknown_session_operation', 'Unsupported session operation')
    validation = None
    if runtime.backend == 'cst' and not (operation == 'history' and params.get('domain') == 'schematic'):
        mark_stage(runtime, 'model.validate')
        from .model_api import settings_only
        only_settings = operation == 'model_api' and settings_only(params['calls'])
        api_result['settings_only'] = only_settings
        if only_settings:
            validation = app.validate_model(rebuild=False)
            validation.update(validation_scope='settings_message_queue', geometry_verified=False)
        else:
            validation = (app.validate_model(rebuild_mode='parametric')
                          if operation == 'set_parameters' else app.validate_model())
        if validation.get('status') != 'success' or not validation.get('rebuild_ok'):
            if validation.get('rebuild_performed') is True and validation.get('rebuild_returned') is not True:
                raise ServiceError('session_geometry_unverified', 'Rebuild did not return normally; inspect before saving',
                                   validation=validation, project_id=params['project_id'],
                                   saved=False, execution_returned=False)
            # Save partial evidence without permitting subsequent dependent stages.
            saved = runtime.save(app, params['project_id'])
            outcome = dict(project=record['path'], operation=operation, operation_id=job.get('operation_id'),
                           job_id=job.get('job_id'), execution_returned=True, validation_returned=True,
                           validation=validation, saved=True, saved_digest=saved.get('saved_digest'),
                           validation_passed=False, geometry_verified=False)
            raise ServiceError('session_geometry_unverified', 'Rebuild/messages require inspection', validation=validation,
                               project_id=params['project_id'], saved=True, saved_digest=saved.get('saved_digest'),
                               execution_returned=True, geometry_outcome=outcome)
    if runtime.backend == 'cst' and operation == 'model_api':
        from .model_api import verify_replacements
        verify_replacements(app, api_result.get('configuration_receipts', []))
    if runtime.backend == 'cst' and operation == 'set_parameters':
        # Legacy history can contain descriptions; restore metadata after rebuild.
        for name, text in params.get('expressions', {}).items():
            app._set_parameter_description(name, text)
    mark_stage(runtime, 'operation.save')
    record = runtime.save(app, params['project_id'])
    checkpoint = {'job_id': job['job_id'], 'operation_id': job['operation_id'],
                  'fingerprint': job['fingerprint'], 'project_id': params['project_id'],
                  'saved_digest': record['saved_digest'], 'saved': True, 'readback_verified': False,
                  'geometry_validation': validation}
    mark_stage(runtime, 'checkpoint.write')
    write(runtime.folder / 'checkpoints' / (job['job_id'] + '.json'), checkpoint)
    return dict(checkpoint, backend=runtime.backend, solver_verified=False, **api_result)


def circuit(runtime, app, record, params):
    """Reuse existing explicit circuit workflow without its temporary DE lifecycle."""
    from types import SimpleNamespace
    from tpc_service.circuit import register_circuit_handlers
    from .project_lifecycle import path_key

    project_id = record.get('project_id')
    registered = runtime.state().get('projects', {}).get(project_id)
    if (project_id != params.get('project_id') or not registered or
            path_key(record['path']) != path_key(registered['path'])):
        raise ServiceError('session_project_mismatch', 'Circuit project must match the registered session project')
    path = Path(registered['path']).resolve()
    folder = Path(runtime.folder).resolve()
    if path != folder and folder not in path.parents:
        grant = registered.get('path_authorization') or {}
        if (grant.get('operation') not in ('create_project', 'import_project', 'adopt_project') or
                not grant.get('working_path') or path_key(grant['working_path']) != path_key(path)):
            raise ServiceError('session_path_authorization_required', 'Circuit routing requires the exact registered formal path grant')

    class BorrowedApp:
        def __getattr__(self, name):
            return getattr(app, name)

        def close(self):
            pass  # Per-operation release; explicit close_session owns DE lifetime.

    handlers = {}
    service = SimpleNamespace(workdir=str(runtime.folder),
                              register_workflow=lambda name, values, **kw: handlers.update(values))
    register_circuit_handlers(service, app_factory=lambda path: BorrowedApp(), authorized_project_path=str(path), borrowed_project=True)
    kind = params.get('kind', 'build')
    if kind not in handlers:
        raise ServiceError('invalid_session_argument', 'Invalid circuit kind')
    result = handlers[kind](project=record, params=params['settings'], job={'kind': kind}, backend=None)
    if params['settings'].get('operation') == 'register_postprocessing_template':
        # The real facade reopens the same owned project. Never cache its closed
        # predecessor, including when the registration returned partial evidence.
        if app.cst_file is None:
            runtime.handles.pop(record['project_id'], None)
        else:
            runtime.handles[record['project_id']] = app.cst_file
    if Path(record['path']).is_file():
        # Handler may save partial changes; update the fingerprint, but never certify partial work.
        state = runtime.state()
        state['projects'][record['project_id']]['saved_digest'] = file_digest(record['path'])
        runtime.update(projects=state['projects'])
    if not result.get('ok'):
        details = {}
        if kind == 'solve' and params['settings'].get('operation') == 'run_task':
            receipt = result.get('result_summary', {}).get('circuit_outcome', {})
            details = dict(project_id=project_id,
                           saved=result.get('saved') is True and receipt.get('saved') is True,
                           saved_digest=receipt.get('saved_digest'),
                           execution_returned=receipt.get('execution_returned') is True,
                           execution_receipt=dict(receipt))
        raise ServiceError('session_circuit_failed', 'Circuit operation failed; inspect partial evidence',
                           outcome=result, **details)
    return result
