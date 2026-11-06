"""Inspect synthetic embedded resources without executing any template code."""
import hashlib
import json

import pytest

from cst_automation import result_templates
from cst_automation.result_templates import ResultTemplateError


def inspect_embedded_python_result_template_files(*args, **kwargs):
    return result_templates.inspect_embedded_python_result_template_files(*args, **kwargs)


@pytest.fixture
def resources(tmp_path):
    root = tmp_path / 'resources'
    folder = root / 'Model/DS/Task/template'; folder.mkdir(parents=True)
    module = folder / 'bound.rtpy'
    # Executing this file would fail; inspecting it must only use the AST.
    module.write_text('raise RuntimeError("do not execute")\ndef define(settings): pass\n'
                      'def evaluate(eval_params, calling_app, settings): yield "metric", None\n', encoding='utf-8')
    metadata = folder / 'bound.rtjson'
    data = {'template': {'python_module': {'path': module.name},
                         'settings': {'input_task': 'ExampleHB', 'opaque': [True, None, 2]}}}
    metadata.write_text(json.dumps(data), encoding='utf-8')
    return root, metadata, module, data


def test_preserves_original_settings_hashes_and_static_only_boundary(resources):
    root, meta, module, data = resources
    before = {path: path.read_bytes() for path in (meta, module)}
    report = inspect_embedded_python_result_template_files(root, metadata_path=meta)
    assert report['metadata'] == data
    assert report['metadata_sha256'] == hashlib.sha256(before[meta]).hexdigest()
    assert report['module_sha256'] == hashlib.sha256(before[module]).hexdigest()
    assert report['module_path'] == str(module)
    assert report['validation']['valid'] is True
    assert report['validation']['executed'] is False
    assert report['native_binding_verified'] is False
    assert report['automatic_update_verified'] is False
    assert report['settings_semantics_verified'] is False
    assert {path: path.read_bytes() for path in before} == before


@pytest.mark.parametrize('failure', ['missing', 'invalid', 'encoding'])
def test_unreadable_or_invalid_module_preserves_binding_and_error(resources, failure):
    root, meta, module, data = resources
    if failure == 'missing': module.unlink()
    elif failure == 'invalid': module.write_text('def broken(', encoding='utf-8')
    else: module.write_bytes(b'\xff\xfe')
    report = inspect_embedded_python_result_template_files(root, metadata_path=meta)
    assert report['metadata'] == data
    assert report['module_error']
    assert report['validation'] is None
    assert report['automatic_update_verified'] is False


def test_external_bound_module_rejected(resources, tmp_path):
    root, meta, module, _ = resources
    outside = tmp_path / 'outside.py'; outside.write_text('raise RuntimeError')
    meta.write_text(json.dumps({'template': {'python_module': {'path': str(outside)}}}))
    with pytest.raises(ResultTemplateError):
        inspect_embedded_python_result_template_files(root, metadata_path=meta)


def test_external_metadata_and_malformed_binding_rejected(resources, tmp_path):
    root, meta, module, _ = resources
    outside = tmp_path / 'other.rtjson'; outside.write_bytes(meta.read_bytes())
    with pytest.raises(ResultTemplateError):
        inspect_embedded_python_result_template_files(root, metadata_path=outside)
    meta.write_text('{"template": {}}')
    with pytest.raises(ResultTemplateError):
        inspect_embedded_python_result_template_files(root, metadata_path=meta)


def test_invalid_path_uses_template_error_boundary(resources):
    root, _, _, _ = resources
    with pytest.raises(ResultTemplateError):
        inspect_embedded_python_result_template_files(root, metadata_path='invalid\x00.rtjson')
