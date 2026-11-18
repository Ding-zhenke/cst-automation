from types import SimpleNamespace

import pytest

from cst_solver import setup as CstSetup
from tpc_service.errors import ServiceError
from tpc_service.sessions.model_api import dispatch


@pytest.mark.parametrize("method, options, native", [
    ("create_discrete_face_port", {"r0": 50, "id_val": 3}, "DiscreteFacePort"),
    ("create_lumped_face_element", {"name": "Load", "r": "Rload", "l": 1e-9,
                                    "c": 1e-12, "element_type": "RLCParallel"}, "LumpedFaceElement"),
])
def test_gap_contact_history_uses_both_picked_strip_edges(method, options, native):
    left = ["-gap/2", 0, "sub_h+metal_t"]
    right = ["gap/2", 0, "sub_h+metal_t"]
    history = []
    app = object.__new__(CstSetup)
    app.cst_file = SimpleNamespace(model3d=SimpleNamespace(
        add_to_history=lambda title, command: history.append(command)))
    dispatch(app, [
        {"method": "pick_clear"},
        {"method": "pick_edge_at", "args": ["strip_left", *left]},
        {"method": "pick_edge_at", "args": ["strip_right", *right]},
        {"method": method, "kwargs": {**options, "p1": left, "p2": right}},
    ])
    clear, first, second, create = history
    assert "Pick.ClearAllPicks" in clear
    assert 'Pick.PickEdgeFromPoint "component1:strip_left", "-gap/2"' in first
    assert 'Pick.PickEdgeFromPoint "component1:strip_right", "gap/2"' in second
    assert f"With {native}" in create
    assert '.SetP1 True, "-gap/2", "0", "sub_h+metal_t"' in create.replace('"True"', 'True')
    assert '.SetP2 True, "gap/2", "0", "sub_h+metal_t"' in create.replace('"True"', 'True')
    if native == "LumpedFaceElement":
        assert '.SetType "RLCParallel"' in create
        assert '.SetR "Rload"' in create
        assert '.SetL "1e-09"' in create
        assert '.SetC "1e-12"' in create


@pytest.mark.parametrize("changes", [{"p2": [0, 1]}, {"element_type": "Diode"}])
def test_invalid_face_element_is_rejected_before_first_pick(changes):
    options = {"name": "Load", "r": 50, "p1": [0, 0, 0], "p2": [1, 0, 0], **changes}
    with pytest.raises(ServiceError, match="Invalid modeling method signature"):
        dispatch(object(), [{"method": "pick_clear"},
                            {"method": "create_lumped_face_element", "kwargs": options}])
