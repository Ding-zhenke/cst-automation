"""Regressions for non-default modeling choices found during the API audit."""
from types import SimpleNamespace
import pytest

from cst_solver import setup as CstSetup


def recorder():
    app = CstSetup.__new__(CstSetup)
    blocks = []
    app.cst_file = SimpleNamespace(model3d=SimpleNamespace(
        add_to_history=lambda name, code: blocks.append(code)))
    return app, blocks


def test_asymmetric_boundaries_keep_each_requested_face():
    app, blocks = recorder()
    values = dict(xmin='electric', xmax='open', ymin='magnetic',
                  ymax='expanded open', zmin='periodic', zmax='unit cell')
    app.boundary(**values)
    for face, value in values.items():
        assert f'.{face.capitalize()} "{value}"' in blocks[-1]


def test_hexagonal_prism_profile_uses_the_requested_curve_group():
    app, blocks = recorder()
    app.create_hexagonal_prism(2, 1, [0, 0, 0], [0, 0, 0], 'hole',
                              curve='profiles', component='etch')
    assert '.Curve "profiles"' in blocks[-1]
    assert 'profiles:hole' in blocks[-1]
    assert '.Component "etch"' in blocks[-1]


def test_torus_converts_centerline_and_tube_radii_to_native_extents():
    app, blocks = recorder()
    app.create_torus('R', 'r', 'ring')
    assert '.OuterRadius "(R)+(r)"' in blocks[-1]
    assert '.InnerRadius "(R)-(r)"' in blocks[-1]


def test_focused_deletion_names_exact_solid_and_curve_item():
    app, blocks = recorder()
    app.delete_solid('hole', component='etch')
    app.delete_curve_item('profile', curve='profiles')
    assert blocks == ['Solid.Delete "etch:hole"',
                      'Curve.DeleteCurveItem "profiles", "profile"']


@pytest.mark.parametrize('bad', ['', 'c:other', 'one\nSolid.Delete "all"', '"bad'])
def test_deletion_rejects_ambiguous_names_before_history(bad):
    app, blocks = recorder()
    for method in (app.delete_solid, app.delete_curve_item):
        with pytest.raises(ValueError):
            method(bad)
    assert not blocks
