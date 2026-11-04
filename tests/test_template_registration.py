"""Versioned resource import tests. These do not certify native execution."""
import json
from types import SimpleNamespace

import pytest

from cst_automation.result_templates import ResultTemplateError
from cst_automation.template_registration import (
    prepare_python_result_registration, inspect_python_result_registration,
    check_registration_conflict, payload_digest,
)


@pytest.fixture
def registration(tmp_path):
    source = tmp_path / 'source.rtpy'
    source.write_text('raise RuntimeError("must not import")\ndef define(settings): pass\ndef evaluate(settings): pass\n')
    kwargs = dict(result_name='Metric', template_name='Calculation', group='Example',
                  result_type='M0D', settings={'hb_task': 'Sweep\\HB', 'nested': [False, 1.5, None]})
    payload = prepare_python_result_registration(source, **kwargs)
    folder = tmp_path / 'resources'; folder.mkdir()
    return source, kwargs, payload, folder


def write_registration(payload, folder):
    for name, content in payload.items(): (folder / name).write_bytes(content)


def test_complete_registration_roundtrip_retains_exact_settings_and_bytes(registration):
    source, kwargs, payload, folder = registration
    write_registration(payload, folder)
    report = inspect_python_result_registration(folder)
    assert report['settings'] == kwargs['settings']
    assert report['registration_sha256'] == payload_digest(payload)[0]
    assert report['native_template_enumeration_verified'] is False
    assert report['template_execution_verified'] is False
    assert report['eval_type'] is None and report['eval_type_status'] == 'not_independently_decoded'
    assert report['raw_evaluation_flags'] == {'flag': 'P', 'layout': 'EP10'}
    assert (folder / 'Metric.rtpy').read_bytes() == source.read_bytes()


def test_conflicts_require_digest_of_all_registration_resources(registration):
    source, kwargs, payload, folder = registration
    assert check_registration_conflict(folder, payload) is None
    write_registration(payload, folder)
    with pytest.raises(ResultTemplateError, match='already exists'):
        check_registration_conflict(folder, payload)
    before = inspect_python_result_registration(folder)
    assert check_registration_conflict(folder, payload, conflict='replace',
        expected_registration_sha256=before['registration_sha256']) == before
    meta = folder / 'Metric.rtjson'
    data = json.loads(meta.read_text()); data['template']['settings']['hb_task'] = 'Changed\\HB'
    meta.write_text(json.dumps(data))
    with pytest.raises(ResultTemplateError, match='SHA-256 mismatch'):
        check_registration_conflict(folder, payload, conflict='replace',
            expected_registration_sha256=before['registration_sha256'])


@pytest.mark.parametrize('mutation', ['multiple', 'wrong_type', 'external_source', 'missing_source'])
def test_refuses_unsupported_or_incomplete_registration(registration, mutation):
    source, kwargs, payload, folder = registration
    write_registration(payload, folder)
    if mutation in ('multiple', 'wrong_type'):
        summary = folder / 'Summary.rpp'; lines = summary.read_text().splitlines()
        if mutation == 'multiple': lines[3] = '2'
        else: lines[7] = 'Unsupported'
        summary.write_text('\n'.join(lines) + '\n')
    elif mutation == 'external_source':
        meta = folder / 'Metric.rtjson'; data = json.loads(meta.read_text())
        data['template']['python_module']['path'] = '../source.rtpy'; meta.write_text(json.dumps(data))
    else: (folder / 'Metric.rtpy').unlink()
    with pytest.raises(ResultTemplateError): inspect_python_result_registration(folder)


@pytest.mark.parametrize('change', [dict(result_name='../escape'), dict(group='CON'),
    dict(settings={'bad': float('nan')}), dict(settings={1: 'bad'}), dict(settings={'bad': object()}),
    dict(result_type='unknown'), dict(eval_type='all_runs')])
def test_invalid_payload_is_rejected_without_creating_resources(registration, change):
    source, kwargs, payload, folder = registration
    with pytest.raises(ResultTemplateError): prepare_python_result_registration(source, **dict(kwargs, **change))
    assert not list(folder.iterdir())


def test_incompatible_literal_source_eval_type_is_rejected_without_execution(registration):
    source, kwargs, payload, folder = registration
    source.write_text('def define(settings):\n    return TemplateSettings(result_type="M0D", eval_type="all_runs")\ndef evaluate(settings): pass\n')
    with pytest.raises(ResultTemplateError, match='eval_type differs'):
        prepare_python_result_registration(source, **kwargs)
    assert not list(folder.iterdir())


def test_invalid_source_is_rejected_before_app_access(registration):
    from cst_solver.circuit.api import CircuitAPI
    source, kwargs, payload, folder = registration
    source.write_text('this is invalid syntax!')
    with pytest.raises(ResultTemplateError):
        CircuitAPI(SimpleNamespace()).register_python_result_template(
            'Sweep', 'Sweep\\HB', 'Sweep\\Post', source, **kwargs)


@pytest.mark.parametrize('restore', ['exact', 'missing', 'changed'])
def test_verification_requires_native_archive_reconstruction_not_existing_files(registration, monkeypatch, restore):
    from cst_solver.circuit import template_registration as native
    from cst_solver.circuit.adapter import CircuitError
    from cst_automation.template_registration import SUPPORTED_NATIVE_VERSION
    source, kwargs, payload, unused = registration
    path = source.parent / 'project.cst'; path.write_bytes(b'fake native archive')
    resources = path.with_suffix(''); folder = resources / 'Model/DS/NativePost'
    folder.mkdir(parents=True)
    events = []
    task = SimpleNamespace(Reset=lambda: None, Name=lambda name: None, DoesExist=lambda: True)
    schematic = SimpleNamespace(GetApplicationVersion=lambda: SUPPORTED_NATIVE_VERSION,
                                GetActivePostprocessingTask=lambda: '', SimulationTask=task)
    def close():
        events.append('close'); app.opened = False
    def handle():
        return SimpleNamespace(filename=lambda: str(path), folder=lambda: str(resources),
                               schematic=schematic, close=close)
    def save(*args, **kwargs):
        events.append('save'); app.archive = {f.name: f.read_bytes() for f in folder.iterdir()}
    def reopen(value):
        # The original directory must have been moved outside the companion root.
        assert not folder.exists()
        events.append('reopen'); app.opened = True; app.cst_file = handle()
        if restore != 'missing':
            folder.mkdir(parents=True)
            write_registration(app.archive, folder)
            if restore == 'changed':
                meta = folder / 'Metric.rtjson'; data = json.loads(meta.read_text())
                data['template']['settings']['hb_task'] = 'Unexpected'
                meta.write_text(json.dumps(data))
    app = SimpleNamespace(opened=True, cst_file=handle(), save=save, open=reopen)
    app.project = SimpleNamespace(list_open_projects=lambda: [str(path)] if app.opened else [])
    monkeypatch.setattr(native, '_task', lambda *a, **kw: task)
    monkeypatch.setattr(native, 'registration_folder', lambda *a: folder)
    monkeypatch.setattr(native, 'configure_hb_postprocessing_chain', lambda *a, **kw: events.append('configure'))
    monkeypatch.setattr(native, 'inspect_hb_postprocessing_chain', lambda *a: {'readback_verified': True})
    if restore == 'exact':
        report = native.register_python_result_template(app, 'Sweep', 'Sweep\\HB', 'Sweep\\Post', source, **kwargs)
        assert report['registration_persistence_verified'] and report['reopen_verified']
        assert report['binding_verified'] is report['template_execution_verified'] is False
    else:
        with pytest.raises(CircuitError) as exc:
            native.register_python_result_template(app, 'Sweep', 'Sweep\\HB', 'Sweep\\Post', source, **kwargs)
        report = exc.value.details['registration_receipt']
        assert report['stage'] == 'native_reopen_and_extract'
        assert report['registration_persistence_verified'] is False
    assert events == ['configure', 'save', 'close', 'reopen']
    assert list(path.parent.glob('.cst_automation_template_audits/*/saved_resources/Summary.rpp'))


@pytest.mark.parametrize('partial', [False, True])
def test_session_route_refreshes_handle_after_reopen_even_on_partial_failure(registration, partial):
    from tpc_service.sessions.operations import circuit
    from cst_solver.circuit.adapter import CircuitError
    from tpc_service.errors import ServiceError
    source, kwargs, payload, folder = registration
    record = {'project_id': 'own-project', 'path': str(source.parent / 'model.cst')}
    source.with_name('model.cst').write_bytes(b'fixture')
    old_handle, reopened_handle = object(), object()
    app = SimpleNamespace(cst_file=old_handle)
    def register(*args, **kwargs):
        app.cst_file = reopened_handle
        if partial:
            raise CircuitError('circuit_build_partial', 'readback mismatch', stage='native_reopen_and_extract')
        return {'saved': True, 'audit_path': str(source.parent / 'receipt.json')}
    app.circuit = SimpleNamespace(register_python_result_template=register)
    state = {'projects': {'own-project': record}}
    runtime = SimpleNamespace(folder=source.parent, handles={'own-project': old_handle},
                              state=lambda: state, update=lambda **values: state.update(values))
    params = {'kind': 'build', 'settings': dict(kwargs, operation='register_postprocessing_template',
        parent_task='Sweep', hb_task='Sweep\\HB', post_task='Sweep\\Post', template_source=str(source))}
    if partial:
        with pytest.raises(ServiceError): circuit(runtime, app, record, params)
    else:
        assert circuit(runtime, app, record, params)['ok']
    assert runtime.handles['own-project'] is reopened_handle
