from types import SimpleNamespace
import copy

import pytest

from cst_solver.circuit.api import CircuitAPI
from cst_solver.circuit.adapter import CircuitError, NativeAdapter
from cst_solver.circuit.capabilities import circuit_capabilities


class Adapter:
    """In-memory external boundary, not an EM/circuit solver."""
    def __init__(self):
        self.snapshot = {"blocks": [], "external_ports": [], "nets": [], "probes": [], "tasks": [], "units": {}, "parameters": {}, "unknown": []}
        self.updated = []
        self.proof = {}
        self.fail_write = False

    def inspect(self): return copy.deepcopy(self.snapshot)
    def apply(self, spec):
        if self.fail_write: raise RuntimeError("native write interrupted")
        for key in self.snapshot:
            if key in spec: self.snapshot[key] = copy.deepcopy(spec[key])
        for block in self.snapshot["blocks"]:
            block["pins"] = [{"pin_name": "1", "port_index": 7}, {"pin_name": "2", "port_index": 9}]
    def task(self, name):
        return next(t for t in self.snapshot["tasks"] if t["name"] == name)
    def update_task(self, name): self.updated.append(name)
    def execution_evidence(self, task, token): return dict(self.proof)
    def properties(self, name, props, units):
        b = next(b for b in self.snapshot["blocks"] if b["name"] == name)
        b["properties"].update(props)
    def dependencies(self): return {"files": [], "unknown": [], "complete": True}
    def link_em(self, **kwargs): return dict(kwargs, verified=False, reason="EM port readback pending")


def raw_spec():
    return {"schema_version": 1, "units": {}, "parameters": {}, "blocks": [], "external_ports": [],
            "nets": [], "probes": [], "em_links": [],
            "tasks": [{"name": "T", "type": "transient", "properties": {"circuit simulator": "cosimulation"}}]}


@pytest.fixture
def env(tmp_path):
    path = tmp_path / "sample.cst"
    path.write_text("offline project", encoding="utf-8")
    saves = []
    app = SimpleNamespace(cst_file=SimpleNamespace(filename=lambda: str(path)),
                          save=lambda *args, **kwargs: saves.append(str(path)) or str(path),
                          get_messages=lambda: [])
    adapter = Adapter()
    api = CircuitAPI(app, adapter=adapter)
    return api, adapter, saves


def test_static_discovery_does_not_claim_license_or_live_validation():
    caps = circuit_capabilities()
    assert caps["license"] == "unknown"
    assert caps["verification"]["transient_cosim"] == "not_run"
    with pytest.raises(CircuitError): circuit_capabilities(probe="live")


def test_conflict_does_not_delete_existing_object(env):
    api, adapter, _ = env
    api.apply(raw_spec())
    with pytest.raises(CircuitError, match="conflict"):
        api.apply(raw_spec())
    assert [t["name"] for t in adapter.snapshot["tasks"]] == ["T"]


def test_partial_write_is_explicit_and_preserves_phase(env):
    api, adapter, _ = env
    adapter.fail_write = True
    with pytest.raises(CircuitError) as error: api.apply(raw_spec())
    assert error.value.code == "circuit_build_partial"
    assert error.value.details["stage"] == "apply"


def test_run_rejects_wrong_mode_before_submission(env):
    api, adapter, _ = env
    api.apply(raw_spec())
    result = api.run_checked("T", mode="network", expected_results=[{"tree_path": "T\\Voltages\\V1", "run_id": 4}])
    assert result["status"] == "failed"
    assert adapter.updated == []


def test_update_selected_task_and_missing_evidence_is_unverified(env):
    api, adapter, saves = env
    api.apply(raw_spec())
    result = api.run_checked("T", mode="transient_cosim", expected_results=[{"tree_path": "T\\Voltages\\V1", "run_id": 4}])
    assert adapter.updated == ["T"]
    assert saves
    assert result["status"] == "unverified"
    assert result["run_token"]
    assert result["errors"][0]["code"] == "circuit_result_unverified"
    assert result["audit_path"]


def test_rejects_results_belonging_to_another_task_before_run(env):
    api, adapter, _ = env
    api.apply(raw_spec())
    result = api.run_checked("T", mode="transient_cosim", expected_results=[{"tree_path": "Other\\Voltage", "run_id": 0}])
    assert result["status"] == "failed" and adapter.updated == []


def test_verified_cache_not_assumed_from_unchanged_results(env):
    api, adapter, _ = env
    api.apply(raw_spec())
    result = api.run_checked("T", mode="transient_cosim", reuse="verified", expected_results=[{"tree_path": "T\\V", "run_id": 1}])
    assert result["status"] == "unverified"
    assert adapter.updated == []


def test_native_index_lookup_uses_port_name_without_subtraction():
    block = SimpleNamespace(Reset=lambda: None, Name=lambda name: None, GetPortIndex=lambda name: {"sig": 7, "ref": 11}[name])
    native = NativeAdapter(SimpleNamespace(cst_file=SimpleNamespace(schematic=SimpleNamespace(Block=block))))
    assert native.endpoint(["Block", "B", "ref"]) == ["Block", "B", 11]


def test_schematic_none_is_explicit():
    with pytest.raises(CircuitError) as error:
        NativeAdapter(SimpleNamespace(cst_file=SimpleNamespace(schematic=None)))
    assert error.value.code == "circuit_unavailable"


def test_setup_circuit_property_is_lazy():
    from cst_solver import setup
    app = setup.__new__(setup)
    app.cst_file = None
    assert isinstance(app.circuit, CircuitAPI)
    with pytest.raises(CircuitError): app.circuit.inspect()


def test_target_completion_without_matching_result_run_is_unverified(env, monkeypatch):
    api, adapter, _ = env
    api.apply(raw_spec())
    adapter.execution_evidence = lambda name, token: {"completed": True, "em_completed": True, "task_name": name, "run_token": token, "mode": "transient_cosim",
                                                     "circuit_runs": [{"tree_path": "T\\V", "run_id": 8}]}
    import cst_solver.circuit.results as results
    monkeypatch.setattr(results, "CircuitResult", lambda path: SimpleNamespace(read_curve=lambda *a, **k: {"parameters": {}, "run_id": 7}))
    out = api.run_checked("T", mode="transient_cosim", expected_results=[{"tree_path": "T\\V", "run_id": 7}])
    assert out["status"] == "unverified"


def test_native_properties_use_si_local_units_without_changing_existing_global_units():
    stored, units = {}, {}
    obj = SimpleNamespace(Reset=lambda: None, Name=lambda n: None, SetLocalUnitForProperty=lambda k,u: units.update({k:u}),
                          SetDoubleProperty=lambda k,v: stored.update({k:v}), GetProperty=lambda k: stored[k])
    native = NativeAdapter(SimpleNamespace(cst_file=SimpleNamespace(schematic=SimpleNamespace(Block=obj, Units=SimpleNamespace(SetUnit=lambda *a: pytest.fail("Existing global units must not change"))))))
    native.properties("C1", {"Capacitance": "2*Cval"}, {"Capacitance": "pF"}, {"Cval": {"value": 1, "unit": "pF"}})
    assert float(stored["Capacitance"]) == pytest.approx(2e-12)
    assert units["Capacitance"] == "F"


def test_incomplete_dependency_closure_prevents_submission(env):
    api, adapter, _ = env
    api.apply(raw_spec())
    adapter.dependencies = lambda: {"files": [], "unknown": [{"reason": "cycle"}], "complete": False}
    result = api.run_checked("T", mode="transient_cosim", expected_results=[{"tree_path": "T\\V", "run_id": 4}])
    assert result["status"] != "succeeded" and adapter.updated == []


def test_existing_and_unreadable_parameters_are_not_overwritten(env):
    api, adapter, _ = env
    raw = raw_spec()
    raw["parameters"] = {"Cval": {"value": 1, "unit": "pF"}}
    adapter.snapshot["parameters"] = {"Cval": "original"}
    with pytest.raises(CircuitError): api.apply(raw)
    assert adapter.snapshot["parameters"]["Cval"] == "original"
    adapter.snapshot["parameters"] = None
    with pytest.raises(CircuitError): api.apply(raw)


def test_run_without_saved_project_returns_structured_failure():
    api = CircuitAPI(SimpleNamespace(cst_file=None))
    out = api.run_checked("T", mode="network", expected_results=[{"tree_path": "T\\V", "run_id": 1}])
    assert out["status"] == "failed" and out["errors"][0]["code"] == "circuit_unavailable"
