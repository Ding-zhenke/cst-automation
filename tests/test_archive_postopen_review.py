import copy
from pathlib import Path

import pytest

from test_model3d_archive_recovery import recovery
from tpc_service.sessions.store import read, write
from tpc_service.errors import ServiceError


MESSAGES = [
    {'type': 'INFO', 'text': 'It seems that the history list contains non ASCII characters. This may cause undesired effects if the CST project is used on computers with a different language setting or operating system.'},
    {'type': 'INFO', 'text': 'History block 228 contains non ASCII characters either in its name or content.'},
    {'type': 'INFO', 'text': 'Schematic window contains tasks in the navigation tree.'},
]


def opened_scene(recovery, monkeypatch):
    m, ref, folder, target, source, live, review, mod = recovery
    monkeypatch.setattr(mod, '_observe', lambda *a, **k: ({'parameters': {}, 'ports': {}}, None, None))
    m.begin_model3d_archive_recovery(ref['session_id'], ref['credential'], **review)
    m.finish_model3d_archive_recovery(ref['session_id'], ref['credential'])
    state = read(folder / 'session.json'); record = state['worker_upgrade']; data = record['archive_recovery']
    record.update(stop_ack=True, phase='recovery_mutation_claimed')
    data.update(close_intent=True, last_error=dict(code='model3d_archive_recovery_refused',
        message='Reopened project reported native messages; inspect dependencies without replay',
        details={'messages': [str(item) for item in MESSAGES]}))
    pair = target.with_suffix('')
    pair.rename(target.parent / (target.stem + '.failed-' + record['token']))
    history = pair / 'Model/3D/ModelHistory.json'
    write(history, {'history': [{'code': ['valid history']}]})
    target.write_bytes(source.read_bytes())
    (Path(data['evidence_dir']) / 'restored.cst').write_bytes(source.read_bytes())
    write(folder / 'session.json', state); live.remove(11)
    observed = dict(parameters=review['expected_parameters'], ports=review['expected_ports'],
                    history_sha256=mod.file_digest(history), reviewed_messages=copy.deepcopy(MESSAGES))
    monkeypatch.setattr(mod, '_observe', lambda *a, **k: (observed, None, None))
    monkeypatch.setattr(mod, '_restore', lambda *a: pytest.fail('Never restore again'))
    monkeypatch.setattr(mod.handoff, 'verify_native', lambda *a: dict(parameters={}, tabs=[]))
    return record['token'], observed['history_sha256']


def test_postopen_review_prepares_handoff_without_replaying_restore(recovery, monkeypatch):
    m, ref, folder, target, source, live, review, mod = recovery
    token, history_sha = opened_scene(recovery, monkeypatch)
    original_job = read(folder / 'jobs/job-original.json')
    result = m.review_model3d_archive_postopen(ref['session_id'], ref['credential'], expected_token=token,
        expected_history_sha256=history_sha, reviewed_messages=MESSAGES,
        review_note='Reviewed unicode and schematic task INFO', confirm_reopened=True, confirm_idle=True)
    assert result['phase'] == 'stop_requested' and result['archive_recovery']['pending'] is False
    assert result['return_to_fence'] is True
    assert result['archive_recovery']['postopen_reviews'][-1]['geometry_verified'] is False
    assert read(folder / 'jobs/job-original.json') == original_job
    assert read(folder / 'session.json')['status'] == 'closing'


@pytest.mark.parametrize('bad', ['warning', 'other_info', 'changed_text', 'missing_message', 'history',
    'token', 'worker_alive', 'no_close', 'source', 'staged', 'no_quarantine', 'wrong_error'])
def test_postopen_unknown_evidence_cannot_release(recovery, monkeypatch, bad):
    m, ref, folder, target, source, live, review, mod = recovery
    token, history_sha = opened_scene(recovery, monkeypatch)
    messages = copy.deepcopy(MESSAGES)
    state = read(folder / 'session.json'); data = state['worker_upgrade']['archive_recovery']
    if bad == 'warning': messages[0]['type'] = 'WARNING'
    elif bad == 'other_info': messages[0]['text'] = 'External resource was not found'
    elif bad == 'changed_text': messages[1]['text'] = messages[1]['text'].replace('228', '229')
    elif bad == 'missing_message': messages.pop()
    elif bad == 'history': history_sha = '0' * 64
    elif bad == 'token': token = 'wrong'
    elif bad == 'worker_alive': live.add(11)
    elif bad == 'no_close': data['close_intent'] = False
    elif bad == 'source': source.write_bytes(b'changed')
    elif bad == 'staged': (Path(data['evidence_dir']) / 'restored.cst').write_bytes(b'changed')
    elif bad == 'no_quarantine':
        quarantine = target.parent / (target.stem + '.failed-' + token)
        quarantine.rename(quarantine.with_name('not-the-transaction-quarantine'))
    elif bad == 'wrong_error': data['last_error']['message'] = 'Native open timed out'
    write(folder / 'session.json', state)
    with pytest.raises(ServiceError):
        m.review_model3d_archive_postopen(ref['session_id'], ref['credential'], expected_token=token,
            expected_history_sha256=history_sha, reviewed_messages=messages,
            review_note='Reviewed', confirm_reopened=True, confirm_idle=True)
    assert read(folder / 'session.json')['worker_upgrade']['archive_recovery']['pending'] is True
