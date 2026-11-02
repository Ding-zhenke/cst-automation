"""Saved-result readback acceptance. No CST imports during test collection."""
import os
from pathlib import Path
import pytest

pytestmark = pytest.mark.cst_live


def test_saved_schematic_readback_opt_in():
    if os.environ.get("CST_CIRCUIT_LIVE") != "1":
        pytest.skip("Explicit CST_CIRCUIT_LIVE=1 required")
    path = os.environ.get("CST_CIRCUIT_SAVED_PROJECT")
    if not path or not Path(path).is_file():
        pytest.fail("CST_CIRCUIT_SAVED_PROJECT must name an existing saved work copy")
    from cst_solver.circuit import CircuitResult
    reader = CircuitResult(path)
    items = reader.get_tree_items()
    assert items, "No saved schematic results; this does not prove a solver run"
    tree = os.environ.get("CST_CIRCUIT_TREE_PATH")
    run = os.environ.get("CST_CIRCUIT_RUN_ID")
    assert tree and run is not None, "Explicit actual tree path and run ID required"
    curve = reader.read_curve(tree, run_id=int(run))
    assert curve["x"] and len(curve["x"]) == len(curve["y"])
    assert curve["domain"] == "schematic"
