"""Staged schematic additions resolve existing objects from fresh readback."""
import copy
from types import SimpleNamespace

import pytest

from cst_automation.circuit_schema import CircuitSpecError, validate_circuit_spec
from cst_solver.circuit.api import CircuitAPI
from cst_solver.circuit.adapter import CircuitError, NativeAdapter


def endpoint(kind, name, pin):
    return dict(component_kind=kind, component_name=name, pin_name=pin)


def wire_spec():
    return dict(schema_version=1, nets=[dict(name="input", endpoints=[
        endpoint("ExternalPort", "P1", "1"), endpoint("Block", "R1", "left")])])


class RecordingAdapter:
    def __init__(self):
        self.snapshot = dict(
            blocks=[dict(name="R1", type="Resistor", pins=[
                dict(pin_name="left", port_index=7), dict(pin_name="right", port_index=9)])],
            external_ports=[dict(name=n, pins=[dict(pin_name="1", port_index=0)])
                            for n in ("P1", "P2")],
            nets=[], probes=[], tasks=[], parameters={}, units={}, unknown=[])
        self.writes = []

    def inspect(self):
        return copy.deepcopy(self.snapshot)

    def apply(self, data):
        self.writes.append(copy.deepcopy(data))


@pytest.fixture
def staged():
    adapter = RecordingAdapter()
    return CircuitAPI(SimpleNamespace(), adapter=adapter), adapter


def test_nets_only_apply_uses_existing_native_objects_without_recreating_them(staged):
    api, adapter = staged
    original = copy.deepcopy(adapter.snapshot)
    result = api.apply(wire_spec())
    assert result["applied"] and not result["solver_verified"]
    assert adapter.writes[0]["nets"] == wire_spec()["nets"]
    assert adapter.writes[0]["blocks"] == adapter.writes[0]["external_ports"] == []
    assert adapter.snapshot == original


def test_offline_complete_spec_validation_still_rejects_unknown_endpoints():
    with pytest.raises(CircuitSpecError, match="Unknown endpoint"):
        validate_circuit_spec(wire_spec())


@pytest.mark.parametrize("change", ["component", "kind", "pin", "unreadable_pins", "no_port_index"])
def test_unresolved_existing_endpoint_is_rejected_before_any_write(staged, change):
    api, adapter = staged
    spec = wire_spec()
    ep = spec["nets"][0]["endpoints"][1]
    if change == "component": ep["component_name"] = "missing"
    if change == "kind": ep["component_kind"] = "Task"
    if change == "pin": ep["pin_name"] = "typo"
    if change == "unreadable_pins": adapter.snapshot["blocks"][0]["pins"] = None
    if change == "no_port_index": adapter.snapshot["blocks"][0]["pins"][0]["port_index"] = None
    with pytest.raises((CircuitSpecError, CircuitError)):
        api.apply(spec)
    assert not adapter.writes


@pytest.mark.parametrize("native_kind", ["ExternalPort", "Externalport"])
def test_existing_native_connection_cannot_be_reassigned_by_new_net(staged, native_kind):
    api, adapter = staged
    adapter.snapshot["nets"] = [dict(name="old", subnets=[[
        ["Block", "R1", 7], [native_kind, "P2", 0]]])]
    with pytest.raises((CircuitSpecError, CircuitError), match="multiple nets|connected|occupied"):
        api.apply(wire_spec())
    assert not adapter.writes


def test_unreadable_native_nets_do_not_mean_existing_pins_are_free(staged):
    api, adapter = staged
    adapter.snapshot["unknown"] = [dict(field="nets", error="native query failed")]
    with pytest.raises((CircuitSpecError, CircuitError), match="nets|readback"):
        api.apply(wire_spec())
    assert not adapter.writes


def test_later_stage_can_add_probe_and_task_to_existing_connected_port(staged):
    api, adapter = staged
    adapter.snapshot["nets"] = [dict(name="old", subnets=[[
        ["Block", "R1", 7], ["ExternalPort", "P1", 0]]])]
    spec = dict(schema_version=1,
        probes=[dict(name="sense", endpoint=endpoint("Block", "R1", "left"), direction_inwards=True)],
        tasks=[dict(name="SP", type="s-parameters", excitations={
            "P1": dict(type="Sine", values=[1, 1])})])
    assert api.apply(spec)["applied"]
    assert adapter.writes[0]["nets"] == []
    assert adapter.writes[0]["tasks"][0]["name"] == "SP"


def test_schema_errors_are_rejected_before_native_inspection():
    api = CircuitAPI(SimpleNamespace(), adapter=SimpleNamespace(
        inspect=lambda: pytest.fail("Invalid schema must not access CST")))
    with pytest.raises(CircuitSpecError):
        api.apply(dict(schema_version=99))


def test_existing_object_name_conflict_is_still_rejected(staged):
    api, adapter = staged
    with pytest.raises((CircuitSpecError, CircuitError), match="conflict|Duplicate"):
        api.apply(dict(schema_version=1, blocks=[dict(name="R1", type="Ground")]))
    assert not adapter.writes


def test_changed_live_pins_are_not_replaced_by_old_cached_spec(staged):
    api, adapter = staged
    api._spec = dict(blocks=[dict(name="R1", pins=[dict(pin_name="left", port_index=7)])])
    adapter.snapshot["blocks"][0]["pins"][0]["pin_name"] = "changed"
    with pytest.raises((CircuitSpecError, CircuitError)):
        api.apply(wire_spec())
    assert not adapter.writes


@pytest.mark.parametrize("displays", [("2(OUT)", "1(IN)"), ("2", "1")])
def test_native_pins_use_canonical_port_names_and_preserve_display_indices(displays):
    block = SimpleNamespace(Reset=lambda: None, Name=lambda n: None,
        GetNumberOfPorts=lambda: 2, GetPortName=lambda i: ("1", "2")[i],
        GetNumberOfPins=lambda: 2, GetPinName=lambda i: displays[i],
        GetPortLabel=lambda i: ("IN", "OUT")[i])
    adapter = NativeAdapter(SimpleNamespace(cst_file=SimpleNamespace(
        schematic=SimpleNamespace(Block=block))))
    pins = adapter.pins("module")
    assert [(p["pin_name"], p["pin_index"], p["port_index"]) for p in pins] == [
        ("2", 0, 1), ("1", 1, 0)]
    assert [p["display_pin_name"] for p in pins] == list(displays)


def test_service_accepts_staged_nets_through_the_same_api(tmp_path, staged):
    from tpc_service import RunService
    from tpc_service.backends.fake import FakeBackend
    from tpc_service.circuit import register_circuit_handlers
    api, adapter = staged
    path = tmp_path / "staged.cst"
    path.write_text("offline fixture", encoding="utf-8")
    app = SimpleNamespace(circuit=api, save=lambda: str(path), close=lambda: None,
                          get_messages=lambda: [])
    service = RunService(str(tmp_path), backend=FakeBackend())
    register_circuit_handlers(service, app_factory=lambda p: app)
    try:
        job = service.submit("build", project_path=str(path), copy=False,
            params=dict(workflow="circuit", operation="configure", spec=wire_spec()))
        result = service.wait(job["job_id"], timeout=3)
        assert result["status"] == "succeeded", result
        assert len(adapter.writes) == 1
    finally:
        service.shutdown()


def test_existing_self_em_link_is_not_treated_as_a_duplicate_new_block(staged):
    api, adapter = staged
    adapter.snapshot["blocks"].append(dict(name="EM", type="CSTMWS", pins=[
        dict(pin_name="1", port_index=0)]))
    link = dict(block_name="EM", source="self", parameter_map={}, port_map=[
        dict(pin_name="1", port_id=1, mode=1, reference="ground", polarity=1)])
    assert api.apply(dict(schema_version=1, em_links=[link]))["applied"]
    assert adapter.writes[0]["blocks"] == []


def test_native_probe_members_preserve_occupancy_of_other_pins(staged):
    api, adapter = staged
    adapter.snapshot["nets"] = [dict(name="other", subnets=[[
        ["Block", "R1", 9], ["Externalport", "P2", 0], ["Probe", "old_sense", 0]]])]
    assert api.apply(wire_spec())["applied"]
