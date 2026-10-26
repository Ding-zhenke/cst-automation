"""Static template checks and filesystem staging; never execute template code."""
import hashlib
import os

import pytest

from cst_automation.result_templates import (
    ResultTemplateError, stage_python_result_template, validate_python_result_template,
)


SOURCE = ('raise RuntimeError("must not execute")\n'
          'def define(def_params, settings):\n    pass\n'
          'def evaluate(eval_params, calling_app, settings):\n    yield "metric", None\n')


def test_stage_copies_bytes_without_executing_or_overwriting(tmp_path):
    source = tmp_path / 'source.py'
    source.write_bytes(SOURCE.encode('utf-8'))
    root = tmp_path / 'library'
    report = stage_python_result_template(source, root, group='Example', name='Metric')
    destination = root / 'Result Templates' / 'Example' / 'Metric.rtpy'
    assert destination.read_bytes() == SOURCE.encode('utf-8')
    assert report['sha256'] == hashlib.sha256(destination.read_bytes()).hexdigest()
    assert report['native_cst_binding_required'] is True
    assert report['validation']['executed'] is False
    with pytest.raises(ResultTemplateError):
        stage_python_result_template(source, root, group='Example', name='Metric')
    assert destination.read_bytes() == SOURCE.encode('utf-8')


@pytest.mark.parametrize('signature', ['settings=None', 'settings, /', '*, settings=None'])
def test_rejects_signatures_native_cst_cannot_invoke(signature):
    source = f'def define({signature}):\n    pass\ndef evaluate(settings):\n    pass\n'
    with pytest.raises(ResultTemplateError):
        validate_python_result_template(source)


@pytest.mark.parametrize('group,name', [('../escape', 'Metric'), ('Example', 'CON'),
                                        ('Example', 'name.'), ('Example', 'a/b')])
def test_unsafe_names_never_create_library(tmp_path, group, name):
    source = tmp_path / 'source.py'
    source.write_text(SOURCE, encoding='utf-8')
    root = tmp_path / 'library'
    with pytest.raises(ResultTemplateError):
        stage_python_result_template(source, root, group=group, name=name)
    assert not root.exists()


def directory_link(target, link):
    if os.name == 'nt':
        import _winapi
        _winapi.CreateJunction(str(target), str(link))
    else:
        link.symlink_to(target, target_is_directory=True)


def test_staging_rejects_link_redirecting_group_outside_library(tmp_path):
    source = tmp_path / 'source.py'
    source.write_text(SOURCE, encoding='utf-8')
    root = tmp_path / 'library'
    templates = root / 'Result Templates'
    templates.mkdir(parents=True)
    outside = tmp_path / 'outside'
    outside.mkdir()
    link = templates / 'Example'
    directory_link(outside, link)
    try:
        with pytest.raises(ResultTemplateError):
            stage_python_result_template(source, root, group='Example', name='Metric')
        assert not (outside / 'Metric.rtpy').exists()
    finally:
        if os.name == 'nt':
            link.rmdir()
        else:
            link.unlink()
