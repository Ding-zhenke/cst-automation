"""Explicit cooperative handoff; native DE survival requires separate acceptance."""
import copy
import math
import os
import time
from uuid import uuid4
from pathlib import Path

from tpc_service.errors import ServiceError
from .store import alive, assert_environment_unclaimed, digest, identifier, lock, process_identity, read, write
from .job_index import JobIndex
from .native import Runtime, file_digest

CAPABILITY = 'preserved-de-worker-handoff-v1'
MODE = 'preserve_native_de_v1'
RELEASE_MAX_AGE = 2.0
STARTUP_ENV = 'CST_HANDOFF_STARTUP_NONCE'


def admit_worker(state, nonce):
    """Caller holds worker.lock and state.lock; no SDK calls before admission."""
    record = state.get('worker_upgrade') or {}
    require(record.get('mode') == MODE and record.get('phase') == 'starting'
            and record.get('launch_claimed') and not record.get('startup_worker'),
            'No unused native worker startup authorization')
    require(isinstance(nonce, str) and bool(nonce)
            and digest(nonce) == record.get('launch_nonce_digest'), 'Startup nonce mismatch')
    launcher = record.get('launcher')
    worker = process_identity(os.getpid())
    require(launcher and state.get('worker') == launcher
            and process_identity(launcher['pid']) == launcher, 'Launcher identity changed')
    require(worker and os.path.normcase(os.path.realpath(worker['image'])) ==
            os.path.normcase(os.path.realpath(record['expected_worker_image'])), 'Unexpected worker image')
    require(worker == launcher or (os.getppid() == launcher['pid']
            and process_identity(os.getppid()) == launcher), 'Worker is not the authorized launcher child')
    record.update(startup_worker=worker, startup_registered_at=time.time())
    return worker


def recover(manager, session_id, credential, *, expected_token, expected_launcher,
            review_note, confirm_no_worker_processes=False):
    require(confirm_no_worker_processes is True and isinstance(review_note,str)
            and 0 < len(review_note.strip()) <= 8192, 'Reviewed absence of failed worker process tree required')
    folder = manager._folder(session_id)
    with lock(folder/'handoff.lock'), lock(folder/'launch.lock'), lock(folder/'worker.lock', blocking=False):
        def check(state):
            record = check_frozen(folder,state)
            require(record['phase'] == 'starting' and record['token'] == expected_token
                    and record.get('launch_claimed') and record.get('stop_ack'), 'Exact consumed launch required')
            require(expected_launcher and state.get('worker') == expected_launcher
                    and record.get('launcher',expected_launcher) == expected_launcher,
                    'Exact failed launcher identity required')
            require(not any(record.get(k) for k in ('startup_worker','new_worker_ready','new_worker_native','new_worker_error')),
                    'Post-admission recovery is not supported')
            require(process_identity(expected_launcher['pid']) is None
                    and not alive(record['old_worker']), 'Old worker or launcher is still present')
            return record
        with lock(manager.root/'registry.lock'), lock(folder/'state.lock'):
            state = manager._state(folder,credential);record = check(state)
        proof = verify_native(Runtime(folder,'cst'),state)
        require(proof == record['pre_exit_native'], 'Native state changed before recovery')
        with lock(manager.root/'registry.lock'), lock(folder/'state.lock'):
            state = manager._state(folder,credential);record = check(state)
            history = record.pop('failed_launches', [])
            history.append(dict(copy.deepcopy(record), recovery_review=review_note,
                                process_tree_absence_asserted_by_caller=True, recovered_at=time.time()))
            for key in ('launch_attempted','launch_claimed','launch_nonce_digest','launcher',
                        'expected_worker_image','startup_error','post_exit_native'):
                record.pop(key,None)
            record.update(token=uuid4().hex,phase='stop_requested',failed_launches=history)
            state.update(worker=None,worker_capabilities=[],worker_launch_intent=False)
            write(folder/'session.json',state)
            return copy.deepcopy(record)


def require(ok, message):
    if not ok:
        raise ServiceError('native_handoff_refused', message)


def error_record(exc):
    if isinstance(exc,ServiceError):
        return exc.to_dict()
    return dict(type=type(exc).__name__,message=str(exc),details=copy.deepcopy(getattr(exc,'details',None)))


def saved_digests(state):
    projects = state['projects']
    require(bool(projects), 'Registered saved projects required')
    result = {}
    for key, project in projects.items():
        require(project.get('saved') is True, 'Every registered project must be saved')
        actual = file_digest(project['path'])
        require(actual == project.get('saved_digest'), 'Registered saved baseline changed')
        result[key] = actual
    return result


def file_versions(state):
    result = {}
    for key, project in state['projects'].items():
        stat = Path(project['path']).stat()
        result[key] = [stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns, stat.st_ino]
    return result


def check_frozen(folder, state):
    record = state.get('worker_upgrade') or {}
    require(record.get('mode') == MODE and state['backend'] == 'cst', 'Native handoff not active')
    require(not record.get('archive_recovery', {}).get('pending'), 'Use archive recovery until restoration is verified')
    require(state['status'] == 'closing' and not state.get('uncertain_jobs')
            and not state.get('launch_intent') and not state.get('close_requested')
            and not JobIndex.load(folder).active_jobs(), 'Handoff must remain idle and frozen')
    require(state.get('environment') == record['environment'] and alive(record['environment']),
            'Original DE disappeared or changed; never create a replacement')
    require(digest(state['projects']) == record['projects_digest']
            and file_versions(state) == record['file_versions'], 'Project baseline changed')
    if record['phase'] not in ('release_requested','release_verified'):
        require(saved_digests(state) == record['project_digests'], 'Project content changed')
    assert_environment_unclaimed(folder.parent, state['session_id'], record['environment'])
    return record


def verify_static_partial(app, review, project_id):
    """Read the full reviewed dirty circuit; never infer it from disk bytes."""
    if project_id != review['project_id']:
        return None
    from cst_solver.circuit.adapter import NativeAdapter
    snapshot = NativeAdapter(app).inspect()
    require(isinstance(snapshot, dict) and all(u == {'field':'parameter_dimensions','status':'unknown'}
            for u in snapshot.get('unknown', [])), 'Incomplete native static circuit snapshot')
    actual = digest(snapshot)
    require(actual == review['snapshot_digest'], 'Dirty static circuit changed since review')
    return actual


def verify_native(runtime, state):
    """Borrow exact existing tabs. Never use Runtime.environment's create/reopen fallback."""
    from cst_solver.dialogs import check_dialogs
    from .read_review import borrow_open_project
    from .inspection import inspect_native
    from .project_lifecycle import path_key
    identity = state['environment']
    require(alive(identity), 'Original DE is not live')
    versions = file_versions(state)
    saved_digests(state)  # Hash before native observations, not after their timestamp.
    check_dialogs(label='native_worker_handoff', pid=identity['pid'])
    projects = {k:p for k,p in state['projects'].items() if not p.get('tab_closed')}
    require(bool(projects), 'At least one registered open tab required')
    expected = {path_key(p['path']) for p in projects.values()}
    parameters, handles, app, static_proof = {}, {}, None, {}
    static_review = (state.get('worker_upgrade') or {}).get('static_partial')
    def parameter_snapshot(app):
        observed = inspect_native(app, {'solid_names': []})
        require(not observed['errors'], 'Full native parameter readback failed')
        for value in observed['parameters'].values():
            require(isinstance(value['value'], (float, int)) and not isinstance(value['value'], bool)
                    and math.isfinite(value['value']), 'Native parameter must be finite')
        return observed['parameters']
    for key, project in projects.items():
        app, handle, opened = borrow_open_project(runtime, identity, project['path'])
        require(set(opened) == expected, 'Open tabs differ; no foreign or missing tabs allowed')
        require(handle.model3d.is_solver_running(timeout=5) is False, 'Native EM idle not proven')
        app.cst_file = handle
        parameters[key] = parameter_snapshot(app)
        if static_review:
            value = verify_static_partial(app, static_review, key)
            if value is not None:
                static_proof[key] = value
        handles[key] = handle
        runtime.app = app
    require(set(map(path_key, app.project.list_open_projects())) == expected and alive(identity),
            'DE or tabs changed during review')
    for key, handle in handles.items():
        app.cst_file = handle
        require(parameter_snapshot(app) == parameters[key], 'Native parameter state changed during review')
        if static_review and key == static_review['project_id']:
            require(verify_static_partial(app, static_review, key) == static_proof.get(key), 'Dirty static circuit drifted')
        require(path_key(handle.filename()) == path_key(projects[key]['path'])
                and handle.model3d.is_solver_running(timeout=5) is False, 'Tab identity or idle changed')
    check_dialogs(label='native_worker_handoff_complete', pid=identity['pid'])
    require(alive(identity), 'DE identity changed during final dialog review')
    observed_at = time.time()
    require(file_versions(state) == versions, 'Saved files changed during native review')
    runtime.handoff_native_observed_at = observed_at
    runtime.handles = handles
    result = {'tabs': sorted(expected), 'parameters': parameters}
    if static_review:
        require(set(static_proof) == {static_review['project_id']}, 'Dirty static project missing')
        result['static_partial'] = static_proof
    return result


def begin(manager, session_id, credential, *, environment_identity, worker_identity,
          project_digests, review_note, required_capabilities, confirm_idle=False,
          confirm_saved_tabs=False, confirm_borrowed_worker=False,
          accept_unverified_native_handoff=False, worker_ownership='borrowed',
          confirm_owned_worker=False, accept_owned_worker_exit_risk=False):
    from .manager import UPGRADE_CAPABILITY
    require(all(x is True for x in (confirm_idle, confirm_saved_tabs,
                                    accept_unverified_native_handoff)), 'Explicit reviewed native handoff confirmations required')
    require(worker_ownership in ('borrowed','owned'), 'Explicit borrowed or owned worker classification required')
    if worker_ownership == 'borrowed':
        require(confirm_borrowed_worker is True and confirm_owned_worker is False
                and accept_owned_worker_exit_risk is False, 'Borrowed-worker review required without owned assertions')
    else:
        require(confirm_borrowed_worker is False and confirm_owned_worker is True
                and accept_owned_worker_exit_risk is True,
                'Owned worker requires separate confirmation and explicit native exit risk acceptance')
    require(isinstance(review_note, str) and 0 < len(review_note.strip()) <= 8192, 'Review note required')
    require(isinstance(required_capabilities, list) and bool(required_capabilities)
            and all(isinstance(x,str) and 0 < len(x) <= 256 for x in required_capabilities)
            and len(set(required_capabilities)) == len(required_capabilities), 'Unique required capabilities required')
    for identity in (environment_identity, worker_identity):
        require(isinstance(identity,dict) and set(identity) == {'pid','started','image'}
                and type(identity['pid']) is int and identity['pid'] > 0
                and bool(identity['started']) and isinstance(identity['image'],str)
                and bool(identity['image']), 'Complete process identity required')
    folder = manager._folder(session_id)
    with lock(manager.root/'registry.lock'), lock(folder/'state.lock'):
        state = manager._state(folder, credential)
        require(manager.backend == state['backend'] == 'cst', 'Native session required')
        if state.get('worker_upgrade'):
            record = check_frozen(folder, state)
            require(record['environment'] == environment_identity and record['old_worker'] == worker_identity
                    and record['project_digests'] == project_digests
                    and record['requested_capabilities'] == required_capabilities
                    and record.get('worker_ownership','borrowed') == worker_ownership
                    and record['review_note'] == review_note, 'Existing handoff inputs differ')
            return copy.deepcopy(record)
        require(state['status'] == 'ready' and not state.get('uncertain_jobs')
                and not state.get('launch_intent') and not state.get('close_requested')
                and not JobIndex.load(folder).active_jobs(), 'Ready idle unfenced session required')
        require(state.get('worker') == worker_identity and alive(worker_identity)
                and UPGRADE_CAPABILITY in state.get('worker_capabilities',[]), 'Exact cooperative worker required')
        require(state.get('environment') == environment_identity and alive(environment_identity), 'Exact live DE required')
        require(saved_digests(state) == project_digests, 'Complete reviewed project digests required')
        assert_environment_unclaimed(manager.root,session_id,environment_identity)
        record = dict(mode=MODE,token=uuid4().hex,phase='reviewing',old_worker=worker_identity,
            environment=environment_identity,projects_digest=digest(state['projects']),
            project_digests=project_digests,review_note=review_note,stop_ack=False,
            file_versions=file_versions(state),
            requested_capabilities=required_capabilities,
            required_capabilities=sorted(set(required_capabilities+[CAPABILITY])),started_at=time.time(),
            native_acceptance='pending',saved_tabs_asserted_by_caller=True,
            schematic_idle_asserted_by_caller=True,
            worker_ownership=worker_ownership,borrowed_worker_asserted_by_caller=confirm_borrowed_worker,
            owned_worker_asserted_by_caller=confirm_owned_worker,
            owned_worker_exit_risk_accepted=accept_owned_worker_exit_risk)
        state.update(status='closing',worker_upgrade=record)
        write(folder/'session.json',state)
        return copy.deepcopy(record)


def begin_failed_static(manager, session_id, credential, *, failed_job_id, project_id,
                        snapshot_digest, environment_identity, worker_identity, project_digests,
                        review_note, confirm_idle=False, confirm_borrowed_worker=False,
                        accept_unverified_native_handoff=False, worker_ownership='borrowed',
                        confirm_owned_worker=False, accept_owned_worker_exit_risk=False,
                        require_self_em_exclusion=False, require_guarded_static_run=False):
    """Freeze the exact failed static session without treating its dirty tab as saved."""
    from .manager import UPGRADE_CAPABILITY
    require(confirm_idle is True and accept_unverified_native_handoff is True,
            'Explicit idle and handoff review required')
    require(worker_ownership in ('borrowed','owned'), 'Explicit worker ownership required')
    if worker_ownership == 'borrowed':
        require(confirm_borrowed_worker is True and confirm_owned_worker is False
                and accept_owned_worker_exit_risk is False, 'Borrowed worker review required')
    else:
        require(confirm_borrowed_worker is False and confirm_owned_worker is True
                and accept_owned_worker_exit_risk is True, 'Owned worker and native exit risk review required')
    require(isinstance(review_note, str) and 0 < len(review_note.strip()) <= 8192, 'Review note required')
    require(isinstance(snapshot_digest, str) and len(snapshot_digest) == 64
            and all(c in '0123456789abcdef' for c in snapshot_digest), 'Reviewed circuit digest required')
    require(type(require_self_em_exclusion) is bool, 'Explicit exclusion capability choice required')
    require(type(require_guarded_static_run) is bool, 'Explicit guarded-run capability choice required')
    failed_job_id, project_id = identifier(failed_job_id), identifier(project_id)
    folder = manager._folder(session_id)
    with lock(manager.root/'registry.lock'), lock(folder/'state.lock'):
        state = manager._state(folder, credential)
        existing = state.get('worker_upgrade')
        if existing:
            record = check_frozen(folder, state)
            review = record.get('static_partial') or {}
            require(record.get('return_to_fence') is True and review.get('failed_job_id') == failed_job_id
                    and review.get('project_id') == project_id and review.get('snapshot_digest') == snapshot_digest
                    and record.get('environment') == environment_identity and record.get('old_worker') == worker_identity
                    and record.get('project_digests') == project_digests and record.get('review_note') == review_note
                    and record.get('worker_ownership') == worker_ownership
                    and ('static-sp-self-em-exclusion-v1' in record.get('requested_capabilities', []))
                        == require_self_em_exclusion
                    and ('static-sp-guarded-run-v1' in record.get('requested_capabilities', []))
                        == require_guarded_static_run, 'Existing handoff inputs differ')
            return copy.deepcopy(record)
        require(manager.backend == state['backend'] == 'cst' and state.get('status') == 'needs_reconcile' and not state.get('uncertain_jobs')
                and not state.get('launch_intent') and not state.get('close_requested')
                and (state.get('runtime_diagnostics') or {}).get('state','clear') == 'clear'
                and not JobIndex.load(folder).active_jobs(), 'Exact idle failed session required')
        job = read(folder/'jobs'/(failed_job_id+'.json')) or {}
        error = job.get('error') or {}
        require(job.get('job_id') == failed_job_id and job.get('session_id') == session_id
                and job.get('status') == 'failed' and job.get('finished_at')
                and job.get('operation') == 'prepare_static_sp' and job.get('params', {}).get('project_id') == project_id
                and error == state.get('last_error') and error.get('code') == 'session_static_sp_prepare_failed'
                and error.get('details', {}).get('mutation_may_have_occurred') is True
                and not (error.get('details', {}).get('session_monitor') or {}).get('failure_latched')
                and not (error.get('details', {}).get('session_monitor') or {}).get('first_failure'),
                'Exact partial static preparation failure required')
        require(project_id in state['projects'] and not state['projects'][project_id].get('tab_closed'), 'Open owned target required')
        require(state.get('worker') == worker_identity and alive(worker_identity)
                and UPGRADE_CAPABILITY in state.get('worker_capabilities', [])
                and CAPABILITY in state.get('worker_capabilities', []), 'Exact preserved-DE cooperative worker required')
        require(state.get('environment') == environment_identity and alive(environment_identity), 'Exact live DE required')
        require(saved_digests(state) == project_digests, 'Exact disk baseline required')
        assert_environment_unclaimed(manager.root, session_id, environment_identity)
        needed = ['static-sp-fenced-recovery-v1']
        if require_self_em_exclusion:
            needed.append('static-sp-self-em-exclusion-v1')
        if require_guarded_static_run:
            needed.append('static-sp-guarded-run-v1')
        record = dict(mode=MODE, token=uuid4().hex, phase='reviewing', old_worker=worker_identity,
            environment=environment_identity, projects_digest=digest(state['projects']), project_digests=project_digests,
            file_versions=file_versions(state), review_note=review_note, stop_ack=False,
            requested_capabilities=needed, required_capabilities=sorted(needed+[CAPABILITY]), started_at=time.time(),
            native_acceptance='pending', saved_tabs_asserted_by_caller=False, schematic_idle_asserted_by_caller=True,
            worker_ownership=worker_ownership, borrowed_worker_asserted_by_caller=confirm_borrowed_worker,
            owned_worker_asserted_by_caller=confirm_owned_worker,
            owned_worker_exit_risk_accepted=accept_owned_worker_exit_risk, return_to_fence=True,
            static_partial={'failed_job_id':failed_job_id,'project_id':project_id,'snapshot_digest':snapshot_digest,
                            'failed_job_digest':digest(job),'saved_disk_only':True})
        state.update(status='closing', worker_upgrade=record)
        write(folder/'session.json',state)
        return copy.deepcopy(record)


def begin_dead_static_worker_recovery(manager, session_id, credential, *, failed_job_id, completion_job_id,
        project_id, snapshot_digest, environment_identity, worker_identity, project_digests, review_note,
        confirm_idle=False, confirm_no_worker_processes=False, require_self_em_exclusion=False,
        require_guarded_static_run=False):
    """Freeze a saved static failure after worker death, then review the same DE."""
    require(confirm_idle is True and confirm_no_worker_processes is True,
            'Explicit idle and absence of the old worker process tree required')
    require(isinstance(review_note,str) and 0<len(review_note.strip())<=8192, 'Review note required')
    require(type(require_self_em_exclusion) is bool and type(require_guarded_static_run) is bool,
            'Explicit capability choices required')
    require(isinstance(snapshot_digest,str) and len(snapshot_digest)==64
            and all(c in '0123456789abcdef' for c in snapshot_digest), 'Reviewed circuit digest required')
    for value in (failed_job_id,completion_job_id,project_id): identifier(value)
    require(isinstance(worker_identity,dict) and type(worker_identity.get('pid')) is int
            and worker_identity['pid']>0 and process_identity(worker_identity['pid']) is None,
            'Old worker PID must be absent, including PID reuse')
    folder=manager._folder(session_id)
    with lock(folder/'handoff.lock'),lock(folder/'launch.lock'),lock(folder/'worker.lock',blocking=False):
        with lock(manager.root/'registry.lock'),lock(folder/'state.lock'):
            state=manager._state(folder,credential)
            existing=state.get('worker_upgrade') or {}
            if existing:
                record=check_frozen(folder,state);partial=record.get('static_partial') or {}
                require(record.get('dead_worker_recovery') is True and record.get('old_worker')==worker_identity
                        and record.get('environment')==environment_identity and record.get('project_digests')==project_digests
                        and record.get('review_note')==review_note and partial.get('failed_job_id')==failed_job_id
                        and partial.get('completion_job_id')==completion_job_id and partial.get('project_id')==project_id
                        and partial.get('snapshot_digest')==snapshot_digest
                        and ('static-sp-self-em-exclusion-v1' in record['requested_capabilities'])==require_self_em_exclusion
                        and ('static-sp-guarded-run-v1' in record['requested_capabilities'])==require_guarded_static_run,
                        'Existing dead-worker recovery differs')
                if record['phase']=='stop_requested': return copy.deepcopy(record)
                require(record['phase']=='reviewing','Recovery is already advancing')
            else:
                require(manager.backend==state.get('backend')=='cst' and state.get('status')=='needs_reconcile'
                        and not state.get('uncertain_jobs') and not state.get('worker_upgrade')
                        and not state.get('launch_intent')
                        and not state.get('close_requested') and not JobIndex.load(folder).active_jobs()
                        and (state.get('runtime_diagnostics') or {}).get('state','clear')=='clear',
                        'Idle fenced session without uncertain work required')
                require(state.get('worker')==worker_identity and not alive(worker_identity)
                        and process_identity(worker_identity['pid']) is None, 'Exact dead worker required')
                require(state.get('environment')==environment_identity and alive(environment_identity), 'Exact live DE required')
                original=read(folder/'jobs'/(failed_job_id+'.json')) or {};error=original.get('error') or {}
                require(original.get('job_id')==failed_job_id and original.get('session_id')==session_id
                        and original.get('operation')=='prepare_static_sp' and original.get('status')=='failed'
                        and original.get('finished_at') and original.get('params',{}).get('project_id')==project_id
                        and error==state.get('last_error') and error.get('code')=='session_static_sp_prepare_failed'
                        and error.get('details',{}).get('mutation_may_have_occurred') is True
                        and not (error.get('details',{}).get('session_monitor') or {}).get('failure_latched')
                        and not (error.get('details',{}).get('session_monitor') or {}).get('first_failure'),
                        'Exact original returned static failure required')
                completed=read(folder/'jobs'/(completion_job_id+'.json')) or {};result=completed.get('result') or {}
                require(completed.get('job_id')==completion_job_id and completed.get('session_id')==session_id
                        and completed.get('operation')=='complete_failed_static_task' and completed.get('status')=='succeeded'
                        and completed.get('params',{}).get('project_id')==project_id
                        and completed.get('params',{}).get('failed_job_id')==failed_job_id
                        and result.get('original_failed_job_id')==failed_job_id and result.get('saved') is True
                        and result.get('saved_digest')==project_digests.get(project_id)
                        and isinstance(result.get('after'),dict) and digest(result['after'])==snapshot_digest,
                        'Exact returned and saved static completion required')
                require(project_id in state['projects'] and not state['projects'][project_id].get('tab_closed')
                        and saved_digests(state)==project_digests, 'Exact saved open projects required')
                assert_environment_unclaimed(manager.root,session_id,environment_identity)
                needed=['static-sp-fenced-recovery-v1']
                if require_self_em_exclusion: needed.append('static-sp-self-em-exclusion-v1')
                if require_guarded_static_run: needed.append('static-sp-guarded-run-v1')
                record=dict(mode=MODE,token=uuid4().hex,phase='reviewing',old_worker=worker_identity,
                    environment=environment_identity,projects_digest=digest(state['projects']),project_digests=project_digests,
                    file_versions=file_versions(state),review_note=review_note,stop_ack=False,dead_worker_recovery=True,
                    requested_capabilities=needed,required_capabilities=sorted(needed+[CAPABILITY]),started_at=time.time(),
                    native_acceptance='pending',return_to_fence=True,worker_ownership='borrowed',
                    schematic_idle_asserted_by_caller=True,worker_process_tree_absence_asserted_by_caller=True,
                    static_partial={'failed_job_id':failed_job_id,'completion_job_id':completion_job_id,
                        'project_id':project_id,'snapshot_digest':snapshot_digest,'failed_job_digest':digest(original),
                        'saved_disk_only':True})
                state.update(status='closing',worker_upgrade=record);write(folder/'session.json',state)
            token=record['token']
        proof=verify_native(Runtime(folder,'cst'),state)
        with lock(manager.root/'registry.lock'),lock(folder/'state.lock'):
            current=manager._state(folder,credential);record=check_frozen(folder,current)
            require(record['token']==token and record['phase']=='reviewing' and current['worker']==worker_identity
                    and process_identity(worker_identity['pid']) is None and not alive(worker_identity),
                    'Dead worker or recovery changed during native review')
            record.update(phase='stop_requested',pre_exit_native=proof,stop_ack=True,
                          dead_worker_absence_verified_at=time.time())
            write(folder/'session.json',current)
            return copy.deepcopy(record)


def finish(manager, session_id, credential):
    folder = manager._folder(session_id)
    # Serialize advances without holding state/registry locks across native getters.
    with lock(folder/'handoff.lock'):
        with lock(manager.root/'registry.lock'), lock(folder/'state.lock'):
            state = manager._state(folder,credential)
            if not state.get('worker_upgrade'):
                previous = state.get('last_worker_upgrade') or {}
                require(previous.get('mode') == MODE and previous.get('phase') == 'complete', 'No native handoff')
                return previous
            record = check_frozen(folder,state)
            phase, token = record['phase'], record['token']
            if phase == 'stop_requested' and (not record.get('stop_ack') or alive(record['old_worker'])):
                return copy.deepcopy(record)
            if phase in ('starting','release_requested','release_verified'):
                worker = state.get('worker')
                if not (worker and worker != record['old_worker'] and alive(worker)
                        and record.get('new_worker_ready') == worker
                        and record.get('new_worker_native') == record.get('pre_exit_native')
                        and set(record['required_capabilities']).issubset(state.get('worker_capabilities',[]))):
                    return copy.deepcopy(record)
                if phase == 'release_requested':
                    return copy.deepcopy(record)
                if (phase == 'release_verified' and record.get('release_worker') == worker
                        and record.get('release_ack') == record.get('release_token')
                        and record.get('release_native') == record['pre_exit_native']
                        and 0 <= time.time()-record.get('release_verified_at',0) <= RELEASE_MAX_AGE):
                    record.update(phase='complete',new_worker=worker,completed_at=time.time(),
                                  native_acceptance='handoff_readback_verified')
                    state.update(status='needs_reconcile' if record.get('return_to_fence') else 'ready',last_worker_upgrade=record)
                    state.pop('worker_upgrade')
                else:
                    record.update(phase='release_requested',release_token=uuid4().hex)
                    for key in ('release_ack','release_worker','release_native','release_verified_at'):
                        record.pop(key,None)
                write(folder/'session.json',state)
                return copy.deepcopy(record)
            require(phase in ('reviewing','stop_requested'), 'Unknown native handoff phase')
            if phase == 'reviewing':
                require(state['worker'] == record['old_worker'] and alive(record['old_worker']), 'Original worker lost before exit request')
        try:
            proof = verify_native(Runtime(folder,'cst'),state)
            if phase == 'stop_requested':
                require(proof == record['pre_exit_native'], 'Native parameter/tab state changed across exit')
        except Exception as exc:
            with lock(folder/'state.lock'):
                current = manager._state(folder,credential)
                if (current.get('worker_upgrade') or {}).get('token') == token:
                    current['worker_upgrade']['last_verification_error'] = error_record(exc)
                    write(folder/'session.json',current)
            raise
        with lock(manager.root/'registry.lock'), lock(folder/'state.lock'):
            current = manager._state(folder,credential);record = check_frozen(folder,current)
            require(record['token'] == token and record['phase'] == phase, 'Handoff changed during verification')
            if phase == 'reviewing':
                require(current['worker'] == record['old_worker'] and alive(record['old_worker']), 'Original worker lost during review')
                record.update(phase='stop_requested',pre_exit_native=proof)
            else:
                require(record.get('stop_ack') and not alive(record['old_worker']), 'Original worker has not exited')
                require(current.get('worker') in (None,record['old_worker']), 'Unexpected replacement worker')
                record.update(phase='starting',launch_attempted=True,post_exit_native=proof)
                current.update(worker=None,worker_capabilities=[])
            write(folder/'session.json',current)
        if phase == 'stop_requested':
            manager._launch(folder,recover=True,native_handoff_token=token)
        return copy.deepcopy(record)


def prepare_new_worker(runtime):
    """Run on the new worker's SDK thread before it may advertise native readiness."""
    folder = runtime.folder
    try:
        with lock(folder.parent/'registry.lock'), lock(folder/'state.lock'):
            state = read(folder/'session.json');record = check_frozen(folder,state)
            require(record['phase'] == 'starting' and record.get('stop_ack')
                    and not alive(record['old_worker']), 'Invalid native replacement phase')
            token, worker = record['token'], state['worker']
            require(worker == process_identity(os.getpid()) and worker != record['old_worker'],
                    'Native readiness must be established by the replacement worker itself')
        proof = verify_native(runtime,state)
        require(proof == record['pre_exit_native'], 'Replacement readback differs from reviewed native state')
        with lock(folder.parent/'registry.lock'), lock(folder/'state.lock'):
            state = read(folder/'session.json');record = check_frozen(folder,state)
            require(record['token'] == token and record['phase'] == 'starting'
                    and state['worker'] == worker and alive(worker), 'Replacement identity changed')
            record.update(new_worker_ready=worker,new_worker_native=proof)
            write(folder/'session.json',state)
        return True
    except Exception as exc:
        with lock(folder/'state.lock'):
            state = read(folder/'session.json')
            if (state.get('worker_upgrade') or {}).get('mode') == MODE:
                state['worker_upgrade']['new_worker_error'] = error_record(exc)
                write(folder/'session.json',state)
        return False


def verify_release(runtime):
    """Fresh token-bound readback on the replacement's SDK thread, while queue is frozen."""
    folder = runtime.folder
    try:
        with lock(folder.parent/'registry.lock'), lock(folder/'state.lock'):
            state = read(folder/'session.json');record = check_frozen(folder,state)
            require(record['phase'] == 'release_requested', 'Release verification not requested')
            token, release_token, worker = record['token'], record['release_token'], state['worker']
            require(worker == process_identity(os.getpid()) and worker == record['new_worker_ready'],
                    'Only the verified replacement may acknowledge release')
        proof = verify_native(runtime,state)
        require(proof == record['pre_exit_native'], 'Native state changed before release')
        observed_at = runtime.handoff_native_observed_at
        with lock(folder.parent/'registry.lock'), lock(folder/'state.lock'):
            state = read(folder/'session.json');record = check_frozen(folder,state)
            require(record['token'] == token and record['phase'] == 'release_requested'
                    and record['release_token'] == release_token and state['worker'] == worker and alive(worker),
                    'Release authorization changed during verification')
            record.update(phase='release_verified',release_ack=release_token,release_worker=worker,
                          release_native=proof,release_verified_at=observed_at)
            write(folder/'session.json',state)
        return True
    except Exception as exc:
        with lock(folder/'state.lock'):
            state = read(folder/'session.json')
            if (state.get('worker_upgrade') or {}).get('mode') == MODE:
                state['worker_upgrade']['release_error'] = error_record(exc)
                write(folder/'session.json',state)
        return False
