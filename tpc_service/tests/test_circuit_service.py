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
