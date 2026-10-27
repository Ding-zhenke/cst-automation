"""CST boundary for durable sessions. Handles stay on the worker's main thread."""
import hashlib
import os
from pathlib import Path

from tpc_service.errors import ServiceError
from .store import alive, assert_environment_unclaimed, contained, identifier, lock, process_identity, read, write


def file_digest(path):
    value = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            value.update(block)
    return value.hexdigest()


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
            app = setup.attach(pid=identity['pid'])
            if environment_pid(app.project) != identity['pid'] or not alive(identity):
                raise ServiceError('session_environment_mismatch', 'Exact CST identity mismatch')
            paths = {os.path.normcase(str(Path(p).resolve())) for p in app.project.list_open_projects()}
            expected = {os.path.normcase(p['path']) for p in state['projects'].values() if Path(p['path']).is_file()}
            if not expected.issubset(paths):
                raise ServiceError('session_project_mismatch', 'Recorded projects are no longer open in the owned DE')
            self.app = app
            return app
        # Only a confirmed absent DE authorizes a new generation; creation intent is durable first.
        self.update(launch_intent=True)
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
        project_id = identifier(project_id)
        record = self.state()['projects'].get(project_id)
        if not record or not Path(record['path']).is_file():
            raise ServiceError('project_not_registered', 'Saved session project not found')
        self.check_saved(record)
        app = self.environment()
        if project_id not in self.handles:
            app.open(record['path'])
            self.handles[project_id] = app.cst_file
        app.cst_file = self.handles[project_id]
        return app, record

    def check_saved(self, record):
        expected = record.get('saved_digest')
        if expected and file_digest(record['path']) != expected:
            raise ServiceError('session_project_changed', 'Saved project changed outside this session; inspect before overwriting')

    def save(self, app, project_id):
        state = self.state()
        record = state['projects'][project_id]
        app.save(record['path'], allow_overwrite=True)
        record.update(saved_digest=file_digest(record['path']), saved=True)
        self.update(projects=state['projects'])
        return record

    def execute(self, job):
        from .operations import execute
        return execute(self, job)
