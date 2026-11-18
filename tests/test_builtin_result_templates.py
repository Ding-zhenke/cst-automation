import struct

import pytest

from cst_automation.builtin_templates import (
    append_index, prepare, resolve_template, settings_resource, touchstone_settings,
)
from cst_automation.result_templates import ResultTemplateError


def test_context_selects_installed_variant_without_fuzzy_matching(tmp_path):
    folder = tmp_path/'General 1D'
    folder.mkdir()
    em = folder/'- Metric^+MWS.rtp'
    ds = folder/'- Metric^+DS.rtp'
    em.write_text('StoreTemplateSetting("TemplateType","1D")\nStoreScriptSetting("Axis", axis)')
    ds.touch()
    selected, source, values, kind, mode = prepare(
        tmp_path, 'General 1D', 'Metric', {'Axis': 'x'}, 'MWS', None, None)
    assert (selected, source, values, kind, mode) == (
        em, em.read_bytes(), {'Axis': 'x', 'TemplateType': '1D'}, '1D', 'legacy')
    assert resolve_template(tmp_path, 'General 1D', '- Metric', 'DS') == ds
    with pytest.raises(ResultTemplateError, match='Unknown scalar'):
        prepare(tmp_path, 'General 1D', 'Metric', {'Axiz': 'x'}, 'MWS', None, None)
    (folder/'Metric.rtp').touch()
    with pytest.raises(ResultTemplateError, match='found 2'):
        resolve_template(tmp_path, 'General 1D', 'Metric', 'MWS')
    with pytest.raises(ResultTemplateError):
        resolve_template(tmp_path, '../General 1D', 'Metric', 'MWS')


def add(data, name, refs=None):
    return append_index(data, name, 'Test', 'Group', 'Test.rtp', '1D', 'legacy', refs or {})


def test_append_preserves_evaluated_rows_and_shared_task_references():
    first, refs = add(None, 'First', {'TaskName': r'Tasks\SP'})
    assert refs == {'TemplateTreeName/TaskName': '1'}
    first = first.replace(b'VBA\r\n0\r\n', b'VBA\r\n1\r\nFirst\r\n')
    result, refs = add(first, 'Second', {'Existing': r'Tasks\SP', 'New': r'Tasks\SP2'})
    assert refs == {'TemplateTreeName/Existing': '1', 'TemplateTreeName/New': '2'}
    assert b'VBA\r\n1\r\nFirst\r\nSecond\r\n' in result
    assert result.endswith(b'2\r\n1:Tasks\\SP\r\n2:Tasks\\SP2\r\n')
    with pytest.raises(ResultTemplateError, match='already exists'):
        add(result, 'FIRST')
    with pytest.raises(ResultTemplateError):
        add(first[:-12], 'Second')


@pytest.mark.parametrize('settings,context', [
    ({'NumberOfSamples': 1}, 'MWS'), ({'FormatG': 'xyz'}, 'MWS'),
    ({'ReferenceImpedance': 0}, 'MWS'), ({'LimitFreqRange': 1, 'FMin': 5, 'FMax': 2}, 'MWS'),
    ({'ReferenceImpedance': 50}, 'DS'), ({'TaskName': 'SP', 'FormatG': 'RI'}, 'DS'),
])
def test_rejects_invalid_touchstone_configuration(settings, context):
    with pytest.raises(ValueError):
        touchstone_settings(settings, context)


def test_settings_resource_contains_exact_installed_source_and_native_values():
    settings = touchstone_settings({'NumberOfSamples': 37, 'FormatG': 'RI'}, 'MWS')
    assert settings['FormatG'] == '1'
    data = settings_resource(b"' original macro\r\n", {'NumberOfSamples': '37', 'FormatG': '1'})
    assert data[:8] == struct.pack('<II', 3, 0)
    assert b'NumberOfSamples\0\x03\0\0\0' + b'37\0' in data
    assert data.endswith(b"' original macro\r\n\0")


def test_registration_lock_excludes_another_writer_and_releases_on_error(tmp_path):
    from cst_solver.postprocessing.builtin_templates import registration_lock
    project = tmp_path/'model.cst'
    with pytest.raises(ResultTemplateError):
        with registration_lock(project), registration_lock(project):
            pytest.fail('Concurrent registration entered')
    with registration_lock(project):
        pass
