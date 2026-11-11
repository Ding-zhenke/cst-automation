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
from .job_index import JobIndex
from .schematic_recovery import OPERATION as SCHEMATIC_RECOVERY
from .store import alive, assert_environment_unclaimed, contained, digest, identifier, lock, process_identity, read, write

OPERATIONS = frozenset(('start', 'create_project', 'import_project', 'adopt_project', 'close_project', 'configure_sweep', 'inspect', 'history',
                        'set_parameters', 'model_api', 'solve', 'circuit', 'reload_project', 'close', 'accept_workflow_evidence', 'fit_em_network', 'update_hb_network', 'qualify_saved_em', 'prepare_hb_embedded_network', 'accept_saved_baseline', SCHEMATIC_RECOVERY))
FENCED_OPERATIONS = frozenset(('inspect', 'close', SCHEMATIC_RECOVERY))
UPGRADE_CAPABILITY = 'cooperative-worker-upgrade-v1'


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
        state = self._state(folder, credential)
        public = {k: v for k, v in state.items() if k != 'credential_hash'}
        # State and journals are atomically replaced. A long history scan must not hold
        # the state lock against a just-launched worker. The state and jobs are
        # consequently observations at different times, not one snapshot.
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

    def bind_workflow(self, session_id, credential, project_id, spec, *, expected_revision=None):
        from .workflow import bind
        folder = self._folder(session_id)
        with lock(self.root / 'registry.lock'), lock(folder / 'state.lock'):
            return bind(folder, self._state(folder, credential), identifier(project_id), spec, expected_revision)

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
        operation_id = operation_id or (params.get('stage_id') if operation in ('history', 'configure_sweep', 'model_api') else None) or request_id
        if not isinstance(operation_id, str) or not operation_id or len(operation_id) > 512:
            raise ServiceError('invalid_session_argument', 'Invalid operation_id')
        fingerprint = digest({'operation': operation, 'params': params})
        folder = self._folder(session_id)
        with lock(self.root / 'registry.lock'), lock(folder / 'state.lock'):
            state = self._state(folder, credential)
            alias_path = folder / 'requests' / (digest(request_id) + '.json')
            alias = read(alias_path)
            if alias:
                if alias['fingerprint'] != fingerprint:
                    raise ServiceError('request_id_conflict', 'Same request has different payload')
                old = read(folder / 'jobs' / (identifier(alias['job_id']) + '.json'))
                if not old or old.get('fingerprint') != fingerprint:
                    raise ServiceError('session_job_journal_missing', 'Request alias has no matching journal')
                return old
            index = JobIndex.load(folder)
            old = index.match(request_id, operation_id)
            if old:
                if old['fingerprint'] != fingerprint:
                    raise ServiceError('request_id_conflict', 'Same request/stage has different payload')
                write(alias_path, {'fingerprint': fingerprint, 'job_id': old['job_id']})
                return old
            if state['status'] in ('closing', 'closed', 'close_failed') or state.get('close_requested'):
                raise ServiceError('session_closing', 'Session is closing or closed')
            if state['status'] == 'needs_reconcile' and operation not in FENCED_OPERATIONS:
                raise ServiceError('session_needs_reconcile', 'Inspect uncertain operations before further writes')
            if operation == SCHEMATIC_RECOVERY and (state['status'] != 'needs_reconcile' or self.backend != 'cst'):
                raise ServiceError('session_schematic_recovery_refused', 'Schematic recovery requires a fenced CST session')
            from .project_lifecycle import check_project_intent
            from .formal_paths import PROJECT_OPERATIONS, assert_path_unclaimed
            if operation in PROJECT_OPERATIONS:
                check_project_intent(state, index.active_jobs(), operation, params)
                assert_path_unclaimed(self.root, folder, operation, params)
            from .workflow import preflight
            from .model_api import settings_only, settings_capability
            from .model_api import uses_hf_tet_adaptation_controls, HF_TET_ADAPTATION_CAPABILITY
            if (operation == 'model_api' and uses_hf_tet_adaptation_controls(params['calls'])
                    and state.get('worker') and alive(state['worker'])
                    and HF_TET_ADAPTATION_CAPABILITY not in state.get('worker_capabilities', [])):
                raise ServiceError('workflow_worker_upgrade_required', 'HF Tet adaptation controls require a compatible idle worker')
            from cst_automation.port_replacement import CAPABILITY as PORT_CAPABILITY, METHOD as PORT_METHOD
            if (operation == 'model_api' and any(c['method'] == PORT_METHOD for c in params['calls'])
                    and state.get('worker') and alive(state['worker'])
                    and PORT_CAPABILITY not in state.get('worker_capabilities', [])):
                raise ServiceError('workflow_worker_upgrade_required', 'Port replacement requires a readback-capable worker')
            if (operation == 'model_api' and settings_only(params['calls'])
                    and state.get('worker') and alive(state['worker'])
                    and settings_capability(params['calls']) not in state.get('worker_capabilities', [])):
                raise ServiceError('workflow_worker_upgrade_required', 'Settings-only batches require an upgraded idle worker')
            workflow_guard = preflight(folder, state, operation, params)
            state['sequence'] = max(state['sequence'], index.maximum_sequence) + 1
            job = {'job_id': 'job-' + uuid4().hex, 'session_id': session_id,
                   'sequence': state['sequence'], 'request_id': request_id, 'operation_id': operation_id,
                   'fingerprint': fingerprint, 'operation': operation, 'params': params,
                   'status': 'queued', 'created_at': time.time(), 'result': None, 'error': None}
            if workflow_guard is not None:
                job['workflow_guard'] = workflow_guard
            # Publish the full receipt first. A missing index entry is repaired from its filename.
            write(folder / 'jobs' / (job['job_id'] + '.json'), job)
            index.add(job)
            index.save()
            write(alias_path, {'fingerprint': fingerprint, 'job_id': job['job_id']})
            if operation == 'close':
                state['close_requested'] = True
                if state['status'] != 'needs_reconcile':
                    state['status'] = 'closing'
            write(folder / 'session.json', state)
        if operation != 'accept_saved_baseline':
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
            if state.get('worker_upgrade'):
                raise ServiceError('session_maintenance', 'Finish the existing worker upgrade instead of resuming')
        self._launch(folder, recover=True)
        return self.status(session_id, credential)

    def begin_worker_upgrade(self, session_id, credential, *, confirm_idle=False, required_capabilities=None):
        folder = self._folder(session_id)
        with lock(self.root / 'registry.lock'), lock(folder / 'state.lock'):
            state = self._state(folder, credential)
            if state.get('worker_upgrade'):
                if required_capabilities is not None and required_capabilities != state['worker_upgrade']['required_capabilities']:
                    raise ServiceError('session_maintenance', 'Existing upgrade has different required capabilities')
                return dict(state['worker_upgrade'])
            if confirm_idle is not True:
                raise ServiceError('session_review_required', 'Confirm the owned session and DE are idle')
            required = [] if required_capabilities is None else required_capabilities
            if (not isinstance(required, list) or any(not isinstance(c, str) or not c for c in required)
                    or len(set(required)) != len(required)):
                raise ServiceError('invalid_session_argument', 'required_capabilities must be a unique list of names')
            if (state['status'] != 'ready' or state.get('uncertain_jobs') or state.get('launch_intent')
                    or state.get('close_requested') or JobIndex.load(folder).active_jobs()):
                raise ServiceError('session_busy', 'Worker upgrade requires an idle, unfenced session')
            worker = state.get('worker')
            if not worker or not alive(worker) or UPGRADE_CAPABILITY not in state.get('worker_capabilities', []):
                raise ServiceError('worker_upgrade_unsupported', 'Live worker lacks cooperative upgrade support')
            if self.backend == 'cst' and state.get('environment') and alive(state['environment']):
                raise ServiceError('worker_upgrade_live_de_unverified', 'Live native DE preservation is not verified')
            record = {'phase': 'stop_requested', 'old_worker': worker, 'stop_ack': False,
                      'started_at': time.time(), 'environment': state.get('environment'),
                      'projects_digest': digest(state['projects']), 'required_capabilities': required}
            state.update(status='closing', worker_upgrade=record)
            write(folder/'session.json', state)
            return dict(record)

    def finish_worker_upgrade(self, session_id, credential):
        folder = self._folder(session_id)
        launch = False
        with lock(self.root / 'registry.lock'), lock(folder / 'state.lock'):
            state = self._state(folder, credential)
            record = state.get('worker_upgrade')
            if not record:
                previous = state.get('last_worker_upgrade')
                if previous and previous.get('phase') == 'complete':
                    return dict(previous)
                raise ServiceError('session_maintenance', 'No worker upgrade is in progress')
            if (state['status'] != 'closing' or state.get('uncertain_jobs') or state.get('launch_intent')
                    or state.get('close_requested') or JobIndex.load(folder).active_jobs()
                    or state.get('environment') != record['environment']
                    or digest(state['projects']) != record['projects_digest']):
                raise ServiceError('session_maintenance', 'Upgrade remains frozen; inspect changed session state')
            if self.backend == 'cst' and state.get('environment') and alive(state['environment']):
                raise ServiceError('worker_upgrade_live_de_unverified', 'Live native DE preservation is not verified')
            if record['phase'] == 'stop_requested':
                if not record.get('stop_ack') or alive(record['old_worker']):
                    return dict(record)
                current = state.get('worker')
                if current != record['old_worker'] and current and alive(current):
                    return dict(record)
                record['phase'] = 'starting'
                record['launch_attempted'] = True
                state.update(worker=None, worker_capabilities=[], worker_upgrade=record)
                write(folder/'session.json', state)
                launch = True
            elif record['phase'] == 'starting':
                worker = state.get('worker')
                if (worker and worker != record['old_worker'] and alive(worker)
                        and record.get('new_worker_ready') == worker
                        and UPGRADE_CAPABILITY in state.get('worker_capabilities', [])
                        and set(record['required_capabilities']).issubset(state.get('worker_capabilities', []))):
                    record.update(phase='complete', new_worker=worker, completed_at=time.time())
                    state.update(status='ready', last_worker_upgrade=record)
                    state.pop('worker_upgrade', None)
                    write(folder/'session.json', state)
                    return dict(record)
                # A lost launch receipt may conceal a live child. Never launch
                # another worker automatically from an uncertain attempt.
            else:
                raise ServiceError('session_maintenance', 'Unknown upgrade phase')
        if launch:
            self._launch(folder, recover=True)
        return dict(record)

    def close(self, session_id, credential, request_id):
        return self.submit(session_id, credential, request_id, 'close')

    def reconcile(self, session_id, credential, review_note, project_digests, *, confirm_idle=False,
                  environment_identity=None, confirm_no_environment=False, abandon_projects=None, resolve_job_ids=None):
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
            selected = [] if resolve_job_ids is None else resolve_job_ids
            if (not isinstance(selected, list) or any(not isinstance(i, str) for i in selected)
                    or len(set(selected)) != len(selected)):
                raise ServiceError('invalid_session_argument', 'resolve_job_ids must be a unique list of job IDs')
            by_id = {j['job_id']: j for j in jobs}
            if any(i not in by_id or by_id[i]['status'] not in ('needs_reconcile', 'failed', 'blocked') for i in selected):
                raise ServiceError('session_review_required', 'Selected job is missing or not eligible for resolution')
            required = set(state.get('uncertain_jobs') or []) | {j['job_id'] for j in jobs if j['status'] == 'needs_reconcile'}
            if not required.issubset(selected):
                raise ServiceError('session_review_required', 'Select every uncertain job before clearing the fence')
            last_error = state.get('last_error')
            matching = {j['job_id'] for j in jobs if j['status'] == 'failed' and j.get('error') == last_error} if last_error else set()
            if not required and last_error and not matching.intersection(selected):
                raise ServiceError('session_review_required', 'Select the failed job corresponding to the session last error')
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
                     'resolved_job_ids': selected,
                     'human_reviewed': True, 'readback_verified': False, 'solver_verified': False,
                     'at': time.time()}
            for job in jobs:
                if job['job_id'] in selected:
                    job.update(status='resolved', resolution=audit)
                    write(folder / 'jobs' / (job['job_id'] + '.json'), job)
            for pid, record in state['projects'].items():
                record.update(saved_digest=project_digests[pid], saved=True)
            state.update(status='ready', uncertain_jobs=[], last_resolution=audit, close_requested=False)
            write(folder / 'session.json', state)
        self._launch(folder, recover=True)
        return self.status(session_id, credential)
