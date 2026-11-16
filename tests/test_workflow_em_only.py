import pytest
from cst_automation.workflow import normalize
from tpc_service.errors import ServiceError
from tpc_service.sessions import workflow


def em_spec():
    return {'schema_version': 2, 'mode': 'em_only',
            'parameters': {'width': {'value': 2, 'affects': 'em'}},
            'initial_values': {'width': 2},
            'em_checks': [{'source': 'parameter', 'name': 'width', 'expected': 2}],
            'evidence_rules': {'error': {'max': 0.01}}}


def test_em_only_accepts_explicit_contract_without_hb():
    assert normalize(em_spec()) == em_spec()


def test_em_only_rejects_hb_fields_and_parameters():
    spec = em_spec()
    spec['hb_task'] = 'fake'
    with pytest.raises(ValueError): normalize(spec)
    spec = em_spec()
    spec['parameters']['width']['affects'] = 'hb'
    with pytest.raises(ValueError): normalize(spec)


def test_old_worker_cannot_bind_new_mode(monkeypatch):
    monkeypatch.setattr(workflow, 'alive', lambda _: True)
    with pytest.raises(ServiceError) as exc:
        workflow.check_worker({'worker': 1, 'worker_capabilities': ['parameter-em-hb-v1']}, em_spec())
    assert exc.value.code == 'workflow_worker_upgrade_required'

from test_workflow_enforcement import setup, submit


def test_em_only_binds_and_refuses_circuit_solve(setup):
    manager, ref, *_ = setup
    manager.bind_workflow(ref['session_id'], ref['credential'], 'p', em_spec())
    with pytest.raises(ServiceError) as exc:
        submit(setup, 'circuit', {'kind': 'solve', 'settings': {
            'operation': 'run_task', 'task_name': 'Any', 'mode': 'network',
            'expected_results': [{'tree_path': r'Tasks\Any\S', 'run_id': 0}]}})
    assert exc.value.code == 'workflow_route_unsupported'
    assert setup[-1] == []


def test_em_only_checks_worker_capability_at_execution(setup):
    from tpc_service.sessions.operations import execute
    from test_workflow_enforcement import runtime_for, native_app
    manager, ref, *_ = setup
    manager.bind_workflow(ref['session_id'], ref['credential'], 'p', em_spec())
    job = submit(setup, 'solve', {}, 'em')
    with pytest.raises(ServiceError) as exc:
        execute(runtime_for(setup, native_app()), job)
    assert exc.value.code == 'workflow_worker_upgrade_required'


def test_em_only_refuses_special_circuit_solve_before_special_routes(setup):
    from tpc_service.sessions.store import read
    manager, ref, folder, *_ = setup
    manager.bind_workflow(ref['session_id'], ref['credential'], 'p', em_spec())
    with pytest.raises(ServiceError) as exc:
        workflow.preflight(folder, read(folder / 'session.json'), 'run_native_static_sp', {'project_id': 'p'})
    assert exc.value.code == 'workflow_route_unsupported'


def test_em_only_solve_runs_native_checks_with_capable_worker(setup):
    from tpc_service.sessions.operations import execute
    from tpc_service.sessions.store import read, write
    from test_workflow_enforcement import runtime_for, native_app
    manager, ref, folder, *_ = setup
    manager.bind_workflow(ref['session_id'], ref['credential'], 'p', em_spec())
    job = submit(setup, 'solve', {}, 'em')
    state = read(folder / 'session.json')
    state['worker_capabilities'] = ['parameter-em-only-v2']
    write(folder / 'session.json', state)
    result = execute(runtime_for(setup, native_app()), job)
    assert result['solver_outcome']['status'] == 'succeeded'


def test_em_only_native_mismatch_refuses_solve(setup):
    from tpc_service.sessions.operations import execute
    from tpc_service.sessions.store import read, write
    from test_workflow_enforcement import runtime_for, native_app
    manager, ref, folder, *_ = setup
    manager.bind_workflow(ref['session_id'], ref['credential'], 'p', em_spec())
    job = submit(setup, 'solve', {}, 'em')
    state = read(folder / 'session.json')
    state['worker_capabilities'] = ['parameter-em-only-v2']
    write(folder / 'session.json', state)
    with pytest.raises(ServiceError) as exc:
        execute(runtime_for(setup, native_app(width=3)), job)
    assert exc.value.code == 'workflow_native_mismatch'
