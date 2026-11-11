from types import SimpleNamespace

import pytest


def fixture(monkeypatch, tmp_path):
    from cst_solver import run_status as mod
    path = tmp_path / 'case.cst'
    path.write_bytes(b'fixture')
    log = tmp_path / 'case' / 'Result' / 'Model.log'
    log.parent.mkdir(parents=True)
    log.write_text('Solver started\nDiagnostic only\n')
    monkeypatch.setattr(mod, 'process_identity', lambda pid: dict(pid=pid, creation_time='100', status='known'))
    monkeypatch.setattr(mod, 'list_dialogs', lambda **kw: [dict(pid=70, blocking=True, body='', text_complete=False)])
    calls = []
    def running(**kw):
        calls.append(kw)
        return True
    app = SimpleNamespace(project=SimpleNamespace(pid=70), cst_file=SimpleNamespace(
        filename=lambda: str(path), model3d=SimpleNamespace(is_solver_running=running)))
    params = dict(job_reader=lambda: dict(job_id='original', status='running'),
                  expected_pid=70, expected_creation_time='100', expected_project=str(path))
    return mod, app, params, calls


def test_running_with_unknown_prompt_is_not_progress_or_idle(monkeypatch, tmp_path):
    mod, app, params, calls = fixture(monkeypatch, tmp_path)
    result = mod.inspect_owned_run(app, **params)
    assert result['native_3d']['value'] is True
    assert result['waiting_for_prompt'] is True
    assert result['whole_sequence_idle'] == 'unknown'
    assert result['computational_progress'] == 'unknown'
    assert result['original_call_returned'] == 'unknown'
    assert result['log']['value']['complete_file'] is True
    assert calls == [{'timeout': 5}]


def test_changed_identity_refuses_before_native_getter(monkeypatch, tmp_path):
    mod, app, params, calls = fixture(monkeypatch, tmp_path)
    params['expected_creation_time'] = '200'
    with pytest.raises(ValueError, match='identity'):
        mod.inspect_owned_run(app, **params)
    assert not calls


def test_changed_project_refuses_before_native_getter(monkeypatch, tmp_path):
    mod, app, params, calls = fixture(monkeypatch, tmp_path)
    params['expected_project'] = str(tmp_path / 'other.cst')
    with pytest.raises(ValueError, match='project'):
        mod.inspect_owned_run(app, **params)
    assert not calls


def test_native_timeout_preserves_job_and_dialog_evidence(monkeypatch, tmp_path):
    mod, app, params, calls = fixture(monkeypatch, tmp_path)
    def fail(**kw):
        raise TimeoutError('fixture')
    app.cst_file.model3d.is_solver_running = fail
    result = mod.inspect_owned_run(app, **params)
    assert result['native_3d']['status'] == 'error'
    assert result['job_after']['value']['status'] == 'running'
    assert result['waiting_for_prompt'] is True


def test_job_replacement_is_not_a_consistent_observation(monkeypatch, tmp_path):
    mod, app, params, calls = fixture(monkeypatch, tmp_path)
    jobs = iter([dict(job_id='first'), dict(job_id='second')])
    params['job_reader'] = lambda: next(jobs)
    result = mod.inspect_owned_run(app, **params)
    assert result['identity_consistent'] is False


def test_observation_end_is_after_the_getter_returns(monkeypatch, tmp_path):
    mod, app, params, calls = fixture(monkeypatch, tmp_path)
    clock = [10.]
    monkeypatch.setattr(mod.time, 'time', lambda: clock[0])
    def running(**kw):
        clock[0] = 20.
        return False
    app.cst_file.model3d.is_solver_running = running
    result = mod.inspect_owned_run(app, **params)
    assert result['native_3d']['started_at'] == 10.
    assert result['native_3d']['finished_at'] == 20.
