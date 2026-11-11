"""Explicit, narrowly scoped review of a proven pre-close archive refusal."""
import copy
from pathlib import Path
import re
import shutil
import time
from uuid import uuid4

from . import model3d_archive_recovery as recovery
from .native import file_digest
from .store import lock, read, write

PRE_CLOSE_MESSAGE = 'Failed companion changed since its verified backup'


def checked_backup(state):
    data = state['worker_upgrade']['archive_recovery']
    evidence = recovery._plain(data['evidence_dir'])
    manifest = read(evidence / 'before_manifest.json') or {}
    recovery.require(manifest.get('project') == data['review']['current_digest']
        and file_digest(evidence / 'before/project.cst') == manifest['project']
        and isinstance(manifest.get('companion'), dict)
        and recovery._manifest(evidence / 'before/companion') == manifest['companion'],
        'Original full backup is missing or changed')
    return evidence, manifest


def permitted_temp(name):
    return bool(re.fullmatch(r'Temp/DataStore/SimProps/(?:registry\.db|'
                            r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})', name))


def capture_delta(state, *, purpose):
    """Hash all files, preserve every changed Temp file, then recheck full hashes."""
    record = state['worker_upgrade']; data = record['archive_recovery']
    evidence, baseline = checked_backup(state)
    pair = Path(state['projects'][data['review']['project_id']]['path']).with_suffix('')
    current = recovery._manifest(pair, exclude_native_lock=True)
    recovery.require(isinstance(current, dict), 'Original companion disappeared')
    changes = {name: dict(before=baseline['companion'].get(name), current=current.get(name))
               for name in sorted(set(baseline['companion']) | set(current))
               if baseline['companion'].get(name) != current.get(name)}
    forbidden = [name for name in changes if not permitted_temp(name)]
    recovery.require(not forbidden, 'Non-permitted companion content changed: ' + ', '.join(forbidden[:10]))
    audit = evidence / 'preclose-drift' / uuid4().hex
    audit.mkdir(parents=True, exist_ok=False)
    for name, change in changes.items():
        if change['current'] is not None:
            source = recovery._plain(pair / name)
            destination = audit / 'delta' / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
            recovery.require(file_digest(destination) == change['current'], 'Temp file changed during delta copy')
    recovery.require(recovery._manifest(pair, exclude_native_lock=True) == current,
                     'Companion changed during full delta review; no close is authorized')
    report = dict(token=record['token'], purpose=purpose, at=time.time(), full_content_comparison=True,
                  baseline_manifest_sha256=file_digest(evidence / 'before_manifest.json'),
                  current_manifest=current, changes=changes, excluded_companion=recovery._lock_exclusion(pair),
                  policy='exact_simprops_registry_or_uuid_leaf_only', old_contents_retained_in='before/companion')
    write(audit / 'report.json', report)
    return dict(path=str(audit), report_sha256=file_digest(audit / 'report.json'))


def verify_approval(state):
    record = state['worker_upgrade']; data = record['archive_recovery']
    reviews = data.get('preclose_drift_reviews') or []
    recovery.require(bool(reviews), 'Explicit preclose drift review required')
    latest = reviews[-1]
    path = recovery._plain(latest['path'])
    expected_parent = recovery._plain(Path(data['evidence_dir']) / 'preclose-drift')
    recovery.require(path.parent == expected_parent and file_digest(path / 'report.json') == latest['report_sha256'],
                     'Preclose drift review artifact changed')
    report = read(path / 'report.json') or {}
    recovery.require(report.get('token') == record['token'] and report.get('purpose') == 'explicit_preclose_review'
        and report.get('full_content_comparison') is True
        and report.get('baseline_manifest_sha256') == file_digest(Path(data['evidence_dir']) / 'before_manifest.json'),
        'Preclose drift review does not bind this backup and transaction')


def review(manager, session_id, credential, *, expected_token, review_note, confirm_preclose=False):
    recovery.require(confirm_preclose is True and isinstance(review_note, str)
                     and 0 < len(review_note.strip()) <= 8192, 'Explicit preclose review required')
    folder = manager._folder(session_id)
    with lock(folder / 'handoff.lock'):
        def check(state):
            record = state.get('worker_upgrade') or {}; data = record.get('archive_recovery') or {}
            recovery.require(state['status'] == 'closing' and record.get('mode') == recovery.handoff.MODE
                and record.get('phase') == 'recovery_mutation_claimed' and record.get('token') == expected_token
                and record.get('stop_ack') and data.get('pending') is True and not data.get('close_intent')
                and not data.get('result') and not recovery.alive(record.get('old_worker')),
                'Exact stopped-worker preclose transaction required')
            error = data.get('last_error') or {}
            recovery.require(error.get('code') == 'model3d_archive_recovery_refused'
                and error.get('message') == PRE_CLOSE_MESSAGE,
                'Only the known backup comparison refusal is eligible; ambiguous close cannot resume')
            target, _, _ = recovery._preflight(folder, state, data['review'])
            evidence = recovery._plain(data['evidence_dir'])
            recovery.require(not (evidence / 'restored.cst').exists() and not (evidence / 'restored_native.json').exists()
                and not (target.parent / (target.stem + '.failed-' + record['token'])).exists(),
                'Restore artifacts exist; cannot establish preclose state')
            return record
        with lock(manager.root / 'registry.lock'), lock(folder / 'state.lock'):
            state = manager._state(folder, credential); record = check(state)
        checked_backup(state)
        proof, _, _ = recovery._observe(folder, state)
        recovery.require(proof == record['archive_recovery']['pre_exit_scene'], 'Original native scene changed')
        audit = capture_delta(state, purpose='explicit_preclose_review')
        with lock(manager.root / 'registry.lock'), lock(folder / 'state.lock'):
            current = manager._state(folder, credential); record = check(current)
            data = record['archive_recovery']
            data.setdefault('preclose_drift_reviews', []).append(dict(audit, review_note=review_note,
                previous_error=copy.deepcopy(data['last_error']), reviewed_at=time.time()))
            record['phase'] = 'stop_requested'
            write(folder / 'session.json', current)
            return copy.deepcopy(record)
