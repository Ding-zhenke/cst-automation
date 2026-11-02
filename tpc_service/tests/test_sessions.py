"""Persistent sessions: real files/processes, fake only at the CST boundary."""
import time
from pathlib import Path

import pytest


def manager(root):
    from tpc_service.sessions import SessionManager
    return SessionManager(str(root.resolve()), backend='fake')


def wait_job(m, b, job, timeout=15):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        value = m.job(b['session_id'], b['credential'], job['job_id'])
        if value['status'] not in ('queued', 'running'):
            return value
        time.sleep(.05)
    pytest.fail('job did not finish: ' + str(value))


def send(m, b, request, operation, params=None, **kw):
    return m.submit(b['session_id'], b['credential'], request, operation, params, **kw)


def cleanup(m, b):
    # Fake test fixtures explicitly accept their saved baseline; this is never a native action.
    from tpc_service.sessions.native import file_digest
    state = m.status(b['session_id'], b['credential'])
    if state['status'] in ('needs_reconcile', 'close_failed') and not state.get('launch_intent'):
        m.reconcile(b['session_id'], b['credential'], 'offline fixture cleanup',
                    {pid: file_digest(p['path']) for pid, p in state['projects'].items()}, confirm_idle=True)
    result = m.close(b['session_id'], b['credential'], 'cleanup')
    wait_job(m, b, result)


def test_binding_is_durable_and_scoped(tmp_path):
    m = manager(tmp_path)
    a = m.ensure('conversation-a', 'first-a')
    assert manager(tmp_path).ensure('conversation-a', 'first-a') == a
    b = m.ensure('conversation-b', 'first-b')
    assert a['session_id'] != b['session_id']
    assert m.status(a['session_id'], a['credential'])['environment'] is None
    with pytest.raises(Exception, match='credential'):
        m.status(a['session_id'], b['credential'])
    assert not list(tmp_path.rglob('worker.log'))


def test_two_sessions_reuse_apps_and_do_not_share_projects(tmp_path):
    m = manager(tmp_path)
    bindings = [m.ensure('a', 'a'), m.ensure('b', 'b')]
    try:
        for b in bindings:
            j = send(m, b, 'new', 'create_project', {'project_id': 'same', 'project_type': 'MWS'})
            assert wait_job(m, b, j)['status'] == 'succeeded'
        states = [m.status(b['session_id'], b['credential']) for b in bindings]
        assert states[0]['worker']['pid'] != states[1]['worker']['pid']
        assert states[0]['projects']['same']['path'] != states[1]['projects']['same']['path']
        first = states[0]['environment']
        assert wait_job(m, bindings[0], send(m, bindings[0], 'again', 'inspect', {'project_id': 'same'}))['status'] == 'succeeded'
        assert m.status(bindings[0]['session_id'], bindings[0]['credential'])['environment'] == first
    finally:
        for b in bindings:
            cleanup(m, b)


def test_request_and_stage_dedup_survive_client_recreation(tmp_path):
    from tpc_service.errors import ServiceError
    m = manager(tmp_path)
    b = m.ensure('a', 'a')
    try:
        j = send(m, b, 'new', 'create_project', {'project_id': 'p'})
        assert wait_job(m, b, j)['status'] == 'succeeded'
        m = manager(tmp_path)
        assert send(m, b, 'new', 'create_project', {'project_id': 'p'})['job_id'] == j['job_id']
        assert send(m, b, 'different-request', 'create_project', {'project_id': 'p'}, operation_id='new')['job_id'] == j['job_id']
        with pytest.raises(ServiceError, match='different'):
            send(m, b, 'new', 'create_project', {'project_id': 'other'})
        assert len(m.status(b['session_id'], b['credential'])['projects']) == 1
    finally:
        cleanup(m, b)


def test_close_drains_and_refuses_new_writes(tmp_path):
    from tpc_service.errors import ServiceError
    m = manager(tmp_path)
    b = m.ensure('a', 'a')
    first = send(m, b, 'new', 'create_project', {'project_id': 'p'})
    close = m.close(b['session_id'], b['credential'], 'close')
    with pytest.raises(ServiceError, match='closing|closed'):
        send(m, b, 'too-late', 'create_project', {'project_id': 'q'})
    assert wait_job(m, b, first)['status'] == 'succeeded'
    assert wait_job(m, b, close)['status'] == 'succeeded'
    assert m.status(b['session_id'], b['credential'])['status'] == 'closed'
    assert m.close(b['session_id'], b['credential'], 'close')['job_id'] == close['job_id']


def test_root_must_be_explicit_absolute(tmp_path):
    from tpc_service.sessions import SessionManager
    with pytest.raises(ValueError, match='absolute'):
        SessionManager('relative')


def test_history_stage_id_prevents_duplicate_modeling(tmp_path):
    import hashlib
    m = manager(tmp_path)
    b = m.ensure('a', 'a')
    try:
        assert wait_job(m, b, send(m, b, 'new', 'create_project', {'project_id': 'p'}))['status'] == 'succeeded'
        code = 'With Brick\n .Create\nEnd With'
        params = {'project_id': 'p', 'stage_id': 'substrate', 'name': 'substrate', 'vba': code,
                  'preview_digest': hashlib.sha256(code.encode()).hexdigest()}
        first = send(m, b, 'history-1', 'history', params)
        assert wait_job(m, b, first)['status'] == 'succeeded'
        assert send(m, b, 'history-retry', 'history', params)['job_id'] == first['job_id']
        readback = wait_job(m, b, send(m, b, 'inspect', 'inspect', {'project_id': 'p'}))
        assert len(readback['result']['offline_model']['history']) == 1
    finally:
        cleanup(m, b)


def test_worker_loss_restores_saved_project_without_copy_or_replay(tmp_path):
    import os
    import signal
    from tpc_service.sessions.store import alive
    m = manager(tmp_path)
    b = m.ensure('a', 'a')
    try:
        assert wait_job(m, b, send(m, b, 'new', 'create_project', {'project_id': 'p'}))['status'] == 'succeeded'
        assert wait_job(m, b, send(m, b, 'params', 'set_parameters', {'project_id': 'p', 'values': {'a': 5}}))['status'] == 'succeeded'
        before = m.status(b['session_id'], b['credential'])
        os.kill(before['worker']['pid'], signal.SIGTERM)
        end = time.monotonic() + 5
        while alive(before['worker']) and time.monotonic() < end:
            time.sleep(.02)
        m = manager(tmp_path)
        m.resume(b['session_id'], b['credential'])
        readback = wait_job(m, b, send(m, b, 'read', 'inspect', {'project_id': 'p'}))
        assert readback['result']['offline_model']['parameters'] == {'a': 5}
        assert m.status(b['session_id'], b['credential'])['projects']['p']['path'] == before['projects']['p']['path']
        assert send(m, b, 'new', 'create_project', {'project_id': 'p'})['status'] == 'succeeded'
    finally:
        cleanup(m, b)


def test_launch_uncertainty_blocks_second_environment(tmp_path):
    from tpc_service.sessions.store import read, write
    m = manager(tmp_path)
    b = m.ensure('a', 'a')
    path = tmp_path / b['session_id'] / 'session.json'
    state = read(path)
    state['launch_intent'] = True
    write(path, state)
    m.resume(b['session_id'], b['credential'])
    end = time.monotonic() + 5
    while m.status(b['session_id'], b['credential'])['status'] != 'needs_reconcile' and time.monotonic() < end:
        time.sleep(.03)
    with pytest.raises(Exception, match='uncertain'):
        send(m, b, 'new', 'create_project', {'project_id': 'p'})
    state = m.status(b['session_id'], b['credential'])
    assert state['environment'] is None
    # Only terminate the fake worker created by this test; no DE exists.
    import os
    import signal
    os.kill(state['worker']['pid'], signal.SIGTERM)


def test_concurrent_launch_produces_one_worker_and_ordered_jobs(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    m = manager(tmp_path)
    b = m.ensure('a', 'a')
    try:
        with ThreadPoolExecutor(max_workers=4) as pool:
            jobs = list(pool.map(lambda i: send(m, b, str(i), 'create_project', {'project_id': 'p' + str(i)}), range(4)))
        results = [wait_job(m, b, j) for j in jobs]
        assert all(j['status'] == 'succeeded' for j in results)
        state = m.status(b['session_id'], b['credential'])
        assert len({j['sequence'] for j in state['jobs']}) == 4
        assert len(state['projects']) == 4
        assert 'session_locked' not in (tmp_path / b['session_id'] / 'worker.log').read_text()
    finally:
        cleanup(m, b)


def test_malformed_history_rejected_before_starting_worker(tmp_path):
    m = manager(tmp_path)
    b = m.ensure('a', 'a')
    with pytest.raises(Exception, match='preview'):
        send(m, b, 'bad', 'history', {'project_id': 'p', 'stage_id': 'x', 'name': 'x', 'vba': 'bad'})
    assert m.status(b['session_id'], b['credential'])['worker'] is None


def test_duplicate_stage_remembers_alias_request_id(tmp_path):
    m = manager(tmp_path)
    b = m.ensure('a', 'a')
    try:
        j = send(m, b, 'r1', 'create_project', {'project_id': 'p'}, operation_id='stage')
        assert wait_job(m, b, j)['status'] == 'succeeded'
        assert send(m, b, 'r2', 'create_project', {'project_id': 'p'}, operation_id='stage')['job_id'] == j['job_id']
        with pytest.raises(Exception, match='different'):
            send(m, b, 'r2', 'create_project', {'project_id': 'q'}, operation_id='other')
    finally:
        cleanup(m, b)


def test_saved_checkpoint_recovers_missing_completion_receipt(tmp_path):
    import os
    import signal
    from tpc_service.sessions.store import alive, read, write
    m = manager(tmp_path)
    b = m.ensure('a', 'a')
    try:
        assert wait_job(m, b, send(m, b, 'new', 'create_project', {'project_id': 'p'}))['status'] == 'succeeded'
        j = send(m, b, 'params', 'set_parameters', {'project_id': 'p', 'values': {'a': 5}})
        assert wait_job(m, b, j)['status'] == 'succeeded'
        worker = m.status(b['session_id'], b['credential'])['worker']
        os.kill(worker['pid'], signal.SIGTERM)
        end = time.monotonic() + 5
        while alive(worker) and time.monotonic() < end:
            time.sleep(.02)
        job_path = tmp_path / b['session_id'] / 'jobs' / (j['job_id'] + '.json')
        saved = read(job_path)
        saved.update(status='running', result=None)
        write(job_path, saved)
        m.resume(b['session_id'], b['credential'])
        recovered = wait_job(m, b, j)
        assert recovered['status'] == 'succeeded'
        assert recovered['recovered_from_checkpoint'] is True
    finally:
        cleanup(m, b)


def test_unknown_work_fenced_until_explicit_reconciliation(tmp_path):
    from tpc_service.sessions.store import read, write
    from tpc_service.sessions.native import file_digest
    m = manager(tmp_path)
    b = m.ensure('a', 'a')
    try:
        assert wait_job(m, b, send(m, b, 'new', 'create_project', {'project_id': 'p'}))['status'] == 'succeeded'
        path = tmp_path / b['session_id'] / 'session.json'
        # Model the known failure state, without executing another native operation.
        from tpc_service.sessions.store import lock
        with lock(path.parent / 'state.lock'):
            state = read(path)
            state.update(status='needs_reconcile', uncertain_jobs=[])
            write(path, state)
        with pytest.raises(Exception, match='uncertain'):
            send(m, b, 'next', 'set_parameters', {'project_id': 'p', 'values': {'a': 1}})
        project = state['projects']['p']
        with pytest.raises(Exception, match='digest'):
            m.reconcile(b['session_id'], b['credential'], 'human-review', {'p': 'incorrect'})
        m.reconcile(b['session_id'], b['credential'], 'human-review', {'p': file_digest(project['path'])}, confirm_idle=True)
        assert wait_job(m, b, send(m, b, 'next', 'set_parameters', {'project_id': 'p', 'values': {'a': 1}}))['status'] == 'succeeded'
    finally:
        cleanup(m, b)


def test_restart_preserves_failure_fence(tmp_path):
    import os
    import signal
    from tpc_service.sessions.store import alive
    m = manager(tmp_path)
    b = m.ensure('a', 'a')
    try:
        assert wait_job(m, b, send(m, b, 'new', 'create_project', {'project_id': 'p'}))['status'] == 'succeeded'
        failed = wait_job(m, b, send(m, b, 'solve', 'solve', {'project_id': 'p'}))
        assert failed['status'] == 'failed'
        state = m.status(b['session_id'], b['credential'])
        os.kill(state['worker']['pid'], signal.SIGTERM)
        end = time.monotonic() + 5
        while alive(state['worker']) and time.monotonic() < end:
            time.sleep(.02)
        m.resume(b['session_id'], b['credential'])
        time.sleep(.5)
        assert m.status(b['session_id'], b['credential'])['status'] == 'needs_reconcile'
        with pytest.raises(Exception, match='uncertain'):
            send(m, b, 'bad-replay', 'set_parameters', {'project_id': 'p', 'values': {'a': 9}})
    finally:
        cleanup(m, b)


def test_close_preserves_uncertain_predecessor_fence(tmp_path, monkeypatch):
    from tpc_service.sessions.store import read, write
    m = manager(tmp_path)
    b = m.ensure('a', 'a')
    path = tmp_path / b['session_id'] / 'session.json'
    state = read(path)
    state.update(status='needs_reconcile', uncertain_jobs=['unknown'])
    write(path, state)
    monkeypatch.setattr(m, '_launch', lambda *a, **kw: None)
    m.close(b['session_id'], b['credential'], 'close')
    assert m.status(b['session_id'], b['credential'])['status'] == 'needs_reconcile'
    assert m.status(b['session_id'], b['credential'])['close_requested'] is True


def test_reconciliation_cannot_adopt_another_sessions_environment(tmp_path):
    import os
    from tpc_service.sessions.store import read, write, process_identity
    m = manager(tmp_path)
    a, b = m.ensure('a', 'a'), m.ensure('b', 'b')
    identity = process_identity(os.getpid())
    path = tmp_path / b['session_id'] / 'session.json'
    state = read(path)
    state['environment'] = identity
    write(path, state)
    path = tmp_path / a['session_id'] / 'session.json'
    state = read(path)
    state.update(status='needs_reconcile', launch_intent=True)
    write(path, state)
    with pytest.raises(Exception, match='another session'):
        m.reconcile(a['session_id'], a['credential'], 'reviewed', {}, confirm_idle=True,
                    environment_identity=identity)


def test_failed_unsaved_project_can_be_explicitly_abandoned(tmp_path, monkeypatch):
    from tpc_service.sessions.store import read, write
    m = manager(tmp_path)
    b = m.ensure('a', 'a')
    path = tmp_path / b['session_id'] / 'session.json'
    state = read(path)
    state.update(status='needs_reconcile', launch_intent=True,
                 projects={'p': {'path': str(tmp_path / b['session_id'] / 'missing.cst'), 'saved': False}})
    write(path, state)
    monkeypatch.setattr(m, '_launch', lambda *a, **kw: None)
    result = m.reconcile(b['session_id'], b['credential'], 'confirmed no DE or saved project', {},
                         confirm_idle=True, confirm_no_environment=True, abandon_projects=['p'])
    assert result['status'] == 'ready'
    assert result['projects'] == {}
