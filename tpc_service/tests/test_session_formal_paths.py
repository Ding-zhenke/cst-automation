"""Exact-path authorization and formal-file adoption, with no native CST."""
from pathlib import Path
from types import SimpleNamespace

import pytest

from tpc_service.errors import ServiceError
from tpc_service.sessions import SessionManager
from tpc_service.sessions.native import Runtime, file_digest
from tpc_service.sessions.store import write


def make_session(tmp_path):
    manager = SessionManager(str(tmp_path / 'sessions'), backend='fake')
    manager._launch = lambda *a, **kw: None
    ref = manager.ensure('one', 'one')
    runtime = Runtime(manager.root / ref['session_id'], 'fake')
    return manager, ref, runtime


def submit(manager, ref, request, operation, **params):
    return manager.submit(ref['session_id'], ref['credential'], request, operation, params)


def test_create_uses_explicit_filename_and_keeps_identity(tmp_path):
    manager, ref, runtime = make_session(tmp_path)
    path = tmp_path / 'formal' / 'ReviewedDevice.cst'
    job = submit(manager, ref, 'new', 'create_project', project_id='device',
                 working_path=str(path), authorize_working_path=True)
    result = runtime.execute(job)
    assert result['project']['path'] == str(path.resolve())
    assert result['project']['project_id'] == 'device'
    assert manager.status(ref['session_id'], ref['credential'])['session_id'] == ref['session_id']
    assert path.is_file()


def test_explicit_path_requires_exact_authorization_before_queue(tmp_path):
    manager, ref, _ = make_session(tmp_path)
    with pytest.raises(ServiceError, match='authoriz'):
        submit(manager, ref, 'new', 'create_project', project_id='device',
               working_path=str(tmp_path / 'formal.cst'))


@pytest.mark.parametrize('paired', [False, True])
def test_create_rejects_existing_file_or_results_before_queue(tmp_path, paired):
    manager, ref, _ = make_session(tmp_path)
    path = tmp_path / 'formal.cst'
    if paired:
        path.with_suffix('').mkdir()
    else:
        path.write_text('delivery')
    with pytest.raises(ServiceError, match='exist'):
        submit(manager, ref, 'new', 'create_project', project_id='device',
               working_path=str(path), authorize_working_path=True)


def test_adopt_is_digest_checked_and_does_not_save(tmp_path):
    manager, ref, runtime = make_session(tmp_path)
    path = tmp_path / 'formal.cst'
    path.write_text('{"parameters":{},"history":[]}', encoding='utf-8')
    baseline = path.read_bytes()
    job = submit(manager, ref, 'adopt', 'adopt_project', project_id='device',
                 working_path=str(path), authorize_working_path=True,
                 expected_digest=file_digest(path), review_note='Continue reviewed formal baseline')
    runtime.save = lambda *a: pytest.fail('Adoption must not save')
    result = runtime.execute(job)
    assert result['adopted'] and not result['saved']
    assert path.read_bytes() == baseline
    assert result['project']['saved_digest'] == file_digest(path)
    assert result['project']['adoption_review']['review_note']


def test_second_session_cannot_claim_queued_destination(tmp_path):
    manager, ref, _ = make_session(tmp_path)
    path = tmp_path / 'formal.cst'
    submit(manager, ref, 'first', 'create_project', project_id='one',
           working_path=str(path), authorize_working_path=True)
    other = manager.ensure('two', 'two')
    with pytest.raises(ServiceError, match='claim|registered'):
        submit(manager, other, 'second', 'create_project', project_id='two',
               working_path=str(path), authorize_working_path=True)


def test_changed_adoption_baseline_rejected_before_open(tmp_path):
    manager, ref, runtime = make_session(tmp_path)
    path = tmp_path / 'formal.cst'
    path.write_text('{}')
    job = submit(manager, ref, 'adopt', 'adopt_project', project_id='device',
                 working_path=str(path), authorize_working_path=True,
                 expected_digest=file_digest(path), review_note='Reviewed')
    path.write_text('{"changed":true}')
    runtime.environment = lambda: pytest.fail('Changed baseline opened')
    with pytest.raises(ServiceError, match='digest|baseline'):
        runtime.execute(job)


def test_import_keeps_source_and_paired_resources(tmp_path):
    manager, ref, runtime = make_session(tmp_path)
    source = tmp_path / 'delivery.cst'
    source.write_text('{"parameters":{},"history":[]}')
    source.with_suffix('').mkdir()
    (source.with_suffix('') / 'dependency.txt').write_text('required')
    before = source.read_bytes()
    target = tmp_path / 'continued' / 'FormalName.cst'
    params = dict(project_id='device', source_path=str(source), working_path=str(target),
                  authorize_working_path=True)
    job = submit(manager, ref, 'import', 'import_project', **params)
    runtime.execute(job)
    assert target.is_file()
    assert (target.with_suffix('') / 'dependency.txt').read_text() == 'required'
    assert source.read_bytes() == before
    assert submit(manager, ref, 'import', 'import_project', **params)['job_id'] == job['job_id']


def test_registered_file_alias_cannot_be_adopted_by_another_session(tmp_path, monkeypatch):
    manager, ref, runtime = make_session(tmp_path)
    source = tmp_path / 'formal.cst'
    source.write_text('{"parameters":{},"history":[]}')
    params = dict(project_id='device', working_path=str(source), authorize_working_path=True,
                  expected_digest=file_digest(source), review_note='Reviewed')
    runtime.execute(submit(manager, ref, 'adopt', 'adopt_project', **params))
    alias = tmp_path / 'alias.cst'
    alias.write_bytes(source.read_bytes())
    # Model Windows same-file identity without requiring filesystem link privileges.
    original = Path.samefile
    monkeypatch.setattr(Path, 'samefile', lambda self, other:
                        True if {self, Path(other)} == {source, alias} else original(self, other))
    other = manager.ensure('other', 'other')
    with pytest.raises(ServiceError, match='registered|claim'):
        submit(manager, other, 'adopt', 'adopt_project', **dict(params, working_path=str(alias)))


@pytest.mark.parametrize('status,launch_intent', [('needs_reconcile', False), ('ready', True)])
def test_failed_adoption_keeps_claim_until_explicit_resolution(tmp_path, status, launch_intent):
    from tpc_service.sessions.worker import _finish_failed_job
    manager, ref, runtime = make_session(tmp_path)
    source = tmp_path / 'formal.cst'
    source.write_text('{"parameters":{},"history":[]}')
    params = dict(project_id='device', working_path=str(source), authorize_working_path=True,
                  expected_digest=file_digest(source), review_note='Reviewed')
    job = submit(manager, ref, 'adopt', 'adopt_project', **params)
    opened = []
    def open_then_fail(path):
        opened.append(path)
        raise RuntimeError('Native open returned no receipt')
    runtime.environment = lambda: SimpleNamespace(open=open_then_fail)
    with pytest.raises(RuntimeError, match='receipt'):
        runtime.execute(job)
    assert opened and not runtime.state()['projects']
    state = runtime.state()
    _finish_failed_job(job, {'code': 'session_operation_failed'}, state)
    state.update(status=status, launch_intent=launch_intent)
    write(runtime.folder / 'session.json', state)
    write(runtime.folder / 'jobs' / (job['job_id'] + '.json'), job)
    other = manager.ensure('other', 'other')
    with pytest.raises(ServiceError, match='claim|registered'):
        submit(manager, other, 'adopt', 'adopt_project', **params)
    # Explicit scene review resolves the failed journal before releasing the claim.
    runtime.update(status='needs_reconcile')
    manager.reconcile(ref['session_id'], ref['credential'], 'Confirmed failed open has no owned tab', {},
                      confirm_idle=True, confirm_no_environment=True)
    accepted = submit(manager, other, 'after-resolution', 'adopt_project', **params)
    assert accepted['status'] == 'queued'


@pytest.mark.parametrize('value', [None, 'bad\x00.cst'])
def test_malformed_explicit_working_path_is_service_error(tmp_path, value):
    manager, ref, _ = make_session(tmp_path)
    if isinstance(value, str):
        value = str(tmp_path / value)
    with pytest.raises(ServiceError) as caught:
        submit(manager, ref, 'bad', 'create_project', project_id='device',
               working_path=value, authorize_working_path=True)
    assert caught.value.code == 'invalid_session_argument'
