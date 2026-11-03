import json
import pytest

from cst_automation.circuit_sample import microstrip_sample, preview_microstrip


def test_exact_geometry_has_conductor_endpoints_and_explicit_reference():
    data = microstrip_sample()
    assert data["unit"] == "mm"
    assert data["solids"]["substrate"]["bounds"] == [[-10, 10], [-5, 5], [0, 0.8]]
    assert data["solids"]["strip"]["bounds"][2] == [0.8, 0.835]
    assert data["ports"][0]["p1"] == [-9.5, 0, 0]
    assert data["ports"][1]["p2"] == [9.5, 0, 0.8]
    assert data["ports"][0]["reference"] == "ground"
    assert data["geometry_verified"] is False


def test_sample_preview_uses_same_parameter_source(tmp_path):
    out = preview_microstrip(str(tmp_path), raster=False)
    data = json.loads((tmp_path / "geometry.json").read_text(encoding="utf-8"))
    assert data["geometry"] == microstrip_sample()
    svg = (tmp_path / "geometry.svg").read_text(encoding="utf-8")
    assert "19 mm" in svg and "0.035 mm" in svg
    assert (tmp_path / "ports.csv").exists()
