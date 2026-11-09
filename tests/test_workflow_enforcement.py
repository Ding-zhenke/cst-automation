"""Exercise real queue/dispatch gates; native boundaries must stay untouched on rejection."""
import copy
import hashlib
import json
from types import SimpleNamespace

import pytest

from tpc_service.errors import ServiceError
from tpc_service.sessions.manager import SessionManager
from tpc_service.sessions.store import read, write


def spec():
    return {'schema_version': 1,
            'parameters': {'width': {'value': 2, 'affects': 'em'},
                           'length': {'min': 1, 'max': 10, 'affects': 'em'},
                           'bias': {'min': 0, 'max': 3, 'affects': 'hb'}},
            'initial_values': {'width': 2, 'length': 4, 'bias': 1},
            'em_checks': [{'source': 'parameter', 'name': 'width', 'expected': 2}],
            'hb_checks': [{'source': 'block_property', 'name': 'RF', 'property': 'R', 'expected': 75}],
            'hb_task': 'Sweep', 'hb_request': {'mode': 'network'},
            'evidence_rules': {'fmin_hz': {'min': 0, 'max': 0},
                               'fmax_hz': {'min': 2e9}, 'fit_error': {'min': 0, 'max': 0.01}}}


@pytest.fixture
def setup(tmp_path, monkeypatch):
    manager = SessionManager(str(tmp_path.resolve()), backend='cst')
    ref = manager.ensure('test', 'test')
    folder = tmp_path / ref['session_id']
    path = folder / 'projects/p/model.cst'
    path.parent.mkdir(parents=True)
    path.write_bytes(b'fixture')
    state = read(folder / 'session.json')
    state.update(status='ready', projects={'p': {'project_id': 'p', 'path': str(path), 'saved': True,
                     'saved_digest': hashlib.sha256(path.read_bytes()).hexdigest()}})
    write(folder / 'session.json', state)
    launches = []
    monkeypatch.setattr(manager, '_launch', lambda *a, **k: launches.append(a))
    return manager, ref, folder, path, launches


def bind(setup):
    manager, ref, *_ = setup
    return manager.bind_workflow(ref['session_id'], ref['credential'], 'p', spec())


def submit(setup, operation, params, request='request'):
    manager, ref, *_ = setup
    return manager.submit(ref['session_id'], ref['credential'], request, operation, dict(project_id='p', **params))


def test_missing_contract_cannot_launch_cst(setup):
    with pytest.raises(ServiceError) as caught:
        submit(setup, 'solve', {})
    assert caught.value.code == 'workflow_required'
    assert setup[-1] == []
    assert not list((setup[2] / 'jobs').glob('*.json'))


@pytest.mark.parametrize('values', [{'width': 3}, {'length': 11}, {'length': 'width*2'},
                                   {'missing': 1}, {'length': float('nan')}, {'length': True}])
def test_bad_parameter_request_never_launches(setup, values):
    bind(setup)
    with pytest.raises((ServiceError, ValueError)):
        submit(setup, 'set_parameters', {'values': values})
    assert setup[-1] == []


def test_spec_cannot_be_changed_while_work_is_queued(setup):
    revision = bind(setup)['revision']
    submit(setup, 'set_parameters', {'values': {'length': 5}})
    manager, ref, *_ = setup
    changed = spec()
    changed['parameters']['width']['value'] = 3
    changed['initial_values']['width'] = 3
    with pytest.raises(ServiceError):
        manager.bind_workflow(ref['session_id'], ref['credential'], 'p', changed, expected_revision=revision)


def test_hb_without_em_evidence_never_launches(setup):
    bind(setup)
    with pytest.raises(ServiceError) as caught:
        submit(setup, 'circuit', {'kind': 'solve', 'settings': {
            'operation': 'run_task', 'task_name': 'Sweep', 'mode': 'network',
            'expected_results': [{'tree_path': r'Tasks\Sweep\S', 'run_id': 0}]}})
    assert caught.value.code == 'workflow_evidence_required'
    assert setup[-1] == []


def test_queue_revision_is_checked_before_project_acquisition(setup):
    from tpc_service.sessions.operations import execute
    bind(setup)
    job = submit(setup, 'solve', {})
    folder = setup[2]
    state = read(folder / 'session.json')
    state['projects']['p']['workflow']['revision'] = 'changed'
    write(folder / 'session.json', state)
    def unexpected(*args):
        pytest.fail('CST project acquisition must not occur')
    runtime = SimpleNamespace(folder=folder, backend='cst', state=lambda: read(folder/'session.json'), project=unexpected)
    with pytest.raises(ServiceError) as caught:
        execute(runtime, job)
    assert caught.value.code == 'workflow_stale_request'


def test_raw_history_cannot_bypass_bound_contract(setup):
    bind(setup)
    code = 'Solver.Start'
    with pytest.raises(ServiceError) as caught:
        submit(setup, 'history', {'stage_id': 'raw', 'name': 'raw', 'vba': code,
                                  'preview_digest': hashlib.sha256(code.encode()).hexdigest()})
    assert caught.value.code == 'workflow_route_unsupported'
    assert setup[-1] == []


def runtime_for(setup, app=None):
    from tpc_service.sessions.native import Runtime
    runtime = Runtime(setup[2], 'cst')
    runtime.project = lambda project_id: (app, runtime.state()['projects'][project_id])
    runtime.save = lambda app, project_id: runtime.state()['projects'][project_id]
    return runtime


def native_app(**values):
    parameters = dict(spec()['initial_values'], **values)
    obj = SimpleNamespace(DoesExist=lambda: True, GetProperty=lambda name: 75)
    return SimpleNamespace(get_parameter=parameters.__getitem__,
        cst_file=SimpleNamespace(model3d=SimpleNamespace(RestoreParameterExpression=lambda n: str(parameters[n]))),
        circuit=SimpleNamespace(adapter=SimpleNamespace(select=lambda *a: obj)),
        run_checked=lambda **k: {'status': 'succeeded'})


def prepare_em_evidence(setup):
    from tpc_service.sessions.operations import execute
    from tpc_service.sessions.workflow import record_success
    bind(setup)
    job = submit(setup, 'solve', {}, 'em')
    runtime = runtime_for(setup, native_app())
    result = execute(runtime, job)
    record_success(runtime, job)
    job.update(status='succeeded', result=result)
    write(setup[2] / 'jobs' / (job['job_id'] + '.json'), job)
    artifact = setup[2] / 'matrix.csv'
    artifact.write_text('synthetic numerical source')
    path = setup[2] / 'analysis.json'
    report = {'em_job_id': job['job_id'], 'em_saved_digest': runtime.state()['projects']['p']['saved_digest'],
              'metrics': {'fmin_hz': 0, 'fmax_hz': 3e9, 'fit_error': .001},
              'artifacts': [{'path': str(artifact), 'sha256': hashlib.sha256(artifact.read_bytes()).hexdigest()}]}
    write(path, report)
    return runtime, job, path, artifact


def accept_evidence(setup):
    from tpc_service.sessions.operations import execute
    runtime, em, path, artifact = prepare_em_evidence(setup)
    job = submit(setup, 'accept_workflow_evidence', {'em_job_id': em['job_id'], 'report_path': str(path)}, 'accept')
    runtime.project = lambda *a: pytest.fail('Evidence acceptance must not access CST')
    result = execute(runtime, job)
    job.update(status='succeeded', result=result)
    write(setup[2] / 'jobs' / (job['job_id'] + '.json'), job)
    return runtime, artifact


def hb(setup, request='hb', **settings):
    return submit(setup, 'circuit', {'kind': 'solve', 'settings': dict(
        operation='run_task', task_name='Sweep', mode='network', expected_results=[{'tree_path': r'Tasks\Sweep\S', 'run_id': 0}], **settings)}, request)


def test_legal_chain_calls_hb_only_after_native_checks(setup, monkeypatch):
    from tpc_service.sessions import operations
    runtime, _ = accept_evidence(setup)
    app = native_app()
    runtime.project = lambda *a: (app, runtime.state()['projects']['p'])
    called = []
    monkeypatch.setattr(operations, 'circuit', lambda *a: called.append('HB') or {'ok': True})
    assert operations.execute(runtime, hb(setup)) == {'ok': True}
    assert called == ['HB']


@pytest.mark.parametrize('change', ['artifact', 'report', 'geometry', 'rerun'])
def test_stale_em_evidence_cannot_launch_hb(setup, change):
    from tpc_service.sessions.workflow import invalidate
    runtime, artifact = accept_evidence(setup)
    if change == 'artifact':
        artifact.write_text('changed')
    elif change == 'report':
        path = setup[2] / 'analysis.json'
        report = read(path)
        report['metrics']['fit_error'] = .002
        write(path, report)
    else:
        invalidate(runtime, {'operation': 'solve' if change == 'rerun' else 'set_parameters',
                             'params': {'project_id': 'p', 'values': {'length': 5}}})
    setup[-1].clear()
    with pytest.raises(ServiceError):
        hb(setup)
    assert not setup[-1]


def test_hb_only_parameter_preserves_matching_em(setup):
    from tpc_service.sessions.workflow import invalidate
    runtime, _ = accept_evidence(setup)
    invalidate(runtime, {'operation': 'set_parameters', 'params': {'project_id': 'p', 'values': {'bias': 2}}})
    assert hb(setup)['status'] == 'queued'


@pytest.mark.parametrize('metrics', [{'fit_error': .1}, {'fmin_hz': 1}, {'fmax_hz': 1e9}, {'fit_error': True}])
def test_invalid_numerical_report_no_launch(setup, metrics):
    runtime, em, path, _ = prepare_em_evidence(setup)
    report = read(path)
    report['metrics'].update(metrics)
    write(path, report)
    setup[-1].clear()
    with pytest.raises(ServiceError):
        submit(setup, 'accept_workflow_evidence', {'em_job_id': em['job_id'], 'report_path': str(path)}, 'bad-evidence')
    assert not setup[-1]


def test_native_mismatch_never_starts_solver(setup):
    from tpc_service.sessions.operations import execute
    bind(setup)
    app = native_app(width=3)
    app.run_checked = lambda **k: pytest.fail('Solver must not start')
    with pytest.raises(ServiceError, match='Native parameter'):
        execute(runtime_for(setup, app), submit(setup, 'solve', {}))


def test_old_live_worker_refuses_new_request_without_restart(setup, monkeypatch):
    from tpc_service.sessions import workflow
    bind(setup)
    state = read(setup[2] / 'session.json')
    state['worker'] = {'pid': 123}
    write(setup[2] / 'session.json', state)
    monkeypatch.setattr(workflow, 'alive', lambda identity: True)
    with pytest.raises(ServiceError) as caught:
        submit(setup, 'solve', {})
    assert caught.value.code == 'workflow_worker_upgrade_required'
    assert not setup[-1]
    assert read(setup[2] / 'session.json')['worker'] == {'pid': 123}


def test_legacy_backend_cannot_open_protected_project(setup, monkeypatch):
    import cst_solver
    from tpc_service.backends.cst_backend import CstBackend
    bind(setup)
    monkeypatch.setattr(cst_solver, 'setup', lambda *a: pytest.fail('Legacy route must not open CST'))
    result = CstBackend().solve(project={'path': str(setup[3])}, params={}, job={})
    assert result['ok'] is False


def test_legacy_circuit_cannot_open_protected_project(setup):
    from tpc_service.circuit import register_circuit_handlers
    bind(setup)
    handlers = {}
    service = SimpleNamespace(workdir=str(setup[2]), register_workflow=lambda name, routes, **k: handlers.update(routes))
    register_circuit_handlers(service, app_factory=lambda *a: pytest.fail('Legacy circuit must not open CST'))
    result = handlers['solve'](project={'path': str(setup[3])}, params={'operation': 'run_task',
        'task_name': 'Sweep', 'mode': 'network', 'expected_results': [{}]}, job={'kind': 'solve'}, backend=None)
    assert result['ok'] is False


def test_revision_update_requires_compare_and_swap(setup):
    original = bind(setup)
    updated = spec()
    updated['parameters']['length']['max'] = 9
    manager, ref, *_ = setup
    with pytest.raises(ServiceError) as caught:
        manager.bind_workflow(ref['session_id'], ref['credential'], 'p', updated)
    assert caught.value.code == 'workflow_revision_conflict'
    result = manager.bind_workflow(ref['session_id'], ref['credential'], 'p', updated, expected_revision=original['revision'])
    assert result['revision'] != original['revision']
    assert not setup[-1]


def test_cli_binding_and_rejection_share_service_gate(setup, monkeypatch, capsys):
    from tpc_service.sessions.__main__ import main
    monkeypatch.setattr(SessionManager, '_launch', lambda *a, **k: pytest.fail('CLI must not launch'))
    manager, ref, folder, *_ = setup
    reference, specification, params = folder/'reference.json', folder/'spec.json', folder/'params.json'
    write(reference, ref)
    write(specification, spec())
    write(params, {'project_id': 'p', 'values': {'width': 3}})
    common = ['--root', str(manager.root), '--reference', str(reference)]
    assert main(common + ['bind-workflow', '--project-id', 'p', '--spec-file', str(specification)]) == 0
    assert main(common + ['submit', '--request-id', 'bad', '--operation', 'set_parameters', '--params-file', str(params)]) == 1
    assert 'workflow_parameter_invalid' in capsys.readouterr().err


def test_mcp_binding_and_rejection_share_service_gate(setup, monkeypatch):
    from cst_mcp import tools
    from cst_mcp.session_tools import register_session_tools
    for name in ('TOOL_SPECS', 'HANDLERS', 'READ_TOOLS', 'WRITE_TOOLS'):
        monkeypatch.setattr(tools, name, getattr(tools, name).copy())
    monkeypatch.setattr(SessionManager, '_launch', lambda *a, **k: pytest.fail('MCP must not launch'))
    manager, ref, *_ = setup
    register_session_tools(str(manager.root), replace=True)
    identity = {k: ref[k] for k in ('session_id', 'credential')}
    assert tools.dispatch('bind_cst_workflow', dict(identity, project_id='p', spec=spec()))['ok']
    result = tools.dispatch('submit_cst_session_operation', dict(identity, request_id='bad',
        operation='set_parameters', params={'project_id': 'p', 'values': {'length': 20}}))
    assert not result['ok']
    assert 'workflow_parameter_invalid' in str(result)


def test_worker_preserves_state_on_pre_native_gate_failure(setup):
    from tpc_service.sessions.operations import execute
    from tpc_service.sessions.worker import _finish_failed_job
    bind(setup)
    job = submit(setup, 'solve', {})
    state = read(setup[2] / 'session.json')
    state['projects']['p']['workflow']['em_generation'] += 1
    write(setup[2] / 'session.json', state)
    runtime = runtime_for(setup)
    runtime.project = lambda *a: pytest.fail('Preflight failure must not acquire CST')
    with pytest.raises(ServiceError) as caught:
        execute(runtime, job)
    _finish_failed_job(job, caught.value.to_dict(), state)
    assert state['status'] == 'ready'
    assert job['status'] == 'failed'


def test_failed_native_parameter_write_invalidates_evidence(setup):
    from tpc_service.sessions.operations import execute
    runtime, _ = accept_evidence(setup)
    app = native_app()
    def fail(*args):
        assert runtime.state()['projects']['p']['workflow']['evidence'] is None
        raise RuntimeError('native write failed')
    app.para = fail
    runtime.project = lambda *a: (app, runtime.state()['projects']['p'])
    job = submit(setup, 'set_parameters', {'values': {'length': 5}}, 'change')
    with pytest.raises(RuntimeError, match='native write failed'):
        execute(runtime, job)
    setup[-1].clear()
    with pytest.raises(ServiceError):
        hb(setup)
    assert not setup[-1]


@pytest.mark.parametrize('results', [None, [], [{}], [{'tree_path': r'Tasks\Sweep\S', 'run_id': True}],
                                     [{'tree_path': r'Tasks\Sweep\S', 'run_id': -1}],
                                     [{'tree_path': r'Tasks\Other\S', 'run_id': 0}]])
def test_malformed_hb_results_rejected_before_launch(setup, results):
    accept_evidence(setup)
    setup[-1].clear()
    with pytest.raises(ServiceError) as caught:
        submit(setup, 'circuit', {'kind': 'solve', 'settings': {'operation': 'run_task',
            'task_name': 'Sweep', 'mode': 'network', 'expected_results': results}}, 'malformed')
    assert caught.value.code == 'workflow_hb_request_mismatch'
    assert not setup[-1]


@pytest.mark.parametrize('expressions', [[], {'missing': 'description'}, {'length': 1}])
def test_bad_parameter_descriptions_rejected_before_cst(setup, expressions):
    bind(setup)
    with pytest.raises(ServiceError):
        submit(setup, 'set_parameters', {'values': {'length': 5}, 'expressions': expressions})
    assert not setup[-1]


def test_curve_sweep_geometry_not_confused_with_parameter_sweep(setup):
    from tpc_service.sessions.workflow import preflight
    bind(setup)
    state = read(setup[2] / 'session.json')
    params = {'project_id': 'p', 'calls': [{'method': 'sweep_curve'}]}
    assert preflight(setup[2], state, 'model_api', params)['revision']
    params['calls'] = [{'method': 'configure_sweep'}]
    with pytest.raises(ServiceError) as caught:
        preflight(setup[2], state, 'model_api', params)
    assert caught.value.code == 'workflow_route_unsupported'
