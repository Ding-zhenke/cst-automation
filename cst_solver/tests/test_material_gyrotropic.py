"""Offline native magnetic Gyrotropic material contract."""

from types import SimpleNamespace
from math import pi

import pytest

from cst_solver import setup as CstSetup
from cst_solver.material.materials import MaterialMixin


class _App(MaterialMixin):
    def __init__(self):
        self.history = []
        # Only history submission is available: saving, solving and changing
        # global units must not be needed by the material method.
        self.cst_file = SimpleNamespace(model3d=SimpleNamespace(
            add_to_history=lambda label, vba: self.history.append((label, vba))))


def _params(**kwargs):
    params = dict(name='ferrite', epsilon=12, larmor_omega=10e9,
                  gyrotropic_omega=5e9, damping=0.002)
    params.update(kwargs)
    return params


def test_native_si_coefficients_units_direction_and_single_submission():
    app = _App()
    app.create_material_gyrotropic(**_params(
        bias_direction=(0, -1, 0), mu_infinity=1.2, kappa=0.3, color='#fff'))
    assert len(app.history) == 1
    label, vba = app.history[0]
    assert label == 'Material: ferrite'
    for line in [
        '.Type "Normal"', '.SetMaterialUnit "Hz", "mm"',
        '.Epsilon "12"', '.MuInfinity "1.2"', '.Kappa "0.3"',
        '.DispModelMu "Gyrotropic"', '.UseSISystem "True"',
        '.DispCoeff1Mu "10000000000.0"', '.DispCoeff2Mu "5000000000.0"',
        '.DispCoeff3Mu "0.002"', '.DispCoeff4MuX "0"',
        '.DispCoeff4MuY "-1"', '.DispCoeff4MuZ "0"',
        '.Colour "1", "1", "1"',
    ]:
        assert line in vba
    assert vba.index('.DispModelMu') < vba.index('.DispCoeff1Mu') < vba.index('.Create')
    assert vba.index('.UseSISystem') < vba.index('.DispCoeff1Mu')
    assert 'TensorFormula' not in vba
    assert 'Anisotropic' not in vba
    assert 'Solver' not in vba
    assert callable(CstSetup.create_material_gyrotropic)


def test_all_project_parameter_expressions_are_preserved_without_evaluation():
    app = _App()
    app.create_material_gyrotropic(**_params(
        epsilon='eps_r', larmor_omega='2*pi*fl_ghz*1e9',
        gyrotropic_omega='omega_m', damping='alpha0*scale',
        bias_direction=['sin(theta)', 0, 'cos(theta)'],
        mu_infinity='mu_inf', kappa='sigma', colour='#123456'))
    vba = app.history[0][1]
    for command, value in [
        ('Epsilon', 'eps_r'), ('DispCoeff1Mu', '2*pi*fl_ghz*1e9'),
        ('DispCoeff2Mu', 'omega_m'), ('DispCoeff3Mu', 'alpha0*scale'),
        ('DispCoeff4MuX', 'sin(theta)'), ('DispCoeff4MuZ', 'cos(theta)'),
        ('MuInfinity', 'mu_inf'), ('Kappa', 'sigma'),
    ]:
        assert f'.{command} "{value}"' in vba


def test_default_bias_direction_and_zero_damping_are_supported():
    app = _App()
    app.create_material_gyrotropic(**_params(damping=0))
    vba = app.history[0][1]
    assert '.DispCoeff4MuX "0"' in vba
    assert '.DispCoeff4MuY "0"' in vba
    assert '.DispCoeff4MuZ "1"' in vba
    assert '.DispCoeff3Mu "0"' in vba
    assert '.Colour ' not in vba


def test_angular_frequency_values_are_forwarded_without_implicit_two_pi_conversion():
    app = _App()
    omega_l, omega_m = 2*pi*10e9, 2*pi*5e9
    app.create_material_gyrotropic(**_params(
        larmor_omega=omega_l, gyrotropic_omega=omega_m))
    vba = app.history[0][1]
    assert f'.DispCoeff1Mu "{omega_l}"' in vba
    assert f'.DispCoeff2Mu "{omega_m}"' in vba


@pytest.mark.parametrize('kwargs', [
    {'name': ''}, {'name': 5}, {'name': 'bad"'},
    {'epsilon': True}, {'epsilon': complex(1, 1)},
    {'larmor_omega': -1}, {'gyrotropic_omega': -1},
    {'damping': -0.1}, {'mu_infinity': 0}, {'kappa': -1},
    {'damping': float('nan')}, {'larmor_omega': float('inf')},
    {'gyrotropic_omega': True}, {'damping': 'x\n.Create'},
    {'kappa': 'x"'}, {'mu_infinity': ''},
    {'bias_direction': (0, 0)}, {'bias_direction': 'z'},
    {'bias_direction': (0, 0, 0)}, {'bias_direction': (0, 0, 2)},
    {'bias_direction': (True, 0, 1)},
    {'bias_direction': (0, float('inf'), 1)},
    {'bias_direction': (0, 1j, 1)},
    {'bias_direction': ('x"', 0, 1)},
    {'color': '#fff', 'colour': '#000'}, {'color': 'invalid'},
])
def test_invalid_inputs_fail_before_project_access(kwargs):
    with pytest.raises(ValueError):
        MaterialMixin().create_material_gyrotropic(**_params(**kwargs))
