"""CST boundary for durable sessions. Handles stay on the worker's main thread."""
import hashlib
import os
from pathlib import Path

from tpc_service.errors import ServiceError
from .store import alive, assert_environment_unclaimed, contained, identifier, lock, process_identity, read, write
from .diagnostics import mark_stage


def file_digest(path):
    value = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            value.update(block)
    return value.hexdigest()



def restore_reviewed_projects(app, state, open_paths):
    """Reopen absent saved tabs only from an explicit, still-matching review."""
    reviewed=state.get('last_resolution', {})
    digests=reviewed.get('project_digests', {})
    missing=[]
    for project_id, record in state['projects'].items():
        if record.get('tab_closed'):
            continue
        path=Path(record['path'])
        key=os.path.normcase(str(path.resolve()))
        if key in open_paths or not path.is_file():
            continue
        digest=file_digest(path)
        if not reviewed.get('human_reviewed') or digests.get(project_id)!=digest or record.get('saved_digest')!=digest:
            raise ServiceError('session_project_mismatch', 'Absent saved project has no matching explicit review', project_id=project_id)
        missing.append(str(path))
    for path in missing:
        app.open(path)
    return {os.path.normcase(str(Path(p).resolve())) for p in app.project.list_open_projects()}


class Runtime:
    def __init__(self, folder, backend):
        self.folder = Path(folder)
        self.backend = backend
        self.app = None
        self.handles = {}

    def state(self):
        return read(self.folder / 'session.json')

    def update(self, **values):
        from contextlib import nullcontext
        registry_lock = lock(self.folder.parent / 'registry.lock') if values.get('environment') else nullcontext()
        with registry_lock, lock(self.folder / 'state.lock'):
            state = self.state()
            if values.get('environment'):
                assert_environment_unclaimed(self.folder.parent, state['session_id'], values['environment'])
            state.update(values)
            write(self.folder / 'session.json', state)

    def environment(self):
        mark_stage(self, 'environment.check_identity')
        if self.app is not None:
            if self.backend == 'cst' and not alive(self.state()['environment']):
                self.app = None
                self.handles.clear()
            else:
                return self.app
        state = self.state()
        if state['launch_intent']:
            raise ServiceError('session_launch_uncertain', 'Environment creation receipt is missing; reconcile before creating another DE')
        if self.backend == 'fake':
            from .offline import OfflineApp
            self.app = OfflineApp()
            self.update(environment={'backend': 'fake', **process_identity(os.getpid())},
                        environment_generation=state['environment_generation'] + 1)
            return self.app
        from cst_solver import setup
        from cst_solver.environment import environment_pid
        identity = state['environment']
        if identity and alive(identity):
            mark_stage(self, 'environment.attach_owned')
            app = setup.attach(pid=identity['pid'])
            if environment_pid(app.project) != identity['pid'] or not alive(identity):
                raise ServiceError('session_environment_mismatch', 'Exact CST identity mismatch')
            mark_stage(self, 'environment.verify_projects')
            paths = {os.path.normcase(str(Path(p).resolve())) for p in app.project.list_open_projects()}
            expected = {os.path.normcase(p['path']) for p in state['projects'].values()
                        if Path(p['path']).is_file() and not p.get('tab_closed')}
            if not expected.issubset(paths):
                mark_stage(self, 'environment.restore_reviewed_projects')
                paths = restore_reviewed_projects(app, state, paths)
                if not expected.issubset(paths):
                    raise ServiceError('session_project_mismatch', 'Reviewed projects could not be reopened in the owned DE', expected_paths=sorted(expected), open_paths=sorted(paths))
            self.app = app
            return app
        # Only a confirmed absent DE authorizes a new generation; creation intent is durable first.
        self.update(launch_intent=True)
        mark_stage(self, 'environment.create_native')
        app = setup()
        pid = environment_pid(app.project)
        identity = process_identity(pid) if pid else None
        if not identity:
            raise ServiceError('session_environment_unidentified', 'Created DE has no verified process identity')
        self.app = app
        self.update(environment=identity, environment_generation=state['environment_generation'] + 1,
                    launch_intent=False)
        return app

    def project(self, project_id):
        mark_stage(self, 'project.resolve_record')
        project_id = identifier(project_id)
        record = self.state()['projects'].get(project_id)
        if not record or not Path(record['path']).is_file():
            raise ServiceError('project_not_registered', 'Saved session project not found')
        self.check_saved(record)
        app = self.environment()
        if project_id not in self.handles:
            if self.backend == 'cst':
                from .project_lifecycle import path_key
                mark_stage(self, 'project.list_open')
                opened = {path_key(p): p for p in app.project.list_open_projects()}
                existing = opened.get(path_key(record['path']))
                if existing:
                    mark_stage(self, 'project.borrow_open')
                    app.cst_file = app.project.get_open_project(existing)
                    mark_stage(self, 'project.activate')
                    app.cst_file.activate()
                else:
                    mark_stage(self, 'project.open')
                    app.open(record['path'])
            else:
                mark_stage(self, 'project.open')
                app.open(record['path'])
            self.handles[project_id] = app.cst_file
        app.cst_file = self.handles[project_id]
        if record.get('tab_closed'):
            mark_stage(self, 'project.update_tab_state')
            state = self.state()
            state['projects'][project_id]['tab_closed'] = False
            self.update(projects=state['projects'])
        return app, record

    def check_saved(self, record):
        mark_stage(self, 'project.digest_check')
        expected = record.get('saved_digest')
        if expected and file_digest(record['path']) != expected:
            raise ServiceError('session_project_changed', 'Saved project changed outside this session; inspect before overwriting')

    def save(self, app, project_id):
        mark_stage(self, 'project.prepare_save')
        state = self.state()
        record = state['projects'][project_id]
        mark_stage(self, 'project.save_native')
        app.save(record['path'], allow_overwrite=True)
        mark_stage(self, 'project.digest_after_save')
        record.update(saved_digest=file_digest(record['path']), saved=True)
        mark_stage(self, 'project.persist_saved_record')
        self.update(projects=state['projects'])
        return record

    def execute(self, job):
        from .operations import execute
        return execute(self, job)
