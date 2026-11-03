"""Regression against the CST Create Full Tensor Material command contract."""
import pytest
from test_material_tensor import _App, IDENTITY

def test_full_electric_and_magnetic_tensors_have_explicit_axes_and_all_entries():
    app = _App()
    eps = [[complex(3*r+c+2, r-c) for c in range(3)] for r in range(3)]
    app.create_material_full_tensor('full', eps, IDENTITY,
        mu_imag=[[0, 'ka', 0], ['-ka', 0, 0], [0, 0, 0]])
    vba = app.history[0][1]
    assert vba.count('.TensorFormulaReal') == 18
    assert vba.count('.TensorFormulaImag') == 18
    assert vba.count('.TensorAlignment2 "1", "0", "0", "0", "1", "0"') == 2
    e, m = vba.split('.TensorFormulaFor "mu_r"')
    for r in range(3):
        for c in range(3):
            assert f'.TensorFormulaReal {r}, {c}, "{eps[r][c].real}"' in e
            assert f'.TensorFormulaImag {r}, {c}, "{-eps[r][c].imag}"' in e
    assert '.TensorFormulaImag 0, 1, "-(ka)"' in m
    assert '.TensorFormulaImag 1, 0, "-(-ka)"' in m

@pytest.mark.parametrize('kwargs', [
    {'epsilon_tensor': [[1]]},
    {'epsilon_imag': [[0]]},
    {'epsilon_tensor': [[1j,0,0],[0,1,0],[0,0,1]], 'epsilon_imag': IDENTITY},
    {'epsilon_axes': ((1,0,0),(2,0,0))},
    {'mu_axes': ((0,0,0),(0,1,0))},
    {'mu_axes': ((1,0,0),(1,1,0))},
])
def test_bad_full_tensor_is_rejected_before_project_access(kwargs):
    from cst_solver.material.materials import MaterialMixin
    args = dict(name='bad', epsilon_tensor=IDENTITY, mu_tensor=IDENTITY)
    args.update(kwargs)
    with pytest.raises(ValueError):
        MaterialMixin().create_material_full_tensor(**args)

def test_legacy_helper_now_uses_explicit_global_axes_for_each_property():
    app = _App()
    app.create_material_tensor('YIG', 'er', IDENTITY)
    assert app.history[0][1].count('.TensorAlignment2') == 2
