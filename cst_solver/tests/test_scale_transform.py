"""Scale-factor propagation and pre-write validation; no CST SDK is loaded."""
from types import SimpleNamespace

import pytest

from cst_solver.modeling.transforms import TransformMixin


def app_and_history():
    history = []
    app = TransformMixin()
    app.cst_file = SimpleNamespace(model3d=SimpleNamespace(
        add_to_history=lambda name, code: history.append(code)))
    return app, history


@pytest.mark.parametrize('factor, expected', [
    (2, '.ScaleFactor "2", "2", "2"'),
    (0.5, '.ScaleFactor "0.5", "0.5", "0.5"'),
    ('size_ratio', '.ScaleFactor "size_ratio", "size_ratio", "size_ratio"'),
    ('a/2', '.ScaleFactor "a/2", "a/2", "a/2"'),
    ([2, 'scale_y', 0.5], '.ScaleFactor "2", "scale_y", "0.5"'),
    ((1, 2, 3), '.ScaleFactor "1", "2", "3"'),
])
def test_requested_scale_factors_reach_native_transform(factor, expected):
    app, history = app_and_history()
    app.scale('arm', factor, center=['cx', 0, 'cz'], component='device')
    assert len(history) == 1
    code = history[0]
    assert expected in code
    assert '.Name "device:arm"' in code
    assert '.Center "cx", "0", "cz"' in code
    assert code.index(expected) < code.index('.Transform "Shape", "Scale"')


@pytest.mark.parametrize('kwargs', [
    dict(factor=True), dict(factor=float('nan')), dict(factor=float('inf')),
    dict(factor=[]), dict(factor=[1, 2]), dict(factor=[1, 2, 3, 4]),
    dict(factor=[1, False, 2]), dict(factor=[1, float('inf'), 2]),
    dict(factor=''), dict(factor='scale"\n.End'), dict(factor={'x': 1}),
    dict(factor=2, center=[0, 0]), dict(factor=2, center=[0, True, 0]),
    dict(factor=2, center=[0, 0, float('nan')]),
    dict(factor=2, name='arm"'), dict(factor=2, component='device\nother'),
])
def test_invalid_scale_is_rejected_before_history(kwargs):
    app, history = app_and_history()
    arguments = dict(name='arm', factor=2)
    arguments.update(kwargs)
    with pytest.raises(ValueError):
        app.scale(**arguments)
    assert history == []
