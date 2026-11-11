import time

import pytest

from tpc_service.errors import ServiceError
from tpc_service.sessions import SessionManager
from tpc_service.sessions.store import read, write, alive


def wait_for(predicate, timeout=15):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        value = predicate()
        if value:
            return value
        time.sleep(.05)
    pytest.fail('timed out waiting for fake worker')


def test_cooperative_upgrade_freezes_queue_and_preserves_audit(tmp_path):
    m = SessionManager(str(tmp_path), backend='fake')
    ref = m.ensure('upgrade', 'one'); sid, cred = ref['session_id'], ref['credential']
    job = m.submit(sid, cred, 'start', 'start')
    wait_for(lambda: m.job(sid, cred, job['job_id'])['status'] == 'succeeded')
    folder = tmp_path/sid; before = read(folder/'jobs'/(job['job_id']+'.json'))
    old = m.status(sid, cred)['worker']
    result = m.begin_worker_upgrade(sid, cred, confirm_idle=True,
                                    required_capabilities=['model-band-no-rebuild-v1'])
    assert result['phase'] == 'stop_requested'
    with pytest.raises(ServiceError): m.submit(sid, cred, 'new', 'start')
    wait_for(lambda: not alive(old))
    wait_for(lambda: m.finish_worker_upgrade(sid, cred)['phase'] == 'complete')
    state = m.status(sid, cred)
    assert state['status'] == 'ready' and state['worker'] != old
    assert m.finish_worker_upgrade(sid, cred)['phase'] == 'complete'
    assert read(folder/'jobs'/(job['job_id']+'.json')) == before
    close = m.close(sid, cred, 'close')
    wait_for(lambda: m.job(sid, cred, close['job_id'])['status'] == 'succeeded')


def test_legacy_worker_refused_without_freezing(tmp_path, monkeypatch):
    m = SessionManager(str(tmp_path), backend='fake'); ref = m.ensure('legacy', 'one')
    folder = tmp_path/ref['session_id']; state = read(folder/'session.json')
    state.update(status='ready', worker={'pid':1}, worker_capabilities=[])
    write(folder/'session.json', state)
    monkeypatch.setattr('tpc_service.sessions.manager.alive', lambda _: True)
    with pytest.raises(ServiceError) as e:
        m.begin_worker_upgrade(ref['session_id'], ref['credential'], confirm_idle=True)
    assert e.value.code == 'worker_upgrade_unsupported'
    assert read(folder/'session.json') == state


def test_submission_and_freeze_are_serialized(tmp_path, monkeypatch):
    import threading
    from tpc_service.sessions.manager import UPGRADE_CAPABILITY
    m = SessionManager(str(tmp_path), backend='fake'); ref = m.ensure('race', 'one')
    folder = tmp_path/ref['session_id']; state = read(folder/'session.json')
    state.update(status='ready', worker={'pid':1}, worker_capabilities=[UPGRADE_CAPABILITY])
    write(folder/'session.json', state)
    monkeypatch.setattr('tpc_service.sessions.manager.alive', lambda _: True)
    monkeypatch.setattr(m, '_launch', lambda *a, **k: None)
    barrier = threading.Barrier(2); results = {}
    def run(name, action):
        barrier.wait()
        try:
            results[name] = action()
        except ServiceError as exc:
            results[name] = exc.code
    a = threading.Thread(target=run, args=('freeze', lambda: m.begin_worker_upgrade(ref['session_id'], ref['credential'], confirm_idle=True)))
    b = threading.Thread(target=run, args=('submit', lambda: m.submit(ref['session_id'], ref['credential'], 'request', 'start')))
    a.start(); b.start(); a.join(10); b.join(10)
    assert not a.is_alive() and not b.is_alive()
    assert ((isinstance(results['freeze'], dict) and results['submit'] == 'session_closing')
            or (results['freeze'] == 'session_busy' and isinstance(results['submit'], dict)))


def test_no_stop_ack_cannot_advance_or_unfreeze(tmp_path, monkeypatch):
    from tpc_service.sessions.manager import UPGRADE_CAPABILITY
    m = SessionManager(str(tmp_path), backend='fake'); ref = m.ensure('ack', 'one')
    folder = tmp_path/ref['session_id']; state = read(folder/'session.json')
    state.update(status='ready', worker={'pid':1}, worker_capabilities=[UPGRADE_CAPABILITY])
    write(folder/'session.json', state)
    monkeypatch.setattr('tpc_service.sessions.manager.alive', lambda _: True)
    m.begin_worker_upgrade(ref['session_id'], ref['credential'], confirm_idle=True)
    assert m.finish_worker_upgrade(ref['session_id'], ref['credential'])['phase'] == 'stop_requested'
    assert read(folder/'session.json')['status'] == 'closing'


def test_live_native_environment_blocks_upgrade(tmp_path, monkeypatch):
    from tpc_service.sessions.manager import UPGRADE_CAPABILITY
    m = SessionManager(str(tmp_path), backend='cst'); ref = m.ensure('native', 'one')
    folder = tmp_path/ref['session_id']; state = read(folder/'session.json')
    state.update(status='ready', worker={'pid':1}, environment={'pid':2}, worker_capabilities=[UPGRADE_CAPABILITY])
    write(folder/'session.json', state)
    monkeypatch.setattr('tpc_service.sessions.manager.alive', lambda _: True)
    with pytest.raises(ServiceError) as exc:
        m.begin_worker_upgrade(ref['session_id'], ref['credential'], confirm_idle=True)
    assert exc.value.code == 'worker_upgrade_live_de_unverified'
    assert read(folder/'session.json') == state


def test_missing_capability_and_changed_project_keep_freeze(tmp_path, monkeypatch):
    from tpc_service.sessions.manager import UPGRADE_CAPABILITY
    from tpc_service.sessions.store import digest
    m = SessionManager(str(tmp_path), backend='fake'); ref = m.ensure('required', 'one')
    folder = tmp_path/ref['session_id']; state = read(folder/'session.json')
    new = {'pid':2}; old = {'pid':1}
    state.update(status='closing', worker=new, worker_capabilities=[UPGRADE_CAPABILITY],
                 worker_upgrade={'phase':'starting', 'old_worker':old, 'new_worker_ready':new,
                                 'environment':None, 'projects_digest':digest({}),
                                 'required_capabilities':['unavailable']})
    write(folder/'session.json', state)
    monkeypatch.setattr('tpc_service.sessions.manager.alive', lambda _: True)
    assert m.finish_worker_upgrade(ref['session_id'], ref['credential'])['phase'] == 'starting'
    assert read(folder/'session.json')['status'] == 'closing'
    state['projects'] = {'changed': {'path':'different'}}
    write(folder/'session.json', state)
    with pytest.raises(ServiceError): m.finish_worker_upgrade(ref['session_id'], ref['credential'])
    assert read(folder/'session.json')['status'] == 'closing'


def test_uncertain_launch_is_not_repeated(tmp_path, monkeypatch):
    from tpc_service.sessions.store import digest
    m = SessionManager(str(tmp_path), backend='fake'); ref = m.ensure('uncertain-launch', 'one')
    folder = tmp_path/ref['session_id']; state = read(folder/'session.json')
    state.update(status='closing', worker=None, worker_upgrade={
        'phase':'starting', 'old_worker':{'pid':1}, 'launch_attempted':True,
        'environment':None, 'projects_digest':digest({}), 'required_capabilities':[]})
    write(folder/'session.json', state)
    monkeypatch.setattr(m, '_launch', lambda *a, **k: pytest.fail('must not repeat uncertain launch'))
    assert m.finish_worker_upgrade(ref['session_id'], ref['credential'])['phase'] == 'starting'
    assert read(folder/'session.json')['status'] == 'closing'
