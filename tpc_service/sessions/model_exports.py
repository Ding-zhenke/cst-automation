"""Export artifacts from the open project handled by the existing worker."""
import sys

from tpc_service.errors import ServiceError
from .native import file_digest
from .read_review import borrow_open_project
from .store import contained, identifier

FIELD = 'export_complex_field_ascii'
VIEW = 'capture_model_view_png'
OPERATIONS = frozenset((FIELD, VIEW))
CAPABILITY = 'model3d-export-v1'


def validate(operation, params):
    allowed = {'project_id', 'tree_path', 'step'} if operation == FIELD else {'project_id'}
    if params.keys() - allowed:
        raise ServiceError('invalid_session_argument', 'Unsupported model export option')
    if operation == FIELD:
        tree = params.get('tree_path')
        if (not isinstance(tree, str) or not tree.startswith('2D/3D Results\\')
                or len(tree) > 4096 or not all(tree.split('\\'))
                or any(ord(char) < 32 for char in tree)):
            raise ServiceError('invalid_session_argument', 'A full 2D/3D result tree path is required')
        step = params.get('step')
        if step is not None and (type(step) not in (int, float) or not 0 < step <= sys.float_info.max):
            raise ServiceError('invalid_session_argument', 'step must be finite and positive')


def check_worker(state, project_id):
    if state.get('backend') != 'cst':
        raise ServiceError('session_export_requires_cst', 'Model exports require the native CST backend')
    if CAPABILITY not in state.get('worker_capabilities', ()):
        raise ServiceError('workflow_worker_upgrade_required', 'Model export requires a compatible existing worker')
    project = state['projects'].get(project_id)
    if (not project or project.get('tab_closed') or state.get('status') != 'ready'
            or state.get('launch_intent') or state.get('uncertain_jobs')):
        raise ServiceError('session_export_unavailable', 'An open registered project in a ready session is required')
    return project


def execute(runtime, job):
    params = job['params']
    operation = job['operation']
    validate(operation, params)
    state = runtime.state()
    record = check_worker(state, params['project_id'])
    runtime.check_saved(record)
    app, handle, _ = borrow_open_project(runtime, state.get('environment'), record['path'])
    if handle.model3d.is_solver_running(timeout=5) is not False:
        raise ServiceError('session_busy', 'Export requires the 3D solver to be idle')
    handle.activate()
    app.cst_file = handle
    folder = contained(runtime.folder, runtime.folder / 'exports' / identifier(job['job_id']))
    folder.mkdir(parents=True, exist_ok=False)
    if operation == FIELD:
        path = folder / 'field.txt'
        app.export_complex_field_ascii(params['tree_path'], str(path), step=params.get('step'))
    else:
        path = folder / 'model.png'
        app.capture_model_view_png(str(path))
    return dict(operation=operation, project_id=params['project_id'], saved_digest=record['saved_digest'],
                path=str(path), bytes=path.stat().st_size, sha256=file_digest(path))
