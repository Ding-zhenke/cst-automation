import copy
from pathlib import Path

import pytest

from tpc_service.sessions import SessionManager
from tpc_service.sessions.native import file_digest
from tpc_service.sessions.store import read, write
from tpc_service.errors import ServiceError


@pytest.fixture
def recovery(tmp_path, monkeypatch):
    from tpc_service.sessions import model3d_archive_recovery as mod
    manager = SessionManager(str(tmp_path / 'sessions'))
    ref = manager.ensure('recovery', 'one')
    folder = manager._folder(ref['session_id'])
    target = tmp_path / 'project' / 'model.cst'
    target.parent.mkdir()
    target.write_bytes(b'failed saved file')
    pair = target.with_suffix('')
    pair.mkdir()
    (pair / 'failed-history').write_text('bad')
    source = tmp_path / 'good.cst'
    source.write_bytes(b'good native archive')
    worker = dict(pid=11, started=1, image='python.exe')
    de = dict(pid=22, started=2, image='cst.exe')
    error = dict(code='session_operation_failed', message='Native returned error', details=dict(diagnostics=dict(
        job_id='job-original', operation='model_api', message_truncated=False,
        message='An error occurred while trying to execute add_to_history:\n(&H8000ffff) Out of range.\n(MeshAdaption3D.MinPasses "1")')))
    job = dict(job_id='job-original', session_id=ref['session_id'], operation='model_api',
               params={'project_id': 'p'}, status='failed', finished_at=1, error=error,
               sequence=1, request_id='original', operation_id='original')
    write(folder / 'jobs' / 'job-original.json', job)
    state = read(folder / 'session.json')
    state.update(status='needs_reconcile', worker=worker, environment=de, last_error=error,
                 worker_capabilities=['cooperative-worker-upgrade-v1'], projects={
                     'p': dict(project_id='p', path=str(target), saved=True,
                               saved_digest=file_digest(source))})
    write(folder / 'session.json', state)
    live = {11, 22}
    monkeypatch.setattr(mod, 'alive', lambda v: bool(v and v['pid'] in live))
    monkeypatch.setattr('tpc_service.sessions.native_handoff.alive', mod.alive)
    monkeypatch.setattr(manager, '_launch', lambda *a, **kw: pytest.fail('Unexpected launch'))
    review = dict(project_id='p', failed_job_id=job['job_id'],
                  environment_identity=de, worker_identity=worker,
                  registered_digest=file_digest(source), current_digest=file_digest(target),
                  source_path=str(source), source_digest=file_digest(source),
                  expected_parameters={'a': {'value': 1, 'expression': '1'}},
                  expected_ports={'1': {'type': 'Discrete', 'number_of_modes': 0}},
                  forbidden_history_fragment='MinPasses "1"', review_note='Reviewed archive recovery',
                  confirm_idle=True, confirm_discard=True, accept_worker_exit_risk=True)
    return manager, ref, folder, target, source, live, review, mod


@pytest.mark.parametrize('kind,modes,valid', [('Discrete', 0, True), ('Waveguide', 1, True),
    ('Waveguide', 0, False), ('Discrete', -1, False), ('Discrete', False, False), ('Discrete', 0.0, False)])
def test_expected_port_mode_contract(recovery, kind, modes, valid):
    m, ref, folder, target, source, live, review, mod = recovery
    review['expected_ports']['1'] = {'type': kind, 'number_of_modes': modes}
    if valid:
        mod._validate(review)
        assert review['expected_ports']['1']['number_of_modes'] == modes
    else:
        with pytest.raises(ServiceError): mod._validate(review)


@pytest.mark.parametrize('bad', ['digest', 'source', 'running', 'identity', 'confirmation', 'job', 'extra_project', 'timeout'])
def test_invalid_recovery_does_not_freeze_or_connect(recovery, monkeypatch, bad):
    m, ref, folder, target, source, live, review, mod = recovery
    state = read(folder / 'session.json')
    if bad == 'digest': review['current_digest'] = '0' * 64
    elif bad == 'source': source.write_bytes(b'changed')
    elif bad == 'running':
        write(folder / 'jobs' / 'job-active.json', dict(job_id='job-active', status='running'))
    elif bad == 'identity': live.remove(11)
    elif bad == 'confirmation': review['confirm_discard'] = False
    elif bad == 'job': review['failed_job_id'] = 'job-missing'
    elif bad == 'timeout':
        job = read(folder / 'jobs' / 'job-original.json')
        job['error']['details']['diagnostics']['message'] = 'Timed out waiting for native call'
        state['last_error'] = job['error']
        write(folder / 'jobs' / 'job-original.json', job)
        write(folder / 'session.json', state)
    else:
        state['projects']['other'] = copy.deepcopy(state['projects']['p'])
        write(folder / 'session.json', state)
    monkeypatch.setattr(mod, '_observe', lambda *a, **k: pytest.fail('Native access'))
    before = read(folder / 'session.json')
    with pytest.raises(ServiceError): m.begin_model3d_archive_recovery(ref['session_id'], ref['credential'], **review)
    assert read(folder / 'session.json') == before


def test_freeze_blocks_existing_paths(recovery, monkeypatch):
    m, ref, folder, target, source, live, review, mod = recovery
    m.begin_model3d_archive_recovery(ref['session_id'], ref['credential'], **review)
    for op in ['start', 'inspect', 'close']:
        with pytest.raises(ServiceError):
            m.submit(ref['session_id'], ref['credential'], op, op, {'project_id': 'p'} if op == 'inspect' else {})
    with pytest.raises(ServiceError): m.resume(ref['session_id'], ref['credential'])
    with pytest.raises(ServiceError): m.reconcile(ref['session_id'], ref['credential'], 'no', {'p': review['current_digest']}, confirm_idle=True)
    with pytest.raises(ServiceError): m.finish_native_worker_handoff(ref['session_id'], ref['credential'])
    assert target.read_bytes() == b'failed saved file'


def test_checkpoint_and_wait_do_not_close_old_worker(recovery, monkeypatch):
    m, ref, folder, target, source, live, review, mod = recovery
    monkeypatch.setattr(mod, '_observe', lambda *a, **k: ({'parameters': {}, 'ports': {}}, None, None))
    m.begin_model3d_archive_recovery(ref['session_id'], ref['credential'], **review)
    result = m.finish_model3d_archive_recovery(ref['session_id'], ref['credential'])
    assert result['phase'] == 'stop_requested'
    snapshot = Path(result['archive_recovery']['evidence_dir']) / 'before'
    assert (snapshot / 'project.cst').read_bytes() == target.read_bytes()
    assert (snapshot / 'companion' / 'failed-history').read_text() == 'bad'
    monkeypatch.setattr(mod, '_restore', lambda *a: pytest.fail('Worker still alive'))
    assert m.finish_model3d_archive_recovery(ref['session_id'], ref['credential'])['phase'] == 'stop_requested'


def test_closed_registrations_preserved_without_reopen(recovery, monkeypatch):
    m, ref, folder, target, source, live, review, mod = recovery
    state = read(folder / 'session.json')
    other = target.parent / 'closed.cst'; other.write_bytes(b'closed native archive')
    closed = dict(project_id='closed', path=str(other), saved=True, saved_digest=file_digest(other), tab_closed=True)
    state['projects']['closed'] = closed
    write(folder / 'session.json', state)
    monkeypatch.setattr(mod, '_observe', lambda *a, **k: ({'parameters': {}, 'ports': {}}, None, None))
    m.begin_model3d_archive_recovery(ref['session_id'], ref['credential'], **review)
    m.finish_model3d_archive_recovery(ref['session_id'], ref['credential'])
    assert read(folder / 'session.json')['projects']['closed'] == closed
    assert other.read_bytes() == b'closed native archive'


def test_nested_closed_reference_is_rejected_before_freeze(recovery, monkeypatch):
    m, ref, folder, target, source, live, review, mod = recovery
    state = read(folder / 'session.json')
    other = target.with_suffix('') / 'reference.cst'; other.write_bytes(b'closed reference')
    state['projects']['closed'] = dict(project_id='closed', path=str(other), saved=True,
                                      saved_digest=file_digest(other), tab_closed=True)
    write(folder / 'session.json', state)
    monkeypatch.setattr(mod, '_observe', lambda *a, **k: pytest.fail('No native access'))
    with pytest.raises(ServiceError):
        m.begin_model3d_archive_recovery(ref['session_id'], ref['credential'], **review)
    assert read(folder / 'session.json') == state
    assert other.read_bytes() == b'closed reference'


def test_mutation_failure_is_not_replayed(recovery, monkeypatch):
    m, ref, folder, target, source, live, review, mod = recovery
    monkeypatch.setattr(mod, '_observe', lambda *a, **k: ({'parameters': {}, 'ports': {}}, None, None))
    m.begin_model3d_archive_recovery(ref['session_id'], ref['credential'], **review)
    m.finish_model3d_archive_recovery(ref['session_id'], ref['credential'])
    state = read(folder / 'session.json'); state['worker_upgrade']['stop_ack'] = True
    write(folder / 'session.json', state); live.remove(11)
    calls = []
    def fail(*args):
        calls.append(True)
        raise RuntimeError('close returned unknown')
    monkeypatch.setattr(mod, '_restore', fail)
    with pytest.raises(RuntimeError): m.finish_model3d_archive_recovery(ref['session_id'], ref['credential'])
    with pytest.raises(ServiceError): m.finish_model3d_archive_recovery(ref['session_id'], ref['credential'])
    assert calls == [True]
    assert read(folder / 'jobs' / 'job-original.json')['status'] == 'failed'


@pytest.mark.parametrize('failure', [None, 'close', 'source_changed', 'companion_changed', 'reopen', 'native'])
def test_restore_quarantines_all_failed_files_and_never_saves_or_retries(recovery, monkeypatch, failure):
    from types import SimpleNamespace
    m, ref, folder, target, source, live, review, mod = recovery
    m.begin_model3d_archive_recovery(ref['session_id'], ref['credential'], **review)
    state = read(folder / 'session.json'); record = state['worker_upgrade']
    proof = {'parameters': {}, 'ports': {}}
    record['archive_recovery']['pre_exit_scene'] = proof
    record['phase'] = 'recovery_mutation_claimed'
    write(folder / 'session.json', state)
    live.remove(11)
    mod._backup(target, Path(record['archive_recovery']['evidence_dir']))
    calls = []; tabs = [str(target)]
    def close():
        calls.append('close')
        if failure == 'close': raise RuntimeError('native close failure')
        tabs.clear()
    def open_project(path):
        calls.append('open')
        assert path == str(target)
        assert target.read_bytes() == b'good native archive'
        assert not target.with_suffix('').exists()
        if failure == 'reopen': raise RuntimeError('missing external dependency')
        tabs.append(path)
        target.with_suffix('').mkdir()
        (target.with_suffix('') / 'new-native').write_text('fresh')
    app = SimpleNamespace(project=SimpleNamespace(list_open_projects=lambda: tabs, open_project=open_project))
    handle = SimpleNamespace(close=close)
    def observe(*args, restored=False):
        if restored and failure == 'native': raise RuntimeError('restored parameter mismatch')
        return proof, app, handle
    monkeypatch.setattr(mod, '_observe', observe)
    monkeypatch.setattr('cst_solver.dialogs.check_dialogs', lambda **kw: None)
    if failure == 'source_changed': source.write_bytes(b'changed')
    if failure == 'companion_changed': (target.with_suffix('') / 'late').write_text('changed')
    if failure:
        with pytest.raises((ServiceError, RuntimeError)): mod._restore(folder, state)
        assert calls.count('close') <= 1 and calls.count('open') <= 1
        if failure in ('source_changed', 'companion_changed'): assert calls == []
    else:
        result = mod._restore(folder, state)
        assert calls == ['close', 'open']
        assert (Path(result['quarantine']) / 'failed-history').read_text() == 'bad'
        assert not (target.with_suffix('') / 'failed-history').exists()
        assert result['restored_digest'] == review['source_digest']
    before = Path(record['archive_recovery']['evidence_dir']) / 'before'
    assert (before / 'project.cst').read_bytes() == b'failed saved file'
    assert (before / 'companion' / 'failed-history').read_text() == 'bad'


def test_success_keeps_failure_and_invalidates_evidence_before_handoff(recovery, monkeypatch):
    m, ref, folder, target, source, live, review, mod = recovery
    state = read(folder / 'session.json')
    state['projects']['p']['workflow'] = dict(em_generation=3, hb_generation=4, network_required=True,
        em_receipt={'old': True}, evidence={'old': True}, network_fit={'old': True}, network_update={'old': True})
    write(folder / 'session.json', state)
    original = read(folder / 'jobs' / 'job-original.json')
    proof = {'parameters': {}, 'ports': {}}
    monkeypatch.setattr(mod, '_observe', lambda *a, **kw: (proof, None, None))
    m.begin_model3d_archive_recovery(ref['session_id'], ref['credential'], **review)
    m.finish_model3d_archive_recovery(ref['session_id'], ref['credential'])
    state = read(folder / 'session.json'); state['worker_upgrade']['stop_ack'] = True
    write(folder / 'session.json', state); live.remove(11)
    def restore(*args):
        target.write_bytes(source.read_bytes())
        return {'native': proof}
    monkeypatch.setattr(mod, '_restore', restore)
    monkeypatch.setattr(mod.handoff, 'verify_native', lambda *a: proof)
    result = m.finish_model3d_archive_recovery(ref['session_id'], ref['credential'])
    assert result['archive_recovery']['pending'] is False
    state = read(folder / 'session.json')
    assert state['status'] == 'closing' and state['worker'] == review['worker_identity']
    assert read(folder / 'jobs' / 'job-original.json') == original
    assert state['last_error'] == original['error']
    workflow = state['projects']['p']['workflow']
    assert workflow['em_generation'] == 4 and workflow['hb_generation'] == 5
    assert workflow['em_receipt'] is None and workflow['network_fit'] is None
    assert workflow['network_required'] is True


def test_new_worker_release_returns_to_original_fence(recovery, monkeypatch):
    import time
    from tpc_service.sessions.store import digest
    m, ref, folder, target, source, live, review, mod = recovery
    m.begin_model3d_archive_recovery(ref['session_id'], ref['credential'], **review)
    state = read(folder / 'session.json'); record = state['worker_upgrade']
    # Synthetic completed admission, using the existing token-bound release logic.
    state['projects']['p']['saved_digest'] = file_digest(target)
    new = dict(pid=33, started=3, image='python.exe'); live.add(33); live.remove(11)
    proof = {'parameters': {}}
    state.update(worker=new, worker_capabilities=[mod.handoff.CAPABILITY])
    record['archive_recovery']['pending'] = False
    record.update(phase='release_verified', projects_digest=digest(state['projects']),
        file_versions=mod.handoff.file_versions(state), project_digests={'p': file_digest(target)},
        new_worker_ready=new, new_worker_native=proof, pre_exit_native=proof,
        release_worker=new, release_native=proof, release_ack='token', release_token='token',
        release_verified_at=time.time())
    write(folder / 'session.json', state)
    assert m.finish_model3d_archive_recovery(ref['session_id'], ref['credential'])['phase'] == 'complete'
    state = read(folder / 'session.json')
    assert state['status'] == 'needs_reconcile' and not state.get('worker_upgrade')
    assert read(folder / 'jobs' / 'job-original.json')['status'] == 'failed'


@pytest.mark.parametrize('case', ['str', 'lines', 'forbidden', 'forbidden_lines', 'missing_history',
                                'bad_history', 'params', 'ports', 'messages', 'running', 'unknown_idle',
                                'reviewed_infos', 'unexpected_info', 'warning_after_review'])
def test_restored_native_checks_use_full_parameters_ports_history_and_messages(recovery, monkeypatch, case):
    from types import SimpleNamespace
    from tpc_service.sessions.project_lifecycle import path_key
    m, ref, folder, target, source, live, review, mod = recovery
    m.begin_model3d_archive_recovery(ref['session_id'], ref['credential'], **review)
    state = read(folder / 'session.json')
    code = 'MeshAdaption3D.MinPasses "2"'
    if case in ('forbidden', 'forbidden_lines'): code = review['forbidden_history_fragment']
    if case in ('lines', 'forbidden_lines'): code = ['MeshSettings.SetMeshType "Tet"', code]
    if case == 'bad_history': code = [None]
    if case != 'missing_history': write(target.with_suffix('') / 'Model/3D/ModelHistory.json', {'history': [{'code': code}]})
    running = True if case == 'running' else None if case == 'unknown_idle' else False
    handle = SimpleNamespace(model3d=SimpleNamespace(is_solver_running=lambda **kw: running), filename=lambda: str(target))
    reviewed = None
    actual_messages = ['INFO missing dependency'] if case == 'messages' else []
    if case in ('reviewed_infos', 'unexpected_info', 'warning_after_review'):
        from tpc_service.sessions.archive_postopen import UNICODE_INFO, TASKS_INFO
        reviewed = [dict(type='INFO', text=UNICODE_INFO),
                    dict(type='INFO', text='History block 228 contains non ASCII characters either in its name or content.'),
                    dict(type='INFO', text=TASKS_INFO)]
        actual_messages = copy.deepcopy(reviewed)
        if case == 'unexpected_info': actual_messages[0]['text'] = 'Missing external library'
        if case == 'warning_after_review': actual_messages[0]['type'] = 'WARNING'
    app = SimpleNamespace(cst_file=handle, project=SimpleNamespace(list_open_projects=lambda: [str(target)]),
                          get_messages=lambda: actual_messages)
    monkeypatch.setattr('tpc_service.sessions.read_review.borrow_open_project', lambda *args: (app, handle, {path_key(target): str(target)}))
    monkeypatch.setattr('cst_solver.dialogs.check_dialogs', lambda **kw: None)
    monkeypatch.setattr('tpc_service.sessions.inspection.inspect_native', lambda *args: dict(errors=[], parameters={} if case == 'params' else review['expected_parameters']))
    monkeypatch.setattr('cst_solver.simulation.port_replacement.port_inventory', lambda *args: {} if case == 'ports' else review['expected_ports'])
    if case in ('str', 'lines', 'reviewed_infos'):
        proof, _, _ = mod._observe(folder, state, restored=True, reviewed_messages=reviewed)
        assert proof['parameters'] == review['expected_parameters']
        assert proof['ports'] == review['expected_ports']
    else:
        with pytest.raises(ServiceError): mod._observe(folder, state, restored=True, reviewed_messages=reviewed)
