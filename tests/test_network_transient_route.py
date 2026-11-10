from types import SimpleNamespace
import pytest

from tpc_service.errors import ServiceError
from cst_solver.circuit.adapter import CircuitError


def test_unbound_transient_is_queued_without_weakening_other_guards(tmp_path):
    from tpc_service.sessions.workflow import preflight
    project = {'project_id': 'p', 'path': str(tmp_path / 'p.cst')}
    state = {'backend': 'cst', 'projects': {'p': project}}
    params = {'project_id': 'p', 'kind': 'solve', 'settings': {
        'operation': 'run_network_transient', 'task_name': 'TR',
        'expected_results': [{'tree_path': r'Tasks\TR\V', 'run_id': 0}]}}
    assert preflight(tmp_path, state, 'circuit', params) is None
    params['settings']['operation'] = 'run_task'
    with pytest.raises(ServiceError, match='specification'):
        preflight(tmp_path, state, 'circuit', params)


@pytest.mark.parametrize('kind,simulator,children', [
    ('spectral lines', 'cst', []), ('transient', 'cosimulation', []),
    ('transient', '', []), ('transient', 'cst', ['TR\\HB'])])
def test_only_native_leaf_network_transient_is_allowed(kind, simulator, children):
    from tpc_service.circuit import validate_network_transient
    adapter = SimpleNamespace(task=lambda name: {'name': name, 'type': kind,
        'properties': {'circuit simulator': simulator}},
        inspect=lambda: {'tasks': [{'name': 'TR'}] + [{'name': x} for x in children]})
    with pytest.raises(CircuitError):
        validate_network_transient(adapter, 'TR')


def test_native_leaf_network_transient_is_accepted():
    from tpc_service.circuit import validate_network_transient
    adapter = SimpleNamespace(task=lambda name: {'name': name, 'type': 'transient',
        'properties': {'circuit simulator': 'cst'}},
        inspect=lambda: {'tasks': [{'name': 'TR'}, {'name': 'other'}]})
    assert validate_network_transient(adapter, 'TR')['type'] == 'transient'


def test_bound_workflow_cannot_use_standalone_route(tmp_path):
    from tpc_service.sessions.workflow import preflight
    project = {'project_id': 'p', 'path': str(tmp_path / 'p.cst'), 'workflow': {'revision': 'x'}}
    state = {'backend': 'cst', 'projects': {'p': project}}
    params = {'project_id': 'p', 'kind': 'solve', 'settings': {'operation': 'run_network_transient',
              'task_name': 'TR', 'expected_results': [{'tree_path': 'TR\\V', 'run_id': 0}]}}
    with pytest.raises(ServiceError) as exc:
        preflight(tmp_path, state, 'circuit', params)
    assert exc.value.code == 'workflow_route_unsupported'


@pytest.mark.parametrize('extra', [{'deadline_seconds': 120}, {'reuse': 'verified'}, {'require_mor': True}])
def test_unsupported_safety_options_rejected_before_launch(tmp_path, extra):
    from tpc_service.sessions.workflow import preflight
    state = {'backend': 'cst', 'projects': {'p': {'path': str(tmp_path/'p.cst')}}}
    settings = {'operation': 'run_network_transient', 'task_name': 'TR',
                'expected_results': [{'tree_path': 'TR\\V', 'run_id': 0}], **extra}
    with pytest.raises(ServiceError) as exc:
        preflight(tmp_path, state, 'circuit', {'project_id': 'p', 'kind': 'solve', 'settings': settings})
    assert exc.value.code == 'workflow_transient_request_invalid'
