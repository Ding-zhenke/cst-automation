"""Explicit read-only acceptance of a specific reopened project's INFO messages."""
import ast
import copy
from pathlib import Path
import re
import time
from uuid import uuid4

from . import model3d_archive_recovery as recovery
from .archive_drift import checked_backup
from .native import Runtime, file_digest
from .store import digest, lock, read, write

MESSAGE_REFUSAL = 'Reopened project reported native messages; inspect dependencies without replay'
UNICODE_INFO = ('It seems that the history list contains non ASCII characters. This may cause undesired effects '
                'if the CST project is used on computers with a different language setting or operating system.')
TASKS_INFO = 'Schematic window contains tasks in the navigation tree.'


def validate_infos(messages):
    recovery.require(isinstance(messages, list) and len(messages) == 3, 'Exactly three reviewed INFO messages required')
    for item in messages:
        recovery.require(isinstance(item, dict) and set(item) == {'text', 'type'} and item['type'] == 'INFO'
            and isinstance(item['text'], str) and 0 < len(item['text']) <= 2048, 'Only complete typed INFO messages accepted')
    recovery.require(messages[0]['text'] == UNICODE_INFO and messages[2]['text'] == TASKS_INFO
        and re.fullmatch(r'History block [1-9][0-9]* contains non ASCII characters either in its name or content\.', messages[1]['text']),
        'Unknown INFO category; explicit review does not waive dependency or warning errors')
    return copy.deepcopy(messages)


def _original_messages(error):
    raw = error.get('details', {}).get('messages')
    recovery.require(isinstance(raw, list) and len(raw) == 3, 'Original message refusal must preserve all messages')
    result = []
    for item in raw:
        recovery.require(isinstance(item, str) and len(item) <= 4096, 'Unsupported original message representation')
        try:
            result.append(ast.literal_eval(item))
        except (ValueError, SyntaxError) as exc:
            raise recovery.ServiceError('model3d_archive_recovery_refused', 'Original message snapshot is not readable') from exc
    return validate_infos(result)


def review(manager, session_id, credential, *, expected_token, expected_history_sha256,
           reviewed_messages, review_note, confirm_reopened=False, confirm_idle=False):
    messages = validate_infos(reviewed_messages)
    recovery.require(confirm_reopened is True and confirm_idle is True and isinstance(review_note, str)
        and 0 < len(review_note.strip()) <= 8192 and isinstance(expected_history_sha256, str)
        and re.fullmatch('[0-9a-f]{64}', expected_history_sha256), 'Explicit reopened/idle review and exact history digest required')
    folder = manager._folder(session_id)
    with lock(folder / 'handoff.lock'):
        def check(state):
            record = state.get('worker_upgrade') or {}; data = record.get('archive_recovery') or {}
            recovery.require(state['status'] == 'closing' and record.get('mode') == recovery.handoff.MODE
                and record.get('phase') == 'recovery_mutation_claimed' and record.get('token') == expected_token
                and record.get('stop_ack') and data.get('pending') is True and data.get('close_intent') is True
                and not data.get('result') and not recovery.alive(record.get('old_worker')),
                'Exact stopped-worker already-reopened transaction required')
            error = data.get('last_error') or {}
            recovery.require(error.get('code') == 'model3d_archive_recovery_refused' and error.get('message') == MESSAGE_REFUSAL
                             and _original_messages(error) == messages, 'Original reopen refusal/messages differ from review')
            # This is a read-only check of the GOOD file now present, not a change
            # to the original bad baseline recorded in the recovery transaction.
            options = dict(data['review'], current_digest=data['review']['source_digest'])
            target, _, _ = recovery._preflight(folder, state, options)
            evidence = recovery._plain(data['evidence_dir'])
            quarantine = recovery._plain(target.parent / (target.stem + '.failed-' + record['token']))
            recovery.require(quarantine.is_dir() and (evidence / 'restored.cst').is_file()
                and file_digest(evidence / 'restored.cst') == options['source_digest'], 'Verified restore staging/quarantine required')
            history = recovery._plain(target.with_suffix('') / 'Model/3D/ModelHistory.json')
            recovery.require(history.is_file() and file_digest(history) == expected_history_sha256, 'Reopened native history differs from review')
            return target, evidence, quarantine
        with lock(manager.root / 'registry.lock'), lock(folder / 'state.lock'):
            state = manager._state(folder, credential)
            target, evidence, quarantine = check(state)
        checked_backup(state)
        preserved = recovery._manifest(quarantine, exclude_native_lock=True)
        excluded_lock = recovery._lock_exclusion(quarantine)
        native, _, _ = recovery._observe(folder, state, restored=True, reviewed_messages=messages)
        recovery.require(native['history_sha256'] == expected_history_sha256, 'History changed during native readback')
        prepared = recovery._restored_handoff_state(state)
        handoff_proof = recovery.handoff.verify_native(Runtime(folder, 'cst'), prepared)
        again, _, _ = recovery._observe(folder, state, restored=True, reviewed_messages=messages)
        recovery.require(again == native and recovery._manifest(quarantine, exclude_native_lock=True) == preserved
                         and recovery._lock_exclusion(quarantine) == excluded_lock, 'Native state or preserved failed files changed')
        with lock(manager.root / 'registry.lock'), lock(folder / 'state.lock'):
            current = manager._state(folder, credential)
            check(current)
            recovery.require(current == state, 'Recovery state changed during postopen review')
        audit = evidence / 'postopen-review' / uuid4().hex
        audit.mkdir(parents=True, exist_ok=False)
        report = dict(token=expected_token, at=time.time(), review_note=review_note, native=native,
                      reviewed_messages=messages, original_error=state['worker_upgrade']['archive_recovery']['last_error'],
                      source_digest=state['worker_upgrade']['archive_recovery']['review']['source_digest'],
                      current_digest=file_digest(target), history_sha256=expected_history_sha256,
                      quarantine=str(quarantine), quarantine_manifest=preserved, quarantine_digest=digest(preserved),
                      quarantine_excluded_companion=excluded_lock,
                      geometry_verified=False, solver_verified=False, external_dependencies_verified=False,
                      schematic_idle_asserted_by_caller=True, restore_replayed=False)
        write(audit / 'report.json', report)
        result = dict(native=native, quarantine=str(quarantine), restored_digest=report['source_digest'],
                      geometry_verified=False, solver_verified=False, postopen_review=True)
        receipt = dict(path=str(audit), report_sha256=file_digest(audit / 'report.json'),
                       geometry_verified=False, solver_verified=False, restore_replayed=False)
        return recovery._commit_handoff(manager, folder, credential, prepared, result, handoff_proof, postopen_audit=receipt)
