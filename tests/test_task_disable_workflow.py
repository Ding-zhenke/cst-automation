"""Real queue, MCP and workflow guards for the disable-only configuration route."""
import pytest
from test_workflow_enforcement import setup, bind, submit, runtime_for
from tpc_service.sessions.store import read, write
from tpc_service.errors import ServiceError


def settings():
    return {'operation': 'disable_tasks', 'tasks': [
        {'task_name': 'Scan', 'expected_type': 'parameter sweep', 'expected_enabled': True}],
        'confirm_idle': True, 'review_note': 'Reviewed native idle'}


def test_old_worker_refused_before_job_or_launch(setup):
    manager, ref, folder, path, launches = setup
    state = read(folder / 'session.json')
    state.update(worker={'pid': 123}, worker_capabilities=[])
    write(folder / 'session.json', state)
    with pytest.raises(ServiceError) as exc:
        submit(setup, 'circuit', {'kind': 'build', 'settings': settings()})
    assert exc.value.code == 'workflow_worker_upgrade_required'
    assert not launches and not list((folder / 'jobs').glob('*.json'))


@pytest.mark.parametrize('change, code', [('generation', 'workflow_stale_request'),
    ('digest', 'workflow_project_changed'), ('owner', 'workflow_owner_mismatch')])
def test_bound_disable_keeps_generation_digest_and_owner_guards(setup, change, code):
    from tpc_service.sessions.operations import execute
    bind(setup)
    job = submit(setup, 'circuit', {'kind': 'build', 'settings': settings()})
    state = read(setup[2] / 'session.json')
    state['worker_capabilities'] = ['disable-native-tasks-v1']
    if change == 'generation':
        state['projects']['p']['workflow']['hb_generation'] += 1
    elif change == 'digest':
        setup[3].write_bytes(b'changed outside session')
    else:
        from tpc_service.sessions.workflow import marker
        write(marker(setup[3]), {'project_id': 'other'})
    write(setup[2] / 'session.json', state)
    runtime = runtime_for(setup)
    runtime.project = lambda *a: pytest.fail('Stale request acquired CST')
    with pytest.raises(ServiceError) as exc:
        execute(runtime, job)
    assert exc.value.code == code


def test_disable_invalidates_hb_but_preserves_em_generation(setup):
    from tpc_service.sessions.workflow import invalidate
    bind(setup)
    runtime = runtime_for(setup)
    before = runtime.state()['projects']['p']['workflow']
    job = {'operation': 'circuit', 'params': {'project_id': 'p', 'kind': 'build', 'settings': settings()}}
    invalidate(runtime, job)
    after = runtime.state()['projects']['p']['workflow']
    assert after['hb_generation'] == before['hb_generation'] + 1
    assert after['em_generation'] == before['em_generation']
    assert after['network_update'] is None


@pytest.mark.parametrize('valid', [True, False])
def test_registered_mcp_route_rejects_bad_requests_without_launch(tmp_path, monkeypatch, valid):
    from cst_mcp import tools
    from cst_mcp.session_tools import register_session_tools
    from tpc_service.sessions.manager import SessionManager
    for name in ('TOOL_SPECS', 'HANDLERS', 'READ_TOOLS', 'WRITE_TOOLS'):
        monkeypatch.setattr(tools, name, getattr(tools, name).copy())
    def launch(*args, **kw):
        if not valid:
            pytest.fail('Invalid request started worker')
    monkeypatch.setattr(SessionManager, '_launch', launch)
    register_session_tools(str(tmp_path.resolve()), backend='fake')
    ref = tools.dispatch('ensure_cst_session', {'binding': 'disable', 'request_id': 'ensure'})['session']
    data = settings()
    if not valid:
        data['tasks'][0]['expected_enabled'] = 'True'
    out = tools.dispatch('submit_cst_session_operation', dict(session_id=ref['session_id'],
        credential=ref['credential'], request_id='disable', operation='circuit',
        params={'project_id': 'p', 'kind': 'build', 'settings': data}))
    assert out['ok'] is valid
    if valid:
        assert out['job']['params']['settings'] == data
    else:
        assert not list((tmp_path / ref['session_id'] / 'jobs').glob('*.json'))
