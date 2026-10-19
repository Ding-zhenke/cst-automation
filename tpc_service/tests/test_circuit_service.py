from types import SimpleNamespace
import threading

import pytest

from tpc_service import RunService
from tpc_service.backends.fake import FakeBackend
from tpc_service.backends.base import fail_result, ok_result
from tpc_service.circuit import register_circuit_handlers
from tpc_service.errors import ServiceError


def test_failed_result_preserves_artifacts_and_identity():
    out = fail_result("circuit_result_unverified", "unverified", artifacts=[{"path": "audit.json"}],
                      run_identity={"run_token": "T"}, result_summary={"evidence": "unverified"}, saved=True)
    assert out["artifacts"] == [{"path": "audit.json"}]
    assert out["run_identity"] == {"run_token": "T"}
    assert out["saved"] is True


def test_explicit_registration_preserves_existing_handler_and_serializes(tmp_path):
    service = RunService(str(tmp_path), backend=FakeBackend())
    service.register_handler("build", lambda **kw: ok_result(result_summary={"old": True}))
    called = []
    def factory(path):
        called.append(threading.current_thread().name)
        return SimpleNamespace(circuit=SimpleNamespace(inspect=lambda: {"blocks": []}), close=lambda: None)
    try:
        with pytest.raises(ServiceError): register_circuit_handlers(service, app_factory=factory)
        register_circuit_handlers(service, replace=True, app_factory=factory)
        path = tmp_path / "p.cst"
        path.write_text("fixture")
        old = service.submit("build", project_path=str(path), copy=False)
        assert service.wait(old["job_id"], timeout=3)["result_summary"]["old"] is True
        queued = service.submit("build", project_path=str(path), copy=False,
                                params={"workflow": "circuit", "operation": "inspect"}, request_id="once")
        out = service.wait(queued["job_id"], timeout=3)
        assert out["status"] == "succeeded"
        assert called == ["cst-automation-worker"]
        duplicate = service.submit("build", project_path=str(path), copy=False,
                                   params={"workflow": "circuit", "operation": "inspect"}, request_id="once")
        assert duplicate["duplicate"] and len(called) == 1
    finally:
        service.shutdown()


def test_unknown_operation_rejected_without_loading_sdk(tmp_path):
    service = RunService(str(tmp_path), backend=FakeBackend())
    register_circuit_handlers(service, app_factory=lambda p: pytest.fail("SDK must not load"))
    try:
        path = tmp_path / "p.cst"
        path.write_text("fixture")
        job = service.submit("build", project_path=str(path), copy=False, params={"workflow": "circuit", "operation": "run_all"})
        out = service.wait(job["job_id"], timeout=3)
        assert out["status"] == "failed" and out["error"]["code"] == "circuit_spec_invalid"
    finally:
        service.shutdown()


def test_invalid_spec_rejected_before_opening_cst(tmp_path):
    service = RunService(str(tmp_path), backend=FakeBackend())
    register_circuit_handlers(service, app_factory=lambda p: pytest.fail("Invalid spec must not open CST"))
    try:
        path = tmp_path / "p.cst"
        path.write_text("fixture")
        job = service.submit("build", project_path=str(path), copy=False, params={"workflow": "circuit", "operation": "configure", "spec": {"schema_version": 99}})
        out = service.wait(job["job_id"], timeout=3)
        assert out["status"] == "failed" and out["error"]["code"] == "circuit_spec_invalid"
    finally:
        service.shutdown()


def test_unverified_maps_to_failed_with_evidence(tmp_path):
    api = SimpleNamespace(run_checked=lambda *a, **k: {"status": "unverified", "run_token": "T", "saved": True, "audit_path": str(tmp_path / "audit.json"), "errors": []})
    service = RunService(str(tmp_path), backend=FakeBackend())
    register_circuit_handlers(service, app_factory=lambda p: SimpleNamespace(circuit=api, close=lambda: None))
    try:
        (tmp_path / "audit.json").write_text("{}")
        path = tmp_path / "p.cst"
        path.write_text("fixture")
        job = service.submit("solve", project_path=str(path), copy=False,
                             params={"workflow": "circuit", "operation": "run_task", "task_name": "T", "mode": "transient_cosim", "expected_results": [{"tree_path": "T\\V", "run_id": 1}]})
        out = service.wait(job["job_id"], timeout=3)
        assert out["status"] == "failed" and out["error"]["code"] == "circuit_result_unverified"
        assert out["run_identity"]["run_token"] == "T" and out["artifacts"]
    finally:
        service.shutdown()


def test_partial_build_saves_audit_and_project_before_close(tmp_path):
    from cst_solver.circuit.adapter import CircuitError
    events = []
    def fail(spec):
        events.append("first_component_created")
        raise CircuitError("circuit_build_partial", "second component failed", stage="apply")
    app = SimpleNamespace(circuit=SimpleNamespace(apply=fail, inspect=lambda: {"blocks": [{"name": "first"}]}),
                          save=lambda: events.append("saved"), get_messages=lambda: ["second component failed"], close=lambda: events.append("closed"))
    service = RunService(str(tmp_path), backend=FakeBackend())
    register_circuit_handlers(service, app_factory=lambda p: app)
    try:
        path = tmp_path / "p.cst"
        path.write_text("fixture")
        job = service.submit("build", project_path=str(path), copy=False,
                             params={"workflow": "circuit", "operation": "configure", "spec": {"schema_version": 1}})
        out = service.wait(job["job_id"], timeout=3)
        assert out["status"] == "failed" and events == ["first_component_created", "saved", "closed"]
        assert out["artifacts"] and out["result_summary"]["partial_build"]["readback"]["blocks"][0]["name"] == "first"
    finally:
        service.shutdown()


@pytest.mark.parametrize('partial', [False, True])
def test_transient_configuration_is_worker_only_and_saves_partial_evidence(tmp_path, partial):
    from cst_solver.circuit.adapter import CircuitError
    events = []
    def configure(name, settings, *, create):
        events.append(('configured', threading.current_thread().name, name, create))
        if partial: raise CircuitError('circuit_build_partial', 'sampling readback failed', stage='configure_transient_task')
        return {'solver_verified': False, 'task_name': name}
    app = SimpleNamespace(circuit=SimpleNamespace(configure_transient_task=configure, inspect=lambda: {'tasks': []}),
                          save=lambda: events.append('saved'), close=lambda: events.append('closed'), get_messages=lambda: [])
    service = RunService(str(tmp_path), backend=FakeBackend())
    register_circuit_handlers(service, app_factory=lambda path: app)
    try:
        path = tmp_path/'p.cst'; path.write_text('fixture')
        job = service.submit('build', project_path=str(path), copy=False,
            params={'workflow':'circuit','operation':'configure_transient_task','task_name':'TR','create':True,
                    'settings':{'mode':'transient_cosim','duration':{'value':40,'unit':'ns'}}})
        out = service.wait(job['job_id'], timeout=3)
        assert out['status'] == ('failed' if partial else 'succeeded')
        assert events == [('configured','cst-automation-worker','TR',True),'saved','closed']
        if partial: assert out['result_summary']['partial_build']['stage']=='configure_transient_task'
    finally: service.shutdown()


def test_invalid_transient_settings_do_not_open_project(tmp_path):
    service = RunService(str(tmp_path), backend=FakeBackend())
    register_circuit_handlers(service, app_factory=lambda path: pytest.fail('Must validate before SDK'))
    try:
        path=tmp_path/'p.cst';path.write_text('fixture')
        job=service.submit('build',project_path=str(path),copy=False,params={'workflow':'circuit','operation':'configure_transient_task','task_name':'TR','settings':{'mode':'transient_cosim','duration':{'value':40,'unit':'V'}}})
        out=service.wait(job['job_id'],timeout=3)
        assert out['status']=='failed' and out['error']['code']=='circuit_spec_invalid'
    finally:service.shutdown()


@pytest.mark.parametrize('partial', [False, True])
def test_em_time_settings_are_worker_only_save_and_keep_partial_audit(tmp_path, partial):
    from cst_solver.simulation.em_time import EMTimeConfigurationError
    events = []
    settings = {'stability_factor': .5, 'output_sampling': 'every_step'}
    def configure(data):
        events.append(('configured', threading.current_thread().name, data))
        if partial:
            raise EMTimeConfigurationError('em_time_configuration_partial', 'history interrupted',
                stage='configure_em_time_settings', requested=data, history_submitted=None,
                native_commands=['Solver.TimeStepStabilityFactor 0.5'])
        return {'solver_verified': False, 'internal_time_step_verified': False}
    # No schematic or circuit property: generic EM settings must not depend on DS.
    app = SimpleNamespace(configure_em_time_settings=configure, save=lambda: events.append('saved'),
                          close=lambda: events.append('closed'), get_messages=lambda: ['native diagnostic'])
    service = RunService(str(tmp_path), backend=FakeBackend())
    register_circuit_handlers(service, app_factory=lambda path: app)
    try:
        path = tmp_path / 'p.cst'; path.write_text('fixture')
        job = service.submit('build', project_path=str(path), copy=False,
            params={'workflow': 'circuit', 'operation': 'configure_em_time_settings', 'settings': settings})
        out = service.wait(job['job_id'], timeout=3)
        assert out['status'] == ('failed' if partial else 'succeeded')
        assert events == [('configured', 'cst-automation-worker', settings), 'saved', 'closed']
        if partial:
            evidence = out['result_summary']['partial_build']
            assert evidence['stage'] == 'configure_em_time_settings'
            assert evidence['requested'] == settings
            assert evidence['native_commands']
            assert evidence['readback_status'] == 'unsupported'
            assert evidence['messages'] == ['native diagnostic']
            assert out['error']['code'] == 'circuit_build_partial' and out['artifacts']
        else:
            assert out['result_summary']['internal_time_step_verified'] is False
    finally:
        service.shutdown()


def test_invalid_em_time_settings_rejected_before_opening_project(tmp_path):
    service = RunService(str(tmp_path), backend=FakeBackend())
    register_circuit_handlers(service, app_factory=lambda path: pytest.fail('Invalid settings must not open CST'))
    try:
        path = tmp_path / 'p.cst'; path.write_text('fixture')
        job = service.submit('build', project_path=str(path), copy=False,
            params={'workflow': 'circuit', 'operation': 'configure_em_time_settings', 'settings': {'stability_factor': 2}})
        out = service.wait(job['job_id'], timeout=3)
        assert out['status'] == 'failed' and out['error']['code'] == 'circuit_spec_invalid'
    finally:
        service.shutdown()


def test_unavailable_em_domain_is_explicit_and_never_saved(tmp_path):
    from cst_solver.simulation.em_time import EMTimeConfigurationError
    events = []
    def configure(data):
        raise EMTimeConfigurationError('em_time_unavailable', 'No model3d',
                                       stage='configure_em_time_settings', history_submitted=False)
    app = SimpleNamespace(configure_em_time_settings=configure,
                          save=lambda: pytest.fail('No mutation, no save'), close=lambda: events.append('closed'))
    service = RunService(str(tmp_path), backend=FakeBackend())
    register_circuit_handlers(service, app_factory=lambda path: app)
    try:
        path = tmp_path / 'p.cst'; path.write_text('fixture')
        job = service.submit('build', project_path=str(path), copy=False,
            params={'workflow': 'circuit', 'operation': 'configure_em_time_settings', 'settings': {'output_sampling': 'every_step'}})
        out = service.wait(job['job_id'], timeout=3)
        assert out['status'] == 'failed' and out['error']['code'] == 'circuit_unavailable'
        assert events == ['closed']
    finally:
        service.shutdown()
