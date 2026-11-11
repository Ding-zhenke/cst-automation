from pathlib import Path
import pytest

from test_model3d_archive_recovery import recovery
from tpc_service.sessions.store import read, write
from tpc_service.errors import ServiceError


def stopped_scene(recovery, monkeypatch):
    m, ref, folder, target, source, live, review, recovery_mod = recovery
    proof = {'parameters': {}, 'ports': {}}
    monkeypatch.setattr(recovery_mod, '_observe', lambda *a, **kw: (proof, None, None))
    m.begin_model3d_archive_recovery(ref['session_id'], ref['credential'], **review)
    m.finish_model3d_archive_recovery(ref['session_id'], ref['credential'])
    state = read(folder / 'session.json'); record = state['worker_upgrade']
    record.update(stop_ack=True, phase='recovery_mutation_claimed')
    record['archive_recovery']['last_error'] = dict(code='model3d_archive_recovery_refused',
        message='Failed companion changed since its verified backup', details={})
    write(folder / 'session.json', state); live.remove(11)
    return record['token']


def test_review_preserves_full_deltas_and_resumes_same_token(recovery, monkeypatch):
    m, ref, folder, target, source, live, review, mod = recovery
    token = stopped_scene(recovery, monkeypatch)
    temp = target.with_suffix('') / 'Temp/DataStore/SimProps'
    temp.mkdir(parents=True)
    (temp / 'registry.db').write_bytes(b'new temp registry')
    (temp / '482da3b6-2ce2-4fbd-be5f-a7912e385e43').write_bytes(b'new temp object')
    original_job = read(folder / 'jobs/job-original.json')
    result = m.review_model3d_archive_drift(ref['session_id'], ref['credential'],
        expected_token=token, review_note='Reviewed exact preclose Temp drift', confirm_preclose=True)
    assert result['phase'] == 'stop_requested' and result['token'] == token
    audit = result['archive_recovery']['preclose_drift_reviews'][-1]
    report = read(Path(audit['path']) / 'report.json')
    assert len(report['changes']) == 2 and report['full_content_comparison'] is True
    assert (Path(audit['path']) / 'delta/Temp/DataStore/SimProps/registry.db').read_bytes() == b'new temp registry'
    assert read(folder / 'jobs/job-original.json') == original_job
    assert target.read_bytes() == b'failed saved file'


@pytest.mark.parametrize('change', ['model', 'result', 'unknown_temp', 'nested_uuid', 'wrong_error',
    'close_intent', 'worker_alive', 'token', 'backup', 'source'])
def test_unknown_drift_or_possible_close_never_unclaims_mutation(recovery, monkeypatch, change):
    m, ref, folder, target, source, live, review, mod = recovery
    token = stopped_scene(recovery, monkeypatch)
    state = read(folder / 'session.json'); data = state['worker_upgrade']['archive_recovery']
    if change in ('model', 'result', 'unknown_temp', 'nested_uuid'):
        names = dict(model='Model/Parameters.json', result='Result/curve.sig', unknown_temp='Temp/unknown',
                     nested_uuid='Temp/DataStore/SimProps/nested/482da3b6-2ce2-4fbd-be5f-a7912e385e43')
        file = target.with_suffix('') / names[change]; file.parent.mkdir(parents=True, exist_ok=True); file.write_bytes(b'changed')
    elif change == 'wrong_error': data['last_error']['message'] = 'Open failed after close'
    elif change == 'close_intent': data['close_intent'] = True
    elif change == 'worker_alive': live.add(11)
    elif change == 'token': token = 'wrong'
    elif change == 'backup': (Path(data['evidence_dir']) / 'before/project.cst').write_bytes(b'corrupt')
    elif change == 'source': source.write_bytes(b'changed')
    write(folder / 'session.json', state)
    with pytest.raises(ServiceError):
        m.review_model3d_archive_drift(ref['session_id'], ref['credential'], expected_token=token,
                                      review_note='Review exact preclose drift', confirm_preclose=True)
    assert read(folder / 'session.json')['worker_upgrade']['phase'] == 'recovery_mutation_claimed'
    assert target.read_bytes() == b'failed saved file'


@pytest.mark.parametrize('new_change', ['temp', 'model'])
def test_next_restore_rechecks_drift_after_native_observation_before_close(recovery, monkeypatch, new_change):
    from types import SimpleNamespace
    m, ref, folder, target, source, live, review, mod = recovery
    token = stopped_scene(recovery, monkeypatch)
    m.review_model3d_archive_drift(ref['session_id'], ref['credential'], expected_token=token,
                                 review_note='Explicit Temp drift acceptance', confirm_preclose=True)
    state = read(folder / 'session.json'); state['worker_upgrade']['phase'] = 'recovery_mutation_claimed'
    write(folder / 'session.json', state)
    proof = state['worker_upgrade']['archive_recovery']['pre_exit_scene']
    tabs = [str(target)]; calls = []
    def close():
        assert read(folder / 'session.json')['worker_upgrade']['archive_recovery']['close_intent'] is True
        calls.append('close'); tabs.clear()
    def open_project(path):
        calls.append('open'); tabs.append(path)
    app = SimpleNamespace(project=SimpleNamespace(list_open_projects=lambda: tabs, open_project=open_project))
    handle = SimpleNamespace(close=close)
    def observe(*args, restored=False):
        if not restored:
            name = 'Temp/DataStore/SimProps/registry.db' if new_change == 'temp' else 'Model/Parameters.json'
            file = target.with_suffix('') / name; file.parent.mkdir(parents=True, exist_ok=True)
            file.write_bytes(b'native observation caused new bytes')
        return proof, app, handle
    monkeypatch.setattr(mod, '_observe', observe)
    monkeypatch.setattr('cst_solver.dialogs.check_dialogs', lambda **kw: None)
    if new_change == 'model':
        with pytest.raises(ServiceError): mod._restore(folder, state)
        assert calls == []
    else:
        result = mod._restore(folder, state)
        assert calls == ['close', 'open']
        data = read(folder / 'session.json')['worker_upgrade']['archive_recovery']
        audit = data['preclose_drift_checks'][-1]
        assert (Path(audit['path']) / 'delta/Temp/DataStore/SimProps/registry.db').read_bytes() == b'native observation caused new bytes'
        assert (Path(result['quarantine']) / 'Temp/DataStore/SimProps/registry.db').exists()
