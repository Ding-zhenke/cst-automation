from types import SimpleNamespace
import json
import pytest

from cst_solver.circuit.results import CircuitResult
from cst_solver.circuit.adapter import CircuitError


@pytest.fixture
def reader(tmp_path, monkeypatch):
    path = tmp_path / "circuit.cst"
    path.write_text("fixture", encoding="utf-8")
    item = SimpleNamespace(get_xdata=lambda: [SimpleNamespace(value=1, unit="GHz"), SimpleNamespace(value=2, unit="GHz")],
                           get_ydata=lambda: [SimpleNamespace(value=1+2j, unit="V"), SimpleNamespace(value=3-4j, unit="V")])
    module = SimpleNamespace(get_tree_items=lambda: ["T\\Voltages\\V1"], get_run_ids=lambda tree: [4, 7],
                             get_parameter_combination=lambda run: {"Cval": 1e-12},
                             get_result_item=lambda tree, run_id: item)
    project = SimpleNamespace(get_schematic=lambda: module, get_3d=lambda: pytest.fail("wrong result domain"))
    import cst_solver.circuit.results as target
    monkeypatch.setattr(target, "_load_cst_module", lambda name: SimpleNamespace(ProjectFile=lambda *a, **k: project))
    return CircuitResult(str(path))


def test_saved_schematic_results_keep_complex_units_and_run(reader):
    curve = reader.read_curve("T\\Voltages\\V1", run_id=7)
    assert curve["y"] == [1+2j, 3-4j]
    assert curve["x_unit"] == "GHz" and curve["y_unit"] == "V"
    assert curve["run_id"] == 7 and curve["domain"] == "schematic"


def test_missing_curve_and_missing_run_do_not_fall_back(reader):
    for tree, run in [("Missing", 7), ("T\\Voltages\\V1", 0)]:
        with pytest.raises(CircuitError): reader.read_curve(tree, run_id=run)


def test_export_csv_has_real_imag_and_metadata(reader, tmp_path):
    dest = tmp_path / "voltage.csv"
    out = reader.export_csv("T\\Voltages\\V1", str(dest), run_id=4)
    assert "1.0,1.0,2.0" in dest.read_text(encoding="utf-8-sig")
    metadata = json.loads((tmp_path / "voltage.csv.json").read_text(encoding="utf-8"))
    assert metadata["run_id"] == 4 and metadata["amplitude_convention"] == "unknown"
    assert len(out["artifacts"]) == 2


@pytest.mark.parametrize("target", ["circuit.cst", "another.cst", "existing.csv"])
def test_export_refuses_project_or_existing_file_collision(reader, tmp_path, target):
    path = tmp_path / target
    path.write_text("preserve", encoding="utf-8")
    with pytest.raises(CircuitError): reader.export_csv("T\\Voltages\\V1", str(path), run_id=4)
    assert path.read_text(encoding="utf-8") == "preserve"


def test_export_refuses_metadata_collision_before_writing_curve(reader, tmp_path):
    target = tmp_path / "out.csv"
    Path = type(target)
    Path(str(target) + ".json").write_text("preserve", encoding="utf-8")
    with pytest.raises(CircuitError): reader.export_csv("T\\Voltages\\V1", str(target), run_id=4)
    assert not target.exists()
