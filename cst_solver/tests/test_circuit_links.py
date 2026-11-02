from pathlib import Path
import pytest

from cst_solver.circuit.links import dependency_manifest, bundle_project
from cst_solver.circuit.adapter import CircuitError


def snapshot(filename):
    return {"blocks": [{"name": "D", "files": [str(filename)]}], "unknown": []}


def test_missing_spice_include_is_reported(tmp_path):
    project = tmp_path / "a.cst"
    project.write_text("project")
    model = tmp_path / "diode.cir"
    model.write_text('.include "missing.lib"\n')
    report = dependency_manifest(str(project), snapshot(model))
    assert not report["complete"]
    assert any(not f["exists"] and f["path"].endswith("missing.lib") for f in report["files"])


def test_include_cycle_is_rejected(tmp_path):
    project = tmp_path / "a.cst"
    project.write_text("project")
    model = tmp_path / "diode.cir"
    model.write_text('.include "diode.cir"\n')
    report = dependency_manifest(str(project), snapshot(model))
    assert not report["complete"] and "cycle" in str(report["unknown"]).lower()


def test_unknown_dependency_prevents_portable_claim(tmp_path):
    project = tmp_path / "a.cst"
    project.write_text("project")
    report = dependency_manifest(str(project), {"blocks": [{"name": "EM", "files": None}], "unknown": []})
    with pytest.raises(CircuitError): bundle_project(str(project), report, str(tmp_path / "out"))


def test_bundle_does_not_overwrite_source_or_claim_cst_relocation(tmp_path):
    project = tmp_path / "a.cst"
    project.write_text("original")
    model = tmp_path / "diode.cir"
    model.write_text("* diode\n")
    manifest = dependency_manifest(str(project), snapshot(model))
    with pytest.raises(CircuitError): bundle_project(str(project), manifest, str(tmp_path))
    out = bundle_project(str(project), manifest, str(tmp_path / "bundle"))
    assert project.read_text() == "original"
    assert out["portable_verified"] is False
    assert Path(out["project"]).read_text() == "original"
    assert out["relocation_required"]

def test_bundle_omits_runtime_project_lock_but_preserves_model_data(tmp_path):
    from cst_solver.circuit.links import bundle_project,dependency_manifest
    source=tmp_path/'model.cst';source.write_text('saved')
    companion=source.with_suffix('');companion.mkdir()
    (companion/'Model.lok').write_text('runtime owner lock')
    (companion/'geometry.bin').write_bytes(b'actual model data')
    target=tmp_path/'relocated'
    result=bundle_project(source,dependency_manifest(source,{'blocks':[]}),target)
    assert not (target/'model/Model.lok').exists()
    assert (target/'model/geometry.bin').read_bytes()==b'actual model data'
    assert (companion/'Model.lok').read_text()=='runtime owner lock'
    assert result['portable_verified'] is False
