from types import SimpleNamespace
from tpc_service.sessions.model_api import dispatch
from cst_solver.import_export.io import IOMixin

def test_binary_sab_uses_existing_sat_reader(tmp_path):
    asset = tmp_path / "source.sab"
    asset.write_bytes(b"ACIS BinaryFile")
    history = []
    app = IOMixin()
    app.cst_file = SimpleNamespace(model3d=SimpleNamespace(add_to_history=lambda *args: history.append(args)))
    dispatch(app, [{"method": "import_sat", "args": [str(asset)], "kwargs": {"tpn": False}}])
    assert len(history) == 1
    assert str(asset) in history[0][1]
    assert '.ScaleToUnit "0"' in history[0][1]
