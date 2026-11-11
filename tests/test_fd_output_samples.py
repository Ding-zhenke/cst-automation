"""Reject invalid display samples before any earlier batch operation or launch."""
import hashlib
import json
from types import SimpleNamespace

import pytest

from cst_solver.simulation.frequency import configure_fd_frequency
from tpc_service.errors import ServiceError
from tpc_service.sessions.model_api import dispatch


def calls_for(value, keyword):
    settings = {'output_samples': value}
    return [{'method': 'new_component', 'args': ['never']},
            {'method': 'configure_fd_frequency',
             **({'kwargs': {'settings': settings}} if keyword else {'args': [settings]})}]


@pytest.mark.parametrize('value', [2, 1, 0, -1, True, 3.0, '3', None, 2147483648])
@pytest.mark.parametrize('keyword', [False, True])
def test_invalid_samples_reject_before_earlier_batch_write(value, keyword):
    app = SimpleNamespace(new_component=lambda *a: pytest.fail('Earlier native write'))
    with pytest.raises(ServiceError):
        dispatch(app, calls_for(value, keyword))


@pytest.mark.parametrize('keyword', [False, True])
def test_mcp_rejects_two_samples_before_queue_or_worker(tmp_path, monkeypatch, keyword):
    from cst_mcp import tools
    from cst_mcp.session_tools import register_session_tools
    from tpc_service.sessions import SessionManager
    for name in ('TOOL_SPECS', 'HANDLERS', 'READ_TOOLS', 'WRITE_TOOLS'):
        monkeypatch.setattr(tools, name, getattr(tools, name).copy())
    monkeypatch.setattr(SessionManager, '_launch', lambda *a, **k: pytest.fail('Worker launch'))
    register_session_tools(str(tmp_path.resolve()), backend='fake')
    ref = tools.dispatch('ensure_cst_session', {'binding': 'samples', 'request_id': 'e'})['session']
    calls = calls_for(2, keyword)
    params = dict(project_id='p', stage_id='samples', calls=calls,
        preview_digest=hashlib.sha256(json.dumps(calls, sort_keys=True, ensure_ascii=False).encode()).hexdigest())
    out = tools.dispatch('submit_cst_session_operation', dict(session_id=ref['session_id'],
        credential=ref['credential'], request_id='samples', operation='model_api', params=params))
    assert out['ok'] is False
    assert not list((tmp_path / ref['session_id'] / 'jobs').glob('*.json'))


def test_execution_rejects_two_samples_before_project_access(tmp_path):
    from tpc_service.sessions.operations import execute
    runtime = SimpleNamespace(folder=tmp_path, backend='cst',
        project=lambda *a: pytest.fail('Native project access'))
    job = {'operation': 'model_api', 'params': {'project_id': 'p', 'calls': calls_for(2, True)}}
    with pytest.raises(ServiceError):
        execute(runtime, job)
    assert job['workflow_preflight_rejected'] is True


@pytest.mark.parametrize('samples', [3, 2147483647])
def test_valid_display_boundary_preserves_two_solve_points(samples):
    history = []
    app = SimpleNamespace(cst_file=SimpleNamespace(model3d=SimpleNamespace(
        add_to_history=lambda *a: history.append(a))))
    report = configure_fd_frequency(app, {'output_samples': samples, 'sampling_intervals': [
        {'start': f, 'stop': f, 'spacing': 'single', 'samples': 1} for f in (.0001, 140)]})
    assert history[0][1].splitlines() == [
        'FDSolver.AddSampleInterval "0.0001", "0.0001", "1", "Single", False',
        'FDSolver.AddSampleInterval "140", "140", "1", "Single", False',
        f'FDSolver.SetNumberOfResultDataSamples "{samples}"']
    assert report['readback_verified'] is False
