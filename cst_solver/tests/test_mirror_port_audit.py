from types import SimpleNamespace
import pytest
from cst_solver.modeling.transforms import TransformMixin


@pytest.mark.parametrize('name', ['Port 2', 2])
def test_port_mirror_uses_port_identity_and_destination(name):
    app = TransformMixin()
    blocks = []
    app.cst_file = SimpleNamespace(model3d=SimpleNamespace(
        add_to_history=lambda label, code: blocks.append(code)))
    app.mirror(name, [0, 0, 0], [1, 0, 0], object='Port', copy=True)
    assert '.Name "Port 2"' in blocks[-1]
    assert '.AutoDestination "False"' in blocks[-1]
    assert '.Transform "Port", "Mirror"' in blocks[-1]
    assert 'component1:Port' not in blocks[-1]
