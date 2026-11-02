from types import SimpleNamespace

import pytest

from cst_automation import circuit_tasks
from cst_automation.circuit_schema import CircuitSpecError
from cst_solver.circuit.api import CircuitAPI
from cst_solver.circuit.adapter import CircuitError, NativeAdapter


def manual():
    return {"period": {"value": 12.5, "unit": "ns"}, "tolerance": 2e-6}


def test_normalization_infers_manual_or_automatic_without_mutating_input():
    original = manual()
    normalized = circuit_tasks.steady_state_settings(original)
    assert normalized == {"automatic_period": False, "period_si": pytest.approx(12.5e-9), "tolerance": 2e-6}
    assert original == manual()
    assert circuit_tasks.steady_state_settings({}) == {"automatic_period": True}


@pytest.mark.parametrize("settings", [
    None, {"unknown": 1}, {"automatic_period": "false"},
    {"automatic_period": True, "period": {"value": 1, "unit": "ns"}},
    {"automatic_period": False}, {"period": {"value": 1, "unit": "V"}},
    {"period": {"value": 0, "unit": "ns"}}, {"period": {"value": True, "unit": "ns"}},
    {"period": {"value": float("inf"), "unit": "ns"}},
    {"tolerance": True}, {"tolerance": 0}, {"tolerance": 1},
    {"tolerance": float("nan")}, {"tolerance": "0.001"},
])
def test_invalid_settings_do_not_access_sdk(settings):
    with pytest.raises(CircuitSpecError):
        CircuitAPI(SimpleNamespace(cst_file=None)).configure_steady_state_task("SS", settings)


class Task:
    def __init__(self, kind="transient", unit="us"):
        self.kind, self.unit, self.calls = kind, unit, []
        self.values = {"time step": "0.1", "sampling method": "Simulated",
                       "steady state tolerance": "0.001", "steady state period": "999"}
    def Reset(self): pass
    def Name(self, name): self.name = name
    def DoesExist(self): return self.kind is not None
    def GetTypeForTask(self, name): return self.kind
    def GetUnit(self, dimension): return self.unit
    def Type(self, kind): self.calls.append(("type", kind))
    def Create(self): self.kind = "transient"; self.calls.append(("create", self.name))
    def SetProperty(self, key, value): self.calls.append((key, value)); self.values[key] = value
    def GetProperty(self, key): return self.values[key]


def adapter(task, global_unit="ms"):
    return NativeAdapter(SimpleNamespace(cst_file=SimpleNamespace(schematic=SimpleNamespace(
        SimulationTask=task, Units=SimpleNamespace(GetUnit=lambda dim: global_unit)))))


def test_manual_period_uses_task_local_units_and_does_not_change_other_settings():
    task = Task()
    api = CircuitAPI(SimpleNamespace(), adapter=adapter(task))
    report = api.configure_steady_state_task("SS", manual())
    assert task.values["circuit simulator"] == "cst - steady state"
    assert task.values["steady state period detection"].lower() == "false"
    assert float(task.values["steady state period"]) == pytest.approx(.0125)
    assert float(task.values["steady state tolerance"]) == pytest.approx(2e-6)
    assert task.values["time step"] == "0.1" and task.values["sampling method"] == "Simulated"
    assert report["readback"]["units"] == {"Time": "us"}
    assert report["solver_verified"] is False
    assert report["period_commensurability_verified"] is False
    assert report["steady_state_convergence_verified"] is False


def test_automatic_detection_preserves_unused_period_and_unspecified_tolerance():
    task = Task()
    report = CircuitAPI(SimpleNamespace(), adapter=adapter(task)).configure_steady_state_task("SS", {})
    assert task.values["steady state period detection"].lower() == "true"
    assert task.values["steady state period"] == "999"
    assert task.values["steady state tolerance"] == "0.001"
    assert report["requested_period_si"] is None


@pytest.mark.parametrize("kind,create", [("s-parameters", False), ("transient", True), (None, False)])
def test_existing_task_and_explicit_creation_conflicts_do_not_write(kind, create):
    task = Task(kind)
    with pytest.raises(CircuitError):
        CircuitAPI(SimpleNamespace(), adapter=adapter(task)).configure_steady_state_task("SS", manual(), create=create)
    assert task.calls == []


def test_creation_has_no_save_update_or_source_calls():
    task = Task(None)
    report = CircuitAPI(SimpleNamespace(), adapter=adapter(task, "us")).configure_steady_state_task("SS", manual(), create=True)
    assert ("create", "SS") in task.calls and report["created"] is True


@pytest.mark.parametrize("key,bad", [("circuit simulator", "cst"), ("steady state period", "0"),
                                     ("steady state tolerance", "nan")])
def test_bad_native_readback_reports_partial_and_clears_cache(key, bad):
    task = Task(); get = task.GetProperty
    task.GetProperty = lambda name: bad if name == key else get(name)
    api = CircuitAPI(SimpleNamespace(), adapter=adapter(task)); api._spec = {"old": True}
    with pytest.raises(CircuitError) as error:
        api.configure_steady_state_task("SS", manual())
    assert error.value.code == "circuit_build_partial"
    assert error.value.details["stage"] == "configure_steady_state_task"
    assert api._spec is None


def test_unknown_manual_time_unit_prevents_native_mutation():
    task = Task(unit="unreadable")
    with pytest.raises((CircuitSpecError, CircuitError)):
        CircuitAPI(SimpleNamespace(), adapter=adapter(task)).configure_steady_state_task("SS", manual())
    assert task.calls == []
