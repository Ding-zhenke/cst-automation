"""Guard configuration at native and managed boundaries without loading CST."""
from types import SimpleNamespace

import pytest

from cst_solver.circuit.api import CircuitAPI
from cst_solver.circuit.adapter import CircuitError
from tpc_service.circuit import register_circuit_handlers
from tpc_service.sessions.validation import validate


def request():
    return {'operation': 'disable_tasks', 'tasks': [
        {'task_name': 'Scan', 'expected_type': 'parameter sweep', 'expected_enabled': True},
        {'task_name': 'Scan\\HB', 'expected_type': 'spectral lines', 'expected_enabled': True}],
        'confirm_idle': True, 'review_note': 'Owner reviewed completed calls and DS idle'}


class Tasks:
    def __init__(self):
        self.rows = {'Scan': ['parameter sweep', 'True'], 'Scan\\HB': ['spectral lines', 'True'],
                     'Other': ['spectral lines', 'True']}
        self.writes = []
        self.ignore_write = False

    def Reset(self):
        self.name = None

    def Name(self, name):
        self.name = name

    def DoesExist(self):
        return self.name in self.rows

    def GetTypeForTask(self, name):
        return self.rows[name][0]

    def GetProperty(self, key):
        assert key == 'enabled'
        return self.rows[self.name][1]

    def SetProperty(self, key, value):
        assert key == 'enabled' and value == 'False'
        self.writes.append(self.name)
        if not self.ignore_write:
            self.rows[self.name][1] = value


def api_and_tasks():
    tasks = Tasks()
    return CircuitAPI(None, adapter=SimpleNamespace(schematic=SimpleNamespace(SimulationTask=tasks))), tasks


def invoke(api, options=None):
    data = dict(options or request())
    data.pop('operation')
    return api.disable_tasks(**data)


def test_disable_exact_targets_reports_native_before_after_without_execution():
    api, tasks = api_and_tasks()
    out = invoke(api)
    assert tasks.writes == ['Scan', 'Scan\\HB']
    assert tasks.rows['Other'] == ['spectral lines', 'True']
    assert [r['enabled'] for r in out['before']] == [True, True]
    assert [r['enabled'] for r in out['after']] == [False, False]
    assert out['readback_verified'] and not out['solver_verified']


@pytest.mark.parametrize('change', ['missing', 'type', 'enabled', 'unknown'])
def test_preflight_checks_all_targets_before_any_write(change):
    api, tasks = api_and_tasks()
    if change == 'missing':
        del tasks.rows['Scan\\HB']
    elif change == 'type':
        tasks.rows['Scan\\HB'][0] = 'transient'
    else:
        tasks.rows['Scan\\HB'][1] = 'False' if change == 'enabled' else 'unknown'
    with pytest.raises(CircuitError):
        invoke(api)
    assert tasks.writes == []


def test_native_write_not_effective_is_partial_failure_with_evidence():
    api, tasks = api_and_tasks()
    tasks.ignore_write = True
    with pytest.raises(CircuitError) as exc:
        invoke(api)
    assert exc.value.code == 'circuit_build_partial'
    assert exc.value.details['before'][0]['enabled'] is True


def test_already_disabled_target_is_read_back_without_reenabling():
    api, tasks = api_and_tasks()
    tasks.rows['Scan'][1] = 'False'
    options = request(); options['tasks'][0]['expected_enabled'] = False
    out = invoke(api, options)
    assert tasks.writes == ['Scan\\HB']
    assert out['after'][0]['enabled'] is False


@pytest.mark.parametrize('update', [
    {'confirm_idle': False}, {'confirm_idle': 1}, {'tasks': []}, {'review_note': ''},
    {'tasks': [{'task_name': 'Scan\\', 'expected_type': 'spectral lines', 'expected_enabled': True}]},
    {'tasks': [{'task_name': 'Scan', 'expected_type': 'parameter sweep', 'expected_enabled': 'True'}]},
    {'enabled': True}, {'run': True},
])
def test_invalid_request_rejected_at_session_validation(update):
    options = request(); options.update(update)
    with pytest.raises(Exception):
        validate('circuit', {'project_id': 'p', 'kind': 'build', 'settings': options})


def handler(tmp_path, api, *, borrowed=True, save_failure=False):
    handlers = {}; calls = []
    def save():
        calls.append('save')
        if save_failure:
            raise OSError('Synthetic save failure')
    app = SimpleNamespace(circuit=api, save=save, close=lambda: calls.append('release'))
    service = SimpleNamespace(workdir=str(tmp_path), register_workflow=lambda name, values, **kw: handlers.update(values))
    path = tmp_path / 'model.cst'; path.write_bytes(b'baseline')
    def factory(path):
        calls.append('factory'); return app
    register_circuit_handlers(service, app_factory=factory,
        authorized_project_path=str(path) if borrowed else None, borrowed_project=borrowed)
    def call(options):
        return handlers['build'](project={'path': str(path)}, params=options, job={'kind': 'build'}, backend=None)
    return call, calls


def test_managed_handler_disables_and_saves_but_does_not_execute(tmp_path):
    api, tasks = api_and_tasks()
    call, calls = handler(tmp_path, api)
    out = call(request())
    assert out['ok'] and out['saved']
    assert calls == ['factory', 'save', 'release']
    assert tasks.writes == ['Scan', 'Scan\\HB']


def test_standalone_route_rejects_before_creating_app(tmp_path):
    api, tasks = api_and_tasks()
    call, calls = handler(tmp_path, api, borrowed=False)
    assert not call(request())['ok']
    assert calls == [] and tasks.writes == []


def test_bad_managed_request_never_creates_app(tmp_path):
    api, tasks = api_and_tasks()
    call, calls = handler(tmp_path, api)
    options = request(); options['confirm_idle'] = False
    assert not call(options)['ok']
    assert calls == [] and tasks.writes == []


def test_partial_native_failure_preserves_failed_receipt_and_audit(tmp_path):
    api, tasks = api_and_tasks()
    tasks.ignore_write = True
    call, calls = handler(tmp_path, api)
    out = call(request())
    assert not out['ok'] and out['saved']
    assert out['result_summary']['partial_build']['before'][0]['enabled'] is True
    assert len(list(tmp_path.rglob('circuit_failures/*.json'))) == 1
    assert calls == ['factory', 'save', 'release']


def test_save_failure_retains_native_changes_and_does_not_retry(tmp_path):
    api, tasks = api_and_tasks()
    call, calls = handler(tmp_path, api, save_failure=True)
    out = call(request())
    assert not out['ok'] and not out['saved']
    report = out['result_summary']['partial_build']
    assert report['stage'] == 'save' and report['after'][0]['enabled'] is False
    assert report['attempted'] == ['Scan', 'Scan\\HB']
    assert report['save_error'] == 'Synthetic save failure'
    assert len(list(tmp_path.rglob('circuit_failures/*.json'))) == 1
    assert calls == ['factory', 'save', 'release']


def test_execution_rejects_old_worker_before_native_access(tmp_path):
    from tpc_service.sessions.operations import execute
    from tpc_service.errors import ServiceError
    class Runtime:
        folder = tmp_path
        def state(self):
            return {'projects': {}, 'worker_capabilities': []}
        def project(self, name):
            pytest.fail('Native project access before capability rejection')
    with pytest.raises(ServiceError) as exc:
        execute(Runtime(), {'operation': 'circuit', 'params': {'project_id': 'p', 'kind': 'build', 'settings': request()}})
    assert exc.value.code == 'workflow_worker_upgrade_required'
