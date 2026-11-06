"""Exercise real Windows replace contention in an isolated session directory."""

import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from tpc_service.sessions import store
from tpc_service.sessions.native import file_digest
from tpc_service.tests.test_session_project_discipline import fixture


pytestmark = pytest.mark.skipif(os.name != 'nt', reason='Windows rename sharing semantics')


def test_save_retries_only_the_receipt_when_reader_releases_it(tmp_path, monkeypatch):
    _, _, runtime, record = fixture(tmp_path)
    state_file = runtime.folder / 'session.json'
    before = state_file.read_bytes()
    save_calls, attempts, sleeps = [], [], []
    replace = os.replace

    def save(path, *, allow_overwrite):
        save_calls.append(path)
        Path(path).write_bytes(b'saved project bytes')

    def replace_once_prepared(source, target):
        assert Path(target) == state_file
        attempts.append((source, Path(source).read_bytes()))
        replace(source, target)

    with state_file.open('rb') as reader:
        def release_reader(delay):
            sleeps.append(delay)
            assert reader.read() == before
            reader.close()

        monkeypatch.setattr(store.os, 'replace', replace_once_prepared)
        monkeypatch.setattr(store.time, 'sleep', release_reader)
        saved = runtime.save(SimpleNamespace(save=save), 'main')

    assert save_calls == [record['path']]
    assert len(sleeps) == 1 and len(attempts) == 2 and attempts[0] == attempts[1]
    assert saved['saved_digest'] == file_digest(record['path'])
    assert store.read(state_file)['projects']['main']['saved_digest'] == saved['saved_digest']
    assert not list(runtime.folder.glob('session.json.*.tmp'))


def test_persistent_contention_raises_and_keeps_original_record(tmp_path, monkeypatch):
    target = tmp_path / 'job.json'
    store.write(target, {'status': 'running'})
    sleeps = []
    monkeypatch.setattr(store.time, 'sleep', sleeps.append)

    with target.open('rb'):
        with pytest.raises(PermissionError) as exc:
            store.write(target, {'status': 'succeeded'})

    assert exc.value.winerror in (5, 32)
    assert 1 <= len(sleeps) <= 6 and sum(sleeps) <= 1
    assert store.read(target) == {'status': 'running'}
    assert not list(tmp_path.glob('job.json.*.tmp'))


def test_unrelated_replace_error_is_not_retried(tmp_path, monkeypatch):
    target = tmp_path / 'job.json'
    store.write(target, {'status': 'running'})
    missing = FileNotFoundError(2, 'missing destination directory')

    def fail(source, target):
        raise missing

    monkeypatch.setattr(store.os, 'replace', fail)
    monkeypatch.setattr(store.time, 'sleep', lambda _: pytest.fail('non-sharing error was retried'))
    with pytest.raises(FileNotFoundError) as exc:
        store.write(target, {'status': 'succeeded'})
    assert exc.value is missing and store.read(target) == {'status': 'running'}
