import copy
import json
import subprocess
import sys

import pytest

from cst_automation.circuit_schema import CircuitSpecError, validate_circuit_spec
from cst_automation.circuit_preview import preview_circuit


def spec():
    return {"schema_version": 1, "units": {"Frequency": "GHz"},
            "parameters": {"Cval": {"value": 1, "unit": "pF"}},
            "blocks": [{"name": "C1", "type": "CircuitBasic\\Capacitor",
                        "properties": {"Capacitance": "2*Cval"},
                        "property_units": {"Capacitance": "pF"}, "position": [50000, 50000]}],
            "external_ports": [{"name": "P1", "position": [49500, 50000]},
                               {"name": "P2", "position": [50500, 50000]}],
            "nets": [{"name": "in", "endpoints": [ep("ExternalPort", "P1", "1"), ep("Block", "C1", "1")]},
                     {"name": "out", "endpoints": [ep("Block", "C1", "2"), ep("ExternalPort", "P2", "1")]}],
            "probes": [], "em_links": [],
            "tasks": [{"name": "SP", "type": "s-parameters", "properties": {"fmin": "0.1", "fmax": "3"}}]}


def ep(kind, name, pin):
    return {"component_kind": kind, "component_name": name, "pin_name": pin}


def test_units_preserve_pf_expression_and_do_not_mutate_input():
    raw = spec()
    original = copy.deepcopy(raw)
    result = validate_circuit_spec(raw)
    assert result["blocks"][0]["properties"]["Capacitance"] == "2*Cval"
    assert result["resolved_si"]["blocks"]["C1"]["Capacitance"] == pytest.approx(2e-12)
    result["blocks"][0]["name"] = "modified"
    assert raw == original


@pytest.mark.parametrize("case", ["duplicate", "endpoint", "unit", "dimension", "expression", "cross_domain", "double_net", "unknown_key", "bool_version"])
def test_reject_invalid_specs(case):
    raw = spec()
    if case == "duplicate": raw["external_ports"][0]["name"] = "C1"
    if case == "endpoint": raw["nets"][0]["endpoints"][0]["component_name"] = "missing"
    if case == "unit": raw["blocks"][0]["property_units"]["Capacitance"] = "bad"
    if case == "dimension": raw["blocks"][0]["property_units"]["Capacitance"] = "nH"
    if case == "expression": raw["blocks"][0]["properties"]["Capacitance"] = "__import__('os')"
    if case == "cross_domain": raw["parameters"]["Cval"]["scope"] = "em"
    if case == "double_net": raw["nets"][1]["endpoints"].append(ep("Block", "C1", "1"))
    if case == "unknown_key": raw["run_all"] = True
    if case == "bool_version": raw["schema_version"] = True
    with pytest.raises(CircuitSpecError): validate_circuit_spec(raw)


def test_preview_contains_connections_parameters_and_digest(tmp_path):
    out = preview_circuit(spec(), str(tmp_path))
    data = json.loads((tmp_path / "circuit.json").read_text(encoding="utf-8"))
    svg = (tmp_path / "circuit.svg").read_text(encoding="utf-8")
    assert data["spec"]["nets"][1]["name"] == "out"
    assert "C1" in svg and "2*Cval" in svg and "pF" in svg
    assert len(out["spec_digest"]) == 64
    assert (tmp_path / "connections.csv").is_file()


def test_preview_does_not_load_cst(tmp_path):
    code = "import sys; from cst_automation.circuit_preview import preview_circuit; import cst_solver.circuit; assert not any(n == 'cst' or n.startswith('cst.') for n in sys.modules)"
    result = subprocess.run([sys.executable, "-B", "-c", code], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_linked_em_endpoint_is_validated_without_duplicate_em_block():
    raw = spec()
    raw["em_links"] = [{"block_name": "EM", "source": "self", "port_map": [{"pin_name": "1", "port_id": 1, "mode": 1, "reference": "ground", "polarity": 1}], "parameter_map": {}}]
    raw["nets"][0]["endpoints"][0] = ep("Block", "EM", "1")
    assert validate_circuit_spec(raw)["em_links"][0]["source"] == "self"


def test_linked_em_preview_includes_external_block(tmp_path):
    raw = spec()
    raw["em_links"] = [{"block_name": "EM", "source": "self", "port_map": [{"pin_name": "1", "port_id": 1, "mode": 1, "reference": "ground", "polarity": 1}], "parameter_map": {}}]
    raw["nets"][0]["endpoints"][0] = ep("Block", "EM", "1")
    preview_circuit(raw, str(tmp_path))
    assert "EM" in (tmp_path / "circuit.svg").read_text(encoding="utf-8")


def test_task_excitation_requires_existing_external_port():
    raw = spec()
    raw["tasks"][0]["excitations"] = {"missing": {"type": "Sine", "values": [1, 1]}}
    with pytest.raises(CircuitSpecError): validate_circuit_spec(raw)


def test_ground_block_and_rotation_are_explicit_supported_geometry():
    raw = {"schema_version": 1, "blocks": [{"name": "GND", "type": "Ground", "rotation": 90}]}
    assert validate_circuit_spec(raw)["blocks"][0]["rotation"] == 90


def test_unknown_block_fields_are_not_silently_ignored():
    raw = spec()
    raw["blocks"][0]["rotate_by_typo"] = 90
    with pytest.raises(CircuitSpecError): validate_circuit_spec(raw)
