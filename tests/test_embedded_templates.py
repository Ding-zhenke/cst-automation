import hashlib
import json
import pytest
from cst_automation.result_templates import ResultTemplateError, replace_embedded_python_result_template

SOURCE = 'def define(def_params, settings):\n    pass\n\ndef evaluate(eval_params, calling_app, settings):\n    yield "metric", None\n'


@pytest.fixture
def binding(tmp_path):
    resources = tmp_path / 'project'
    folder = resources / 'Model/DS/Task/example'; folder.mkdir(parents=True)
    module = folder / 'bound.rtpy'; module.write_text('original', encoding='utf-8')
    meta = folder / 'bound.rtjson'
    meta.write_text(json.dumps({'template': {'python_module': {'path': module.name}, 'settings': {'hb_task': 'MyHB'}}}), encoding='utf-8')
    source = tmp_path / 'new.py'; source.write_text(SOURCE, encoding='utf-8')
    return resources, module, meta, source


def test_updates_only_explicit_binding_and_retains_metadata(binding):
    root, module, meta, source = binding
    before = meta.read_bytes()
    result = replace_embedded_python_result_template(source, root, metadata_path=meta,
        expected_sha256=hashlib.sha256(module.read_bytes()).hexdigest())
    assert module.read_text(encoding='utf-8') == SOURCE and meta.read_bytes() == before
    assert result['native_save_required'] is True and result['readback_verified'] is False


def test_hash_conflict_leaves_existing_module_untouched(binding):
    root, module, meta, source = binding
    with pytest.raises(ResultTemplateError):
        replace_embedded_python_result_template(source, root, metadata_path=meta, expected_sha256='0'*64)
    assert module.read_text() == 'original'


def test_bound_module_cannot_escape_project(binding):
    root, module, meta, source = binding
    meta.write_text(json.dumps({'template': {'python_module': {'path': str(source)}}}), encoding='utf-8')
    with pytest.raises(ResultTemplateError):
        replace_embedded_python_result_template(source, root, metadata_path=meta, expected_sha256='0'*64)
    assert module.read_text() == 'original'


def test_invalid_source_does_not_replace_bound_module(binding):
    root, module, meta, source = binding; source.write_text('raise RuntimeError("do not execute")')
    with pytest.raises(ResultTemplateError):
        replace_embedded_python_result_template(source, root, metadata_path=meta,
            expected_sha256=hashlib.sha256(module.read_bytes()).hexdigest())
    assert module.read_text() == 'original'
