"""Fenced archive restore, followed by cooperative fresh-handle worker admission.

Controller calls borrow the exact DE only after the queue is frozen. No solve,
save, history editing, forced exit, automatic retry, or companion-file merging.
"""
import copy
import math
from pathlib import Path
import re
import shutil
import time
from uuid import uuid4

from tpc_service.errors import ServiceError
from .native import Runtime, file_digest
from .store import alive, assert_environment_unclaimed, digest, identifier, lock, read, write
from . import native_handoff as handoff


def require(condition, message):
    if not condition:
        raise ServiceError('model3d_archive_recovery_refused', message)


def _plain(path):
    path = Path(path)
    require(path.is_absolute(), 'Absolute path required')
    for parent in (path, *path.parents):
        require(not parent.is_symlink() and not getattr(parent, 'is_junction', lambda: False)(),
                'Linked recovery paths are not supported')
    return path.resolve()


def _manifest(path):
    path = _plain(path)
    if not path.exists():
        return None
    require(path.is_dir(), 'Companion path must be a directory')
    result = {}
    for entry in path.rglob('*'):
        _plain(entry)
        require(entry.is_file() or entry.is_dir(), 'Unsupported companion entry')
        if entry.is_file():
            result[entry.relative_to(path).as_posix()] = file_digest(entry)
    return result


def _validate(review):
    fields = {'project_id', 'failed_job_id', 'environment_identity', 'worker_identity',
              'registered_digest', 'current_digest', 'source_path', 'source_digest',
              'expected_parameters', 'expected_ports', 'forbidden_history_fragment',
              'review_note', 'confirm_idle', 'confirm_discard', 'accept_worker_exit_risk'}
    require(set(review) == fields, 'Exact archive recovery fields required')
    for key in ('project_id', 'failed_job_id'):
        identifier(review[key])
    for key in ('registered_digest', 'current_digest', 'source_digest'):
        require(isinstance(review[key], str) and re.fullmatch('[0-9a-f]{64}', review[key]), 'Exact digests required')
    for key in ('confirm_idle', 'confirm_discard', 'accept_worker_exit_risk'):
        require(review[key] is True, 'Explicit idle, discard and worker-exit risk acceptance required')
    for key in ('review_note', 'forbidden_history_fragment'):
        require(isinstance(review[key], str) and 0 < len(review[key].strip()) <= 8192, 'Bounded review text required')
    for key in ('environment_identity', 'worker_identity'):
        value = review[key]
        require(isinstance(value, dict) and set(value) == {'pid', 'started', 'image'}
                and type(value['pid']) is int and value['pid'] > 0 and value['started']
                and isinstance(value['image'], str) and value['image'], 'Complete process identity required')
    params = review['expected_parameters']
    require(isinstance(params, dict) and 0 < len(params) <= 10000, 'Full expected parameter map required')
    for name, value in params.items():
        require(isinstance(name, str) and name and isinstance(value, dict) and set(value) == {'value', 'expression'}
                and type(value['value']) in (int, float) and math.isfinite(value['value'])
                and isinstance(value['expression'], str), 'Invalid expected parameter')
    ports = review['expected_ports']
    require(isinstance(ports, dict) and 0 < len(ports) <= 10000, 'Full expected port inventory required')
    for key, value in ports.items():
        require(isinstance(key, str) and key.isdecimal() and int(key) > 0
                and isinstance(value, dict) and set(value) == {'type', 'number_of_modes'}
                and value['type'] in ('Discrete', 'Waveguide') and type(value['number_of_modes']) is int
                and value['number_of_modes'] > 0, 'Invalid expected port inventory')


def _preflight(folder, state, review):
    require(state['backend'] == 'cst' and not state.get('launch_intent') and not state.get('uncertain_jobs')
            and not state.get('close_requested'), 'No unresolved native work permitted')
    require({key for key, value in state['projects'].items() if not value.get('tab_closed')} == {review['project_id']},
            'Exactly one registered open target required; closed registrations are retained')
    target = _plain(state['projects'][review['project_id']]['path'])
    pair = _plain(target.with_suffix(''))
    for key, value in state['projects'].items():
        if key != review['project_id']:
            other = _plain(value['path'])
            for left in (target, pair):
                for right in (other, _plain(other.with_suffix(''))):
                    require(left != right and left not in right.parents and right not in left.parents,
                            'Target archive/companion overlaps another registered project')
            require(value.get('tab_closed') is True and value.get('saved') is True
                    and other.is_file() and file_digest(other) == value.get('saved_digest'),
                    'Closed project baseline changed or unavailable')
    transaction = (state.get('worker_upgrade') or {}).get('archive_recovery')
    if transaction:
        require(state['projects'] == transaction['original_projects'], 'Registered projects changed during recovery')
    project = state['projects'][review['project_id']]
    require(project.get('saved') is True and not project.get('tab_closed')
            and project.get('saved_digest') == review['registered_digest'], 'Registered baseline differs')
    source = _plain(review['source_path'])
    require(target.suffix.lower() == source.suffix.lower() == '.cst' and source != target
            and pair not in source.parents, 'Separate extracted native CST source required')
    require(source.is_file() and target.is_file() and file_digest(source) == review['source_digest']
            and file_digest(target) == review['current_digest'], 'Current or source bytes differ from review')
    require(state.get('environment') == review['environment_identity'] and alive(state['environment']), 'Original DE identity lost')
    require(state.get('worker') == review['worker_identity'], 'Original worker identity changed')
    assert_environment_unclaimed(folder.parent, state['session_id'], state['environment'])
    original = read(folder / 'jobs' / (review['failed_job_id'] + '.json')) or {}
    require(original.get('status') == 'failed' and original.get('finished_at')
            and original.get('job_id') == review['failed_job_id'] and original.get('session_id') == state['session_id']
            and original.get('operation') in ('model_api', 'history')
            and original.get('params', {}).get('domain', 'model3d') == 'model3d'
            and original.get('params', {}).get('project_id') == review['project_id']
            and original.get('error') == state.get('last_error') and original.get('error'),
            'Matching finished failed 3D job required; unknown calls cannot be recovered')
    diagnostic = original.get('error', {}).get('details', {}).get('diagnostics', {})
    message = diagnostic.get('message')
    require(diagnostic.get('job_id') == original['job_id']
            and diagnostic.get('operation') == original['operation']
            and diagnostic.get('message_truncated') is False and isinstance(message, str)
            and re.fullmatch(r'An error occurred while trying to execute add_to_history:\r?\n'
                             r'\(&H[0-9a-fA-F]{8}\) [\s\S]+\r?\n\([^\r\n]+\)\s*', message),
            'Complete returned native add_to_history error required; timeout/connection loss is not a return proof')
    for journal in (folder / 'jobs').glob('*.json'):
        require(read(journal).get('status') not in ('queued', 'running', 'needs_reconcile'), 'Active or uncertain job prevents recovery')
    return target, source, original


def begin(manager, session_id, credential, **review):
    _validate(review)
    folder = manager._folder(session_id)
    with lock(manager.root / 'registry.lock'), lock(folder / 'state.lock'):
        state = manager._state(folder, credential)
        if state.get('worker_upgrade'):
            record = state['worker_upgrade']
            require(record.get('archive_recovery', {}).get('review') == review, 'Existing maintenance inputs differ')
            return copy.deepcopy(record)
        require(state['status'] == 'needs_reconcile', 'Recovery begins from the original fence')
        target, source, original = _preflight(folder, state, review)
        require(alive(state['worker']) and 'cooperative-worker-upgrade-v1' in state.get('worker_capabilities', []),
                'A live cooperative old worker is required; no force-stop fallback')
        token = uuid4().hex
        record = dict(mode=handoff.MODE, phase='recovery_reviewing', token=token,
                      old_worker=copy.deepcopy(state['worker']), environment=copy.deepcopy(state['environment']),
                      stop_ack=False, started_at=time.time(), required_capabilities=[handoff.CAPABILITY],
                      requested_capabilities=[handoff.CAPABILITY], review_note=review['review_note'],
                      return_to_fence=True,
                      archive_recovery=dict(pending=True, review=copy.deepcopy(review), original_job=original,
                          original_projects=copy.deepcopy(state['projects']),
                          evidence_dir=str(folder / 'archive-recovery' / token)))
        state.update(status='closing', worker_upgrade=record)
        write(folder / 'session.json', state)
        return copy.deepcopy(record)


def _observe(folder, state, restored=False):
    from cst_solver.dialogs import check_dialogs
    from cst_solver.simulation.port_replacement import port_inventory
    from .inspection import inspect_native
    from .read_review import borrow_open_project
    from .project_lifecycle import path_key
    review = state['worker_upgrade']['archive_recovery']['review']
    path = state['projects'][review['project_id']]['path']
    identity = state['environment']
    check_dialogs(label='archive_recovery_review', pid=identity['pid'])
    app, handle, opened = borrow_open_project(Runtime(folder, 'cst'), identity, path)
    require(set(opened) == {path_key(path)}, 'Foreign or missing tabs prevent recovery')
    require(handle.model3d.is_solver_running(timeout=5) is False, 'Native EM must be idle')
    app.cst_file = handle
    def snapshot():
        observed = inspect_native(app, {'solid_names': []})
        require(not observed['errors'], 'Complete native parameter readback required')
        return dict(parameters=observed['parameters'], ports=port_inventory(app))
    proof = snapshot()
    require(snapshot() == proof and alive(identity), 'Native scene changed during review')
    if restored:
        require(proof['parameters'] == review['expected_parameters'] and proof['ports'] == review['expected_ports'],
                'Restored parameters or ports differ from reviewed archive')
        history = read(Path(path).with_suffix('') / 'Model' / '3D' / 'ModelHistory.json')
        require(isinstance(history, dict) and isinstance(history.get('history'), list) and history['history'],
                'Fresh native history was not materialized; do not reuse failed evidence')
        commands = []
        for row in history['history']:
            require(isinstance(row, dict), 'Unsupported native history entry')
            code = row.get('code')
            require(isinstance(code, str) or (isinstance(code, list) and all(isinstance(line, str) for line in code)),
                    'Unsupported native history format')
            commands.append(code if isinstance(code, str) else '\n'.join(code))
        require(all(review['forbidden_history_fragment'] not in code for code in commands),
                'Failed history fragment remains after reopen')
        messages = list(app.get_messages())
        if messages:
            raise ServiceError('model3d_archive_recovery_refused',
                               'Reopened project reported native messages; inspect dependencies without replay',
                               messages=[str(message) for message in messages])
        proof['history_sha256'] = file_digest(Path(path).with_suffix('') / 'Model' / '3D' / 'ModelHistory.json')
    check_dialogs(label='archive_recovery_review_complete', pid=identity['pid'])
    require(alive(identity) and path_key(handle.filename()) == path_key(path)
            and set(map(path_key, app.project.list_open_projects())) == {path_key(path)}, 'Native identity changed')
    return proof, app, handle


def _backup(target, evidence):
    before = evidence / 'before'
    before.mkdir(parents=True, exist_ok=False)
    pair = target.with_suffix('')
    cst_hash, manifest = file_digest(target), _manifest(pair)
    shutil.copy2(target, before / 'project.cst')
    if manifest is not None:
        shutil.copytree(pair, before / 'companion')
    require(file_digest(target) == file_digest(before / 'project.cst') == cst_hash
            and _manifest(pair) == _manifest(before / 'companion') == manifest, 'Failed scene changed during backup')
    write(evidence / 'before_manifest.json', dict(project=cst_hash, companion=manifest))


def _restore(folder, state):
    record = state['worker_upgrade']; data = record['archive_recovery']; review = data['review']
    target, source, _ = _preflight(folder, state, review)
    evidence = _plain(data['evidence_dir'])
    require(file_digest(evidence / 'before' / 'project.cst') == review['current_digest'], 'Failed archive missing')
    manifest = read(evidence / 'before_manifest.json') or {}
    require(manifest.get('project') == review['current_digest']
            and _manifest(evidence / 'before' / 'companion') == manifest.get('companion')
            and _manifest(target.with_suffix('')) == manifest.get('companion'),
            'Failed companion changed since its verified backup')
    proof, app, handle = _observe(folder, state)
    require(proof == data['pre_exit_scene'], 'Scene changed across old worker exit')
    pair = target.with_suffix('')
    quarantine = _plain(target.parent / (target.stem + '.failed-' + record['token']))
    require(quarantine.parent == target.parent and not quarantine.exists(), 'Exact unused companion quarantine required')
    # Both the pre-close copy and the complete post-close companion tree are kept.
    handle.close()
    require(alive(state['environment']) and not app.project.list_open_projects(), 'Target closure is unverified')
    require(file_digest(target) == review['current_digest'] and file_digest(source) == review['source_digest'],
            'Archive changed during close; recovery remains frozen')
    if pair.exists():
        _manifest(pair)  # Reject reparse points before renaming the exact sibling.
        pair.rename(quarantine)
    require(not pair.exists(), 'Failed companion directory must be absent before reopen')
    staged = evidence / 'restored.cst'
    shutil.copy2(source, staged)
    require(file_digest(staged) == review['source_digest'], 'Staged archive digest mismatch')
    shutil.copy2(staged, target)
    require(file_digest(target) == review['source_digest'], 'Restored file digest mismatch')
    from cst_solver.dialogs import check_dialogs
    check_dialogs(label='archive_recovery_before_reopen', pid=state['environment']['pid'])
    require(alive(state['environment']), 'Original DE lost before reopen')
    app.project.open_project(str(target))
    proof, _, _ = _observe(folder, state, restored=True)
    require(file_digest(target) == review['source_digest'], 'Reopen changed reviewed saved bytes')
    write(evidence / 'restored_native.json', proof)
    return dict(native=proof, quarantine=str(quarantine), restored_digest=review['source_digest'])


def finish(manager, session_id, credential):
    folder = manager._folder(session_id)
    state = manager._state(folder, credential)
    record = state.get('worker_upgrade') or state.get('last_worker_upgrade') or {}
    require(record.get('archive_recovery'), 'No archive recovery transaction')
    if not record['archive_recovery']['pending']:
        return handoff.finish(manager, session_id, credential)
    with lock(folder / 'handoff.lock'):
        with lock(manager.root / 'registry.lock'), lock(folder / 'state.lock'):
            state = manager._state(folder, credential); record = state['worker_upgrade']
            require(state['status'] == 'closing' and record.get('mode') == handoff.MODE, 'Recovery freeze changed')
            data = record['archive_recovery']; review = data['review']
            target, _, _ = _preflight(folder, state, review)
            phase = record['phase']
            require(phase in ('recovery_reviewing', 'stop_requested'), 'Mutation already claimed; inspect audit, never replay')
            if phase == 'stop_requested':
                if not record.get('stop_ack') or alive(record['old_worker']):
                    return copy.deepcopy(record)
                record['phase'] = 'recovery_mutation_claimed'
                write(folder / 'session.json', state)
        try:
            if phase == 'recovery_reviewing':
                require(alive(record['old_worker']), 'Original worker lost before reviewed exit')
                proof, _, _ = _observe(folder, state)
                _backup(target, Path(data['evidence_dir']))
                require(_observe(folder, state)[0] == proof, 'Scene changed while preserving failed files')
                with lock(manager.root / 'registry.lock'), lock(folder / 'state.lock'):
                    current = manager._state(folder, credential)
                    _preflight(folder, current, review)
                    require(current['worker_upgrade']['token'] == record['token'] and alive(record['old_worker']), 'Maintenance changed')
                    current['worker_upgrade']['archive_recovery']['pre_exit_scene'] = proof
                    current['worker_upgrade']['phase'] = 'stop_requested'
                    write(folder / 'session.json', current)
                    return copy.deepcopy(current['worker_upgrade'])
            result = _restore(folder, state)
            # Refresh only the registered baseline and dependent evidence. The job
            # and original last_error remain intact until explicit reconciliation.
            project = state['projects'][review['project_id']]
            project['saved_digest'] = review['source_digest']
            workflow = project.get('workflow')
            if workflow:
                workflow['em_generation'] += 1; workflow['hb_generation'] += 1
                for key in ('em_receipt', 'evidence', 'network_fit', 'network_update', 'sp_network', 'sp_setup'):
                    workflow[key] = None
            runtime = Runtime(folder, 'cst')
            proof = handoff.verify_native(runtime, state)
            with lock(manager.root / 'registry.lock'), lock(folder / 'state.lock'):
                current = manager._state(folder, credential)
                require(current['worker_upgrade']['token'] == record['token']
                        and current['worker_upgrade']['phase'] == 'recovery_mutation_claimed'
                        and current['projects'] == data['original_projects']
                        and not alive(record['old_worker']) and alive(record['environment']), 'Restore identity changed')
                current['projects'] = state['projects']
                record = current['worker_upgrade']
                record['archive_recovery'].update(pending=False, result=result, restored_at=time.time())
                record.update(phase='stop_requested', pre_exit_native=proof,
                              projects_digest=digest(current['projects']), file_versions=handoff.file_versions(current),
                              project_digests=handoff.saved_digests(current))
                write(folder / 'session.json', current)
                return copy.deepcopy(record)
        except Exception as exc:
            with lock(folder / 'state.lock'):
                current = manager._state(folder, credential)
                current['worker_upgrade']['archive_recovery']['last_error'] = handoff.error_record(exc)
                write(folder / 'session.json', current)
            raise
