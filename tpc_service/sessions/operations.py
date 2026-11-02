"""Bounded operation registry. No eval, dynamic imports, Python scripts or shell."""
import hashlib
from pathlib import Path

from tpc_service.errors import ServiceError
from .native import file_digest
from .store import contained, identifier, write


def execute(runtime, job):
    operation, params = job['operation'], job['params']
    for predecessor in params.get('depends_on', []):
        from .store import read
        matches = [read(p) for p in (runtime.folder / 'jobs').glob('*.json')]
        if not any(j['operation_id'] == predecessor and j['status'] == 'succeeded' for j in matches):
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
        if state['status'] == 'needs_reconcile':
            return {'backend': runtime.backend, 'state': 'needs_reconcile', 'projects': state['projects'],
                    'uncertain_jobs': state.get('uncertain_jobs', []), 'readback_verified': False}
        app, record = runtime.project(params['project_id'])
        result = {'project': record, 'backend': runtime.backend, 'readback_verified': False, 'solver_verified': False}
        if runtime.backend == 'cst':
            result['messages'] = [str(m) for m in app.get_messages()]
        else:
            result['offline_model'] = app.cst_file
        return result
    if operation == 'start':
        runtime.environment()
        return {'environment': runtime.state()['environment'], 'backend': runtime.backend}
    if operation in ('create_project', 'import_project'):
        project_id = identifier(params['project_id'])
        state = runtime.state()
        if project_id in state['projects']:
            raise ServiceError('project_exists', 'Project already registered; use the original stage/request')
        project_type = params.get('project_type', 'MWS')
        if project_type not in ('MWS', 'DS'):
            raise ServiceError('invalid_session_argument', 'project_type must be MWS or DS')
        path = contained(runtime.folder, runtime.folder / 'projects' / project_id / 'model.cst')
        if path.exists():
            raise ServiceError('project_exists', 'Unregistered file exists; reconcile instead of overwriting')
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
        state['projects'][project_id] = {'project_id': project_id, 'path': str(path),
                                          'source_path': source, 'saved': False}
        runtime.update(projects=state['projects'])
        app = runtime.environment()
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
    app, record = runtime.project(params['project_id'])
    if operation == 'history':
        code = params['vba']
        if not isinstance(code, str) or not code.strip() or len(code) > 1_000_000:
            raise ServiceError('invalid_session_argument', 'Explicit bounded VBA history required')
        checksum = hashlib.sha256(code.encode()).hexdigest()
        if params.get('preview_digest') != checksum or not params.get('stage_id') or not params.get('name'):
            raise ServiceError('session_preview_required', 'Supply reviewed VBA digest, stage_id and history name')
        if runtime.backend == 'fake':
            app.cst_file['history'].append({'name': params['name'], 'vba': code})
        else:
            app.cst_file.model3d.add_to_history(params['name'], code)
    elif operation == 'set_parameters':
        values = params['values']
        if not isinstance(values, dict) or not values:
            raise ServiceError('invalid_session_argument', 'Nonempty parameter values required')
        if runtime.backend == 'fake':
            app.cst_file['parameters'].update(values)
        else:
            for name, value in values.items():
                app.para(name, value)
    elif operation == 'solve':
        if runtime.backend == 'fake':
            raise ServiceError('offline_solver_unavailable', 'Fake sessions cannot certify a solve')
        result = app.run_checked(project_path=record['path'], note=str(params.get('note', '')))
        runtime.save(app, params['project_id'])
        if result.get('status') != 'succeeded':
            raise ServiceError('session_solve_unverified', 'Solver did not confirm success', outcome=result)
        return {'saved': True, 'solver_outcome': result, 'backend': 'cst'}
    elif operation == 'circuit':
        return circuit(runtime, app, record, params)
    else:
        raise ServiceError('unknown_session_operation', 'Unsupported session operation')
    validation = None
    if runtime.backend == 'cst':
        validation = app.validate_model()
        if validation.get('status') != 'success' or not validation.get('rebuild_ok'):
            # Save partial evidence without permitting subsequent dependent stages.
            runtime.save(app, params['project_id'])
            raise ServiceError('session_geometry_unverified', 'Rebuild/messages require inspection', validation=validation)
    record = runtime.save(app, params['project_id'])
    checkpoint = {'job_id': job['job_id'], 'operation_id': job['operation_id'],
                  'fingerprint': job['fingerprint'], 'project_id': params['project_id'],
                  'saved_digest': record['saved_digest'], 'saved': True, 'readback_verified': False,
                  'geometry_validation': validation}
    write(runtime.folder / 'checkpoints' / (job['job_id'] + '.json'), checkpoint)
    return dict(checkpoint, backend=runtime.backend, solver_verified=False)


def circuit(runtime, app, record, params):
    """Reuse existing explicit circuit workflow without its temporary DE lifecycle."""
    from types import SimpleNamespace
    from tpc_service.circuit import register_circuit_handlers

    class BorrowedApp:
        def __getattr__(self, name):
            return getattr(app, name)

        def close(self):
            pass  # Per-operation release; explicit close_session owns DE lifetime.

    handlers = {}
    service = SimpleNamespace(workdir=str(runtime.folder),
                              register_workflow=lambda name, values, **kw: handlers.update(values))
    register_circuit_handlers(service, app_factory=lambda path: BorrowedApp())
    kind = params.get('kind', 'build')
    if kind not in handlers:
        raise ServiceError('invalid_session_argument', 'Invalid circuit kind')
    result = handlers[kind](project=record, params=params['settings'], job={'kind': kind}, backend=None)
    if Path(record['path']).is_file():
        # Handler may save partial changes; update the fingerprint, but never certify partial work.
        state = runtime.state()
        state['projects'][record['project_id']]['saved_digest'] = file_digest(record['path'])
        runtime.update(projects=state['projects'])
    if not result.get('ok'):
        raise ServiceError('session_circuit_failed', 'Circuit operation failed; inspect partial evidence', outcome=result)
    return result
