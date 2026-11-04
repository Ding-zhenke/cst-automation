"""Regression cases for duplicate process models and abandoned check tabs."""
from types import SimpleNamespace

import pytest

from tpc_service.errors import ServiceError
from tpc_service.sessions import SessionManager
from tpc_service.sessions.native import Runtime, file_digest


def fixture(tmp_path):
    manager = SessionManager(str(tmp_path.resolve()), backend='fake')
    binding = manager.ensure('test', 'test')
    manager._launch = lambda *a, **kw: None
    runtime = Runtime(tmp_path / binding['session_id'], 'fake')
    path = runtime.folder / 'projects' / 'main' / 'model.cst'
    path.parent.mkdir(parents=True)
    path.write_text('{"parameters":{},"history":[]}', encoding='utf-8')
    record = dict(project_id='main', path=str(path), saved=True, saved_digest=file_digest(path))
    runtime.update(projects={'main': record})
    return manager, binding, runtime, record


def job(operation, **params):
    return dict(job_id='j', operation_id='stage', fingerprint='f', operation=operation, params=params)


def test_duplicate_project_rejected_before_queue_or_worker(tmp_path):
    manager, binding, runtime, record = fixture(tmp_path)
    for operation, params in [('create_project', {'project_id': 'main'}),
                              ('import_project', {'project_id': 'copy', 'source_path': record['path']})]:
        with pytest.raises(ServiceError, match='registered|Reuse'):
            manager.submit(binding['session_id'], binding['credential'], operation, operation, params)
    assert not list((runtime.folder / 'jobs').glob('*.json'))


def test_queued_source_intent_cannot_be_duplicated(tmp_path):
    manager, binding, runtime, record = fixture(tmp_path)
    source = tmp_path / 'baseline.cst'
    source.write_text('{}')
    manager.submit(binding['session_id'], binding['credential'], 'one', 'import_project',
                   dict(project_id='one', source_path=str(source)))
    with pytest.raises(ServiceError, match='Reuse'):
        manager.submit(binding['session_id'], binding['credential'], 'two', 'import_project',
                       dict(project_id='two', source_path=str(source)))
    manager.submit(binding['session_id'], binding['credential'], 'reference', 'import_project',
                   dict(project_id='reference', source_path=str(source), copy_reason='Independent bare reference'))


def test_close_tab_saves_first_keeps_de_and_is_idempotent(tmp_path):
    _, _, runtime, record = fixture(tmp_path)
    seen = []
    app = SimpleNamespace(cst_file=SimpleNamespace(close=lambda: seen.append('tab-close')),
                          project=SimpleNamespace(close=lambda: pytest.fail('DE closed'), list_open_projects=lambda: []))
    runtime.backend = 'cst'
    runtime.project = lambda project_id: (app, record)
    def save(app, project_id):
        seen.append('save')
        return record
    runtime.save = save
    result = runtime.execute(job('close_project', project_id='main'))
    assert seen == ['save', 'tab-close']
    assert result['tab_closed'] and result['environment_closed'] is False
    assert runtime.state()['projects']['main']['tab_closed']
    runtime.project = lambda *_: pytest.fail('Reopened closed tab')
    again = runtime.execute(job('close_project', project_id='main'))
    assert again['already_closed'] and not again['retired']


def test_failed_tab_close_keeps_record_and_handle(tmp_path):
    _, _, runtime, record = fixture(tmp_path)
    def fail():
        raise RuntimeError('native close failed')
    app = SimpleNamespace(cst_file=SimpleNamespace(close=fail))
    runtime.backend = 'cst'
    runtime.project = lambda *_: (app, record)
    runtime.save = lambda *_: record
    runtime.handles['main'] = app.cst_file
    with pytest.raises(RuntimeError, match='close failed'):
        runtime.execute(job('close_project', project_id='main'))
    assert not runtime.state()['projects']['main'].get('tab_closed')
    assert runtime.handles['main'] is app.cst_file


def test_noop_native_close_does_not_claim_closed(tmp_path):
    _, _, runtime, record = fixture(tmp_path)
    app = SimpleNamespace(cst_file=SimpleNamespace(close=lambda: None),
                          project=SimpleNamespace(list_open_projects=lambda: [record['path']]))
    runtime.backend = 'cst'
    runtime.project = lambda *_: (app, record)
    runtime.save = lambda *_: record
    with pytest.raises(ServiceError, match='still open'):
        runtime.execute(job('close_project', project_id='main'))
    assert not runtime.state()['projects']['main'].get('tab_closed')


def test_temporary_close_retires_binding_before_file_cleanup(tmp_path):
    manager, binding, runtime, record = fixture(tmp_path)
    record['lifetime'] = 'temporary'
    runtime.update(projects={'main': record})
    result = runtime.execute(job('close_project', project_id='main'))
    assert result['retired'] is True
    state = runtime.state()
    assert 'main' not in state['projects']
    assert state['retired_projects']['main']['saved_digest']
    again = runtime.execute(job('close_project', project_id='main'))
    assert again['already_closed'] and again['retired']
    from pathlib import Path
    Path(record['path']).unlink()
    runtime.update(status='needs_reconcile')
    manager.reconcile(binding['session_id'], binding['credential'], 'offline test', {}, confirm_idle=True)


def test_project_reuses_existing_native_tab_after_handle_loss(tmp_path):
    _, _, runtime, record = fixture(tmp_path)
    tab = SimpleNamespace(activate=lambda: None)
    app = SimpleNamespace(project=SimpleNamespace(list_open_projects=lambda: [record['path']],
                         get_open_project=lambda path: tab),
                         open=lambda *_: pytest.fail('Opened a duplicate tab'))
    runtime.backend = 'cst'
    runtime.environment = lambda: app
    assert runtime.project('main')[0].cst_file is tab


def test_inspection_is_outside_history_rebuild_and_save(tmp_path):
    _, _, runtime, record = fixture(tmp_path)
    solid = SimpleNamespace(GetNumberOfShapes=lambda: 1, GetNameOfShapeFromIndex=lambda index: 'c:s',
                            DoesExist=lambda name: True, GetMaterialNameForShape=lambda name: 'PEC',
                            GetVolume=lambda name: 2.5, IsPointInsideShape=lambda x,y,z,name: x == 0)
    model = SimpleNamespace(Solid=solid, GetNumberOfParameters=lambda: 1,
                            GetParameterName=lambda index: 'a', RestoreParameterExpression=lambda name: '2+3')
    app = SimpleNamespace(cst_file=SimpleNamespace(model3d=model), get_messages=lambda: [],
                          get_parameter=lambda name: 5)
    runtime.backend = 'cst'
    runtime.project = lambda *_: (app, record)
    runtime.save = lambda *_: pytest.fail('Inspection saved the model')
    result = runtime.execute(job('inspect', project_id='main', native_readback=True,
                         sample_points=[dict(id='inside', solid='c:s', point=[0, 1, 2])]))
    assert result['readback_verified'] is True
    assert result['native_readback']['parameters']['a'] == dict(value=5, expression='2+3')
    assert result['native_readback']['solids']['c:s']['volume'] == 2.5
    assert result['native_readback']['sample_points'][0]['inside'] is True
    solid.GetVolume = lambda name: (_ for _ in ()).throw(RuntimeError('query failed'))
    result = runtime.execute(job('inspect', project_id='main', native_readback=True))
    assert not result['readback_verified'] and result['native_readback']['errors']


@pytest.mark.parametrize('options', [dict(native_readback='yes'), dict(captures=[]),
    dict(native_readback=True, sample_points=[dict(id='x', solid='s', point=[0, float('nan'), 1])])])
def test_invalid_inspection_options_rejected_before_queue(tmp_path, options):
    manager, binding, runtime, _ = fixture(tmp_path)
    with pytest.raises(ServiceError):
        manager.submit(binding['session_id'], binding['credential'], 'inspect', 'inspect',
                       dict(project_id='main', **options))
    assert not list((runtime.folder / 'jobs').glob('*.json'))


def test_audit_file_writes_cannot_be_added_to_replay_history(tmp_path):
    import hashlib
    manager, binding, runtime, _ = fixture(tmp_path)
    code = 'Open GetProjectPathName("Project") & "\\audit.csv" For Output As #1\nPrint #1, "volume"\nClose #1'
    with pytest.raises(ServiceError, match='inspect|history'):
        manager.submit(binding['session_id'], binding['credential'], 'audit', 'history',
                       dict(project_id='main', stage_id='audit', name='audit', vba=code,
                            preview_digest=hashlib.sha256(code.encode()).hexdigest()))
    assert not list((runtime.folder / 'jobs').glob('*.json'))


def test_worker_scan_stage_retry_and_temporary_retirement(tmp_path):
    import time
    manager = SessionManager(str(tmp_path.resolve()), backend='fake')
    binding = manager.ensure('worker-test', 'worker-test')
    def submit(request, operation, **params):
        accepted = manager.submit(binding['session_id'], binding['credential'], request, operation, params)
        end = time.monotonic() + 15
        while time.monotonic() < end:
            result = manager.job(binding['session_id'], binding['credential'], accepted['job_id'])
            if result['status'] not in ('queued', 'running'):
                assert result['status'] == 'succeeded', result
                return result
            time.sleep(.05)
        pytest.fail('Worker did not finish')
    try:
        submit('new', 'create_project', project_id='check', lifetime='temporary')
        sweep = dict(project_id='check', stage_id='scan', sequence_name='scan', parameters={'x': [0, 1]}, replace_all=True)
        first = submit('scan-1', 'configure_sweep', **sweep)
        assert submit('scan-retry', 'configure_sweep', **sweep)['job_id'] == first['job_id']
        result = submit('read', 'inspect', project_id='check', native_readback=True)
        assert not result['result']['readback_verified']
        assert result['result']['offline_model']['sweep']['parameters'] == {'x': [0, 1]}
        assert submit('close-tab', 'close_project', project_id='check')['result']['retired']
        assert manager.status(binding['session_id'], binding['credential'])['projects'] == {}
    finally:
        submit('close', 'close')
