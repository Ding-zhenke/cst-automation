import hashlib
import json
from types import SimpleNamespace

import pytest

from cst_solver.mesh.mesh import normalize_tetrahedral_mesh_settings
from tpc_service.errors import ServiceError
from tpc_service.sessions.model_api import dispatch


def batch(settings, keyword):
    return [{'method': 'new_component', 'args': ['never']},
            {'method': 'configure_tetrahedral_mesh',
             **({'kwargs': {'settings': settings}} if keyword else {'args': [settings]})}]


@pytest.mark.parametrize('adaptation', [
    {'min_passes': 1}, {'max_passes': 1}, {'min_passes': 1, 'max_passes': 1},
    {'enabled': False, 'min_passes': 1}, {'min_passes': True},
    {'min_passes': 2.0}, {'min_passes': '2'}, {'min_passes': 3, 'max_passes': 2},
])
@pytest.mark.parametrize('keyword', [False, True])
def test_invalid_limits_reject_whole_batch_before_writes(adaptation, keyword):
    app = SimpleNamespace(new_component=lambda *a: pytest.fail('Earlier native write'))
    with pytest.raises(ServiceError):
        dispatch(app, batch({'adaptation': adaptation}, keyword))


@pytest.mark.parametrize('key', ['min_passes', 'max_passes'])
def test_invalid_limits_reject_mcp_before_queue_or_launch(tmp_path, monkeypatch, key):
    from cst_mcp import tools
    from cst_mcp.session_tools import register_session_tools
    from tpc_service.sessions import SessionManager
    for name in ('TOOL_SPECS', 'HANDLERS', 'READ_TOOLS', 'WRITE_TOOLS'):
        monkeypatch.setattr(tools, name, getattr(tools, name).copy())
    monkeypatch.setattr(SessionManager, '_launch', lambda *a, **k: pytest.fail('Worker launch'))
    register_session_tools(str(tmp_path.resolve()), backend='fake')
    ref = tools.dispatch('ensure_cst_session', {'binding': 'passes', 'request_id': 'e'})['session']
    calls = batch({'adaptation': {key: 1}}, True)
    params = dict(project_id='p', stage_id='passes', calls=calls,
                  preview_digest=hashlib.sha256(json.dumps(calls, sort_keys=True, ensure_ascii=False).encode()).hexdigest())
    out = tools.dispatch('submit_cst_session_operation', dict(session_id=ref['session_id'],
        credential=ref['credential'], request_id='passes', operation='model_api', params=params))
    assert out['ok'] is False
    assert not list((tmp_path / ref['session_id'] / 'jobs').glob('*.json'))


def test_execution_rejects_before_project_access(tmp_path):
    from tpc_service.sessions.operations import execute
    runtime = SimpleNamespace(folder=tmp_path, backend='cst',
                              project=lambda *a: pytest.fail('Native project access'))
    job = {'operation': 'model_api', 'params': {'project_id': 'p',
           'calls': batch({'adaptation': {'min_passes': 1}}, False)}}
    with pytest.raises(ServiceError):
        execute(runtime, job)
    assert job['workflow_preflight_rejected'] is True


@pytest.mark.parametrize('adaptation', [
    {'min_passes': 2, 'max_passes': 2, 'delta_s_checks': 1},
    {'max_passes': 2}, {'enabled': False},
])
def test_valid_boundary_and_sparse_controls_preserved(adaptation):
    assert normalize_tetrahedral_mesh_settings({'adaptation': adaptation}) == {'adaptation': adaptation}
