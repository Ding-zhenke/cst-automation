"""Offline contract tests for full complex permeability tensor materials."""

from types import SimpleNamespace

import pytest

from cst_solver import setup as CstSetup
from cst_solver.material.materials import MaterialMixin


class _App(MaterialMixin):
    def __init__(self):
        self.history = []
        self.cst_file = SimpleNamespace(model3d=SimpleNamespace(
            add_to_history=lambda label, vba: self.history.append((label, vba))))


IDENTITY = [[1, 0, 0], [0, 1, 0], [0, 0, 1]]


def test_full_complex_tensor_preserves_indices_and_converts_imaginary_sign():
    app = _App()
    matrix = [[complex(3*r+c+1, 3*r+c-4) for c in range(3)]
              for r in range(3)]
    app.create_material_tensor('ferrite', 12, matrix, color='#123456')
    assert len(app.history) == 1
    label, vba = app.history[0]
    assert label == 'Material: ferrite'
    assert '.Type "Tensor formula"' in vba
    assert vba.index('.TensorFormulaFor "epsilon_r"') < vba.index(
        '.TensorFormulaFor "mu_r"') < vba.index('.Create')
    eps, mu = vba.split('.TensorFormulaFor "mu_r"')
    for r in range(3):
        assert f'.TensorFormulaReal {r}, {r}, "12"' in eps
        for c in range(3):
            assert f'.TensorFormulaReal {r}, {c}, "{matrix[r][c].real}"' in mu
            expected = -matrix[r][c].imag
            assert f'.TensorFormulaImag {r}, {c}, "{expected}"' in mu
    assert mu.count('.TensorFormulaReal') == 9
    assert mu.count('.TensorFormulaImag') == 9
    assert '.Colour ' in vba
    assert '.Mu ' not in vba
    assert '.Epsilon ' not in vba


def test_project_parameters_and_hz_frequency_expressions_are_not_evaluated():
    app = _App()
    real = [['mu_d+fm^2/(f0^2-f^2)', 0, 0], [0, 'mu_d', 0], [0, 0, 1]]
    imag = [[0, 'kappa_m*f/f0', 0], ['-kappa_m*f/f0', 0, 0], [0, 0, '-loss']]
    app.create_material_tensor('parametric', 'eps_r', real, mu_imag=imag)
    vba = app.history[0][1]
    assert '.TensorFormulaReal 0, 0, "mu_d+fm^2/(f0^2-f^2)"' in vba
    assert '.TensorFormulaImag 0, 1, "-(kappa_m*f/f0)"' in vba
    assert '.TensorFormulaImag 1, 0, "-(-kappa_m*f/f0)"' in vba
    assert '.TensorFormulaReal 2, 2, "eps_r"' in vba


def test_real_tensor_has_zero_imaginary_entries_and_colour_alias():
    app = _App()
    app.create_material_tensor('real', 1, tuple(map(tuple, IDENTITY)), colour='#fff')
    assert app.history[0][1].count(', "0"') >= 9
    assert '.Colour "1", "1", "1"' in app.history[0][1]
    assert callable(CstSetup.create_material_tensor)


@pytest.mark.parametrize('kwargs', [
    {'mu_tensor': [[1, 0], [0, 1]]},
    {'mu_tensor': [[1, 0, 0], [0, 1], [0, 0, 1]]},
    {'mu_tensor': 'mu'},
    {'mu_imag': [[0]]},
    {'mu_tensor': [[True, 0, 0], [0, 1, 0], [0, 0, 1]]},
    {'mu_tensor': [[float('inf'), 0, 0], [0, 1, 0], [0, 0, 1]]},
    {'mu_tensor': [[complex(1, float('nan')), 0, 0], [0, 1, 0], [0, 0, 1]]},
    {'mu_tensor': [[1j, 0, 0], [0, 1, 0], [0, 0, 1]], 'mu_imag': IDENTITY},
    {'mu_imag': [[1j, 0, 0], [0, 1, 0], [0, 0, 1]]},
    {'mu_tensor': [['', 0, 0], [0, 1, 0], [0, 0, 1]]},
    {'mu_tensor': [['a"', 0, 0], [0, 1, 0], [0, 0, 1]]},
    {'epsilon': 'eps\n.Create'},
    {'epsilon': complex(1, 2)},
    {'name': 'bad"name'},
    {'color': '#fff', 'colour': '#000'},
    {'color': 'invalid'},
])
def test_invalid_input_never_accesses_project(kwargs):
    params = dict(name='bad', epsilon=1, mu_tensor=IDENTITY)
    params.update(kwargs)
    # No cst_file: input errors must precede even project access.
    with pytest.raises(ValueError):
        MaterialMixin().create_material_tensor(**params)
