"""Durable manager facade. No CST handle, global active session or network server."""
import hmac
import os
from pathlib import Path
import secrets
import subprocess
import sys
import time
from uuid import uuid4

from tpc_service.errors import ServiceError
from .store import alive, assert_environment_unclaimed, contained, digest, identifier, lock, process_identity, read, write

OPERATIONS = frozenset(('start', 'create_project', 'import_project', 'inspect', 'history',
                        'set_parameters', 'solve', 'circuit', 'close'))


class SessionManager:
    def __init__(self, root, *, backend='cst'):
        if not Path(root).is_absolute():
            raise ValueError('Session root must be absolute')
        if backend not in ('cst', 'fake'):
            raise ValueError('backend must be cst or fake')
        self.root = Path(root).resolve()
        self.backend = backend
        self.root.mkdir(parents=True, exist_ok=True)

    def ensure(self, binding, request_id):
        if not all(isinstance(v, str) and 1 <= len(v) <= 512 for v in (binding, request_id)):
            raise ServiceError('invalid_session_argument', 'binding and request_id required')
        with lock(self.root / 'registry.lock'):
            path = self.root / 'bindings' / (digest(binding) + '.json')
            old = read(path)
            if old:
                if old['request_hash'] != digest(request_id):
                    raise ServiceError('binding_conflict', 'Binding already exists; use its original recovery reference')
                return old['reference']
            sid, credential = 'ses-' + uuid4().hex, secrets.token_urlsafe(32)
            folder = self.root / sid
            state = {'schema_version': 1, 'session_id': sid, 'backend': self.backend,
                     'credential_hash': digest(credential), 'status': 'allocated', 'worker': None,
                     'environment': None, 'environment_generation': 0, 'projects': {},
                     'sequence': 0, 'launch_intent': False, 'created_at': time.time()}
            write(folder / 'session.json', state)
            reference = {'session_id': sid, 'credential': credential, 'root': str(self.root)}
            write(path, {'request_hash': digest(request_id), 'reference': reference})
            return reference

    def _folder(self, sid):
        return contained(self.root, self.root / identifier(sid))

    def _state(self, folder, credential):
        state = read(folder / 'session.json')
        if not state or not isinstance(credential, str) or not hmac.compare_digest(
                state['credential_hash'], digest(credential)):
            raise ServiceError('session_credential_invalid', 'Invalid session credential')
        if state['backend'] != self.backend:
            raise ServiceError('session_backend_mismatch', 'Explicit backend does not match session')
        return state

    def status(self, session_id, credential):
        folder = self._folder(session_id)
        with lock(folder / 'state.lock'):
            state = self._state(folder, credential)
            public = {k: v for k, v in state.items() if k != 'credential_hash'}
            public['jobs'] = [read(p) for p in sorted((folder / 'jobs').glob('*.json'))]
        return public

    def job(self, session_id, credential, job_id):
        folder = self._folder(session_id)
        with lock(folder / 'state.lock'):
            self._state(folder, credential)
            value = read(folder / 'jobs' / (identifier(job_id) + '.json'))
        if value is None:
            raise ServiceError('unknown_job', 'Unknown session job')
        return value

    def submit(self, session_id, credential, request_id, operation, params=None, *, operation_id=None):
        if operation not in OPERATIONS:
            raise ServiceError('unknown_session_operation', 'Unknown explicit session operation')
        if not isinstance(request_id, str) or not request_id or len(request_id) > 512:
            raise ServiceError('invalid_session_argument', 'Nonempty request_id required')
        params = {} if params is None else params
        if not isinstance(params, dict):
            raise ServiceError('invalid_session_argument', 'params must be an object')
        from .validation import validate
        validate(operation, params)
        operation_id = operation_id or (params.get('stage_id') if operation == 'history' else None) or request_id
        if not isinstance(operation_id, str) or not operation_id or len(operation_id) > 512:
            raise ServiceError('invalid_session_argument', 'Invalid operation_id')
        fingerprint = digest({'operation': operation, 'params': params})
        folder = self._folder(session_id)
        with lock(folder / 'state.lock'):
            state = self._state(folder, credential)
            alias_path = folder / 'requests' / (digest(request_id) + '.json')
            alias = read(alias_path)
            if alias:
                if alias['fingerprint'] != fingerprint:
                    raise ServiceError('request_id_conflict', 'Same request has different payload')
                return read(folder / 'jobs' / (alias['job_id'] + '.json'))
            # Journals themselves are the authoritative indices: no index/receipt crash gap.
            maximum_sequence = state['sequence']
            for path in (folder / 'jobs').glob('*.json'):
                old = read(path)
                maximum_sequence = max(maximum_sequence, old['sequence'])
                if old['request_id'] == request_id or old['operation_id'] == operation_id:
                    if old['fingerprint'] != fingerprint:
                        raise ServiceError('request_id_conflict', 'Same request/stage has different payload')
                    write(alias_path, {'fingerprint': fingerprint, 'job_id': old['job_id']})
                    return old
            if state['status'] in ('closing', 'closed', 'close_failed') or state.get('close_requested'):
                raise ServiceError('session_closing', 'Session is closing or closed')
            if state['status'] == 'needs_reconcile' and operation not in ('inspect', 'close'):
                raise ServiceError('session_needs_reconcile', 'Inspect uncertain operations before further writes')
            state['sequence'] = maximum_sequence + 1
            job = {'job_id': 'job-' + uuid4().hex, 'session_id': session_id,
                   'sequence': state['sequence'], 'request_id': request_id, 'operation_id': operation_id,
                   'fingerprint': fingerprint, 'operation': operation, 'params': params,
                   'status': 'queued', 'created_at': time.time(), 'result': None, 'error': None}
            # Persist queue acceptance before state sequence; worker sorts by durable sequence.
            write(folder / 'jobs' / (job['job_id'] + '.json'), job)
            write(alias_path, {'fingerprint': fingerprint, 'job_id': job['job_id']})
            if operation == 'close':
                state['close_requested'] = True
                if state['status'] != 'needs_reconcile':
                    state['status'] = 'closing'
            write(folder / 'session.json', state)
        self._launch(folder)
        return self.job(session_id, credential, job['job_id'])

    def _launch(self, folder, *, recover=False):
        with lock(folder / 'launch.lock'):
            with lock(folder / 'state.lock'):
                state = read(folder / 'session.json')
                if state['status'] == 'closed':
                    return
                if alive(state['worker']):
                    return
                if state.get('worker_launch_intent') and not recover:
                    raise ServiceError('session_worker_lost', 'Worker unavailable; call resume, do not repeat modeling')
                state['worker_launch_intent'] = True
                write(folder / 'session.json', state)
                flags = (subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP) if os.name == 'nt' else 0
                source_root = Path(__file__).resolve().parents[2]
                with (folder / 'worker.log').open('ab') as log:
                    proc = subprocess.Popen([sys.executable, '-m', 'tpc_service.sessions.worker', str(folder)],
                                            cwd=str(source_root), stdin=subprocess.DEVNULL, stdout=log,
                                            stderr=log, creationflags=flags, start_new_session=os.name != 'nt')
                state['worker'] = process_identity(proc.pid)
                write(folder / 'session.json', state)

    def resume(self, session_id, credential):
        folder = self._folder(session_id)
        with lock(folder / 'state.lock'):
            state = self._state(folder, credential)
            if state['status'] == 'closed':
                raise ServiceError('session_closed', 'Explicitly closed session; create a new binding to reopen saved work')
        self._launch(folder, recover=True)
        return self.status(session_id, credential)

    def close(self, session_id, credential, request_id):
        return self.submit(session_id, credential, request_id, 'close')

    def reconcile(self, session_id, credential, review_note, project_digests, *, confirm_idle=False,
                  environment_identity=None, confirm_no_environment=False, abandon_projects=None):
        """Explicit human-reviewed baseline, never an automatic retry or success certification."""
        from .native import file_digest
        folder = self._folder(session_id)
        with lock(self.root / 'registry.lock'), lock(folder / 'state.lock'):
            state = self._state(folder, credential)
            if state['status'] not in ('needs_reconcile', 'close_failed'):
                raise ServiceError('session_reconcile_not_needed', 'Only uncertain/failed-close sessions can be reconciled')
            jobs = [read(p) for p in (folder / 'jobs').glob('*.json')]
            if any(j['status'] == 'running' for j in jobs):
                raise ServiceError('session_busy', 'Original operation is still running; do not reconcile it')
            if not isinstance(review_note, str) or not review_note.strip():
                raise ServiceError('session_review_required', 'Explicit human review note required')
            for pid in abandon_projects or []:
                record = state['projects'].get(pid)
                if not record or record.get('saved') or Path(record['path']).exists():
                    raise ServiceError('session_review_required', 'Only explicitly reviewed, missing unsaved project intents can be abandoned')
                state['projects'].pop(pid)
            if not isinstance(project_digests, dict) or set(project_digests) != set(state['projects']):
                raise ServiceError('session_digest_mismatch', 'Provide reviewed digest for every registered project')
            for pid, record in state['projects'].items():
                if not Path(record['path']).is_file() or file_digest(record['path']) != project_digests[pid]:
                    raise ServiceError('session_digest_mismatch', 'Reviewed digest does not match saved project')
            if confirm_idle is not True:
                raise ServiceError('session_review_required', 'Human must explicitly confirm CST is idle')
            if state['launch_intent']:
                if environment_identity and alive(environment_identity):
                    assert_environment_unclaimed(self.root, session_id, environment_identity)
                    state['environment'] = environment_identity
                elif confirm_no_environment is True:
                    state['environment'] = None
                else:
                    raise ServiceError('session_review_required', 'Resolve unknown DE creation before further writes')
                state['launch_intent'] = False
            audit = {'review_note': review_note, 'project_digests': project_digests,
                     'abandoned_projects': abandon_projects or [],
                     'human_reviewed': True, 'readback_verified': False, 'solver_verified': False,
                     'at': time.time()}
            for job in jobs:
                if job['status'] in ('needs_reconcile', 'failed', 'blocked'):
                    job.update(status='resolved', resolution=audit)
                    write(folder / 'jobs' / (job['job_id'] + '.json'), job)
            for pid, record in state['projects'].items():
                record.update(saved_digest=project_digests[pid], saved=True)
            state.update(status='ready', uncertain_jobs=[], last_resolution=audit, close_requested=False)
            write(folder / 'session.json', state)
        self._launch(folder, recover=True)
        return self.status(session_id, credential)
