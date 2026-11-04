"""Run-contract evidence must survive backend, service storage and MCP queries."""
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from cst_mcp import runtime, tools
from cst_solver.run_contract import RunContract
from tpc_service.backends.cst_backend import CstBackend


@pytest.mark.parametrize('state', ['not_read', 'read', 'read_failed'])
def test_observation_survives_backend_service_storage_and_mcp(tmp_path, monkeypatch, state):
    values = iter([{'items': [['x', 1, 1]]}, {'items': [['x', 2, 2]]}])
    sink = SimpleNamespace(write=lambda result: 'offline-jsonl')
    contract = RunContract('offline.cst', probe=lambda path: next(values), sink=sink)
    reader = (None if state == 'not_read' else Mock(return_value=[])
              if state == 'read' else Mock(side_effect=OSError('reader failed')))
    outcome = contract.run_and_record(lambda: None, read_messages=reader,
                                      message_source='sdk_pending_queue')
    app = SimpleNamespace(project=None, run_checked=Mock(return_value=outcome),
                           save=Mock(), close=Mock())
    import cst_solver
    monkeypatch.setattr(cst_solver, 'setup', Mock(return_value=app))
    backend = CstBackend()
    backend.dialog_monitoring = False  # this test must not enumerate desktop windows
    path = tmp_path / 'fake.cst'
    path.write_text('offline fixture')
    runtime.reset()
    runtime.configure(workdir=str(tmp_path / 'work'), backend=backend)
    service = runtime.get_service()
    try:
        job = service.submit('solve', project_path=str(path), copy=False)
        done = service.wait(job['job_id'], timeout=3)
        expected_status = 'succeeded' if state == 'read' else 'failed'
        assert done['status'] == expected_status
        for record in [done, service.store.load(job['job_id']).to_dict(),
                       tools.dispatch('get_job_status', {'job_id': job['job_id']})['job']]:
            evidence = record['result_summary']['run_contract']
            assert evidence['messages_state'] == state
            assert evidence['messages_clean'] is (True if state == 'read' else None)
            assert evidence['message_source'] == 'sdk_pending_queue'
            assert evidence['native_warnings'] is None and evidence['mesh_convergence'] == 'unknown'
        payload = tools.dispatch('get_results', {'job_id': job['job_id']})
        if state == 'read':
            assert payload['result_summary']['run_contract']['messages_clean'] is True
            app.save.assert_called_once()
        else:
            assert payload['ok'] is False
            evidence = payload['error']['details']['job_error']['details']['run_contract']
            assert evidence['messages_state'] == state and evidence['messages_clean'] is None
            app.save.assert_not_called()
    finally:
        service.shutdown(wait=True, timeout=3)
        runtime.reset()
    app.close.assert_called_once()


def test_save_failure_preserves_observed_run_contract(tmp_path, monkeypatch):
    outcome = {'status': 'succeeded', 'run_token': 'offline-token', 'messages': [],
               'messages_state': 'read', 'messages_read': True, 'messages_clean': True,
               'message_source': 'sdk_pending_queue', 'native_warnings': None}
    app = SimpleNamespace(project=None, run_checked=Mock(return_value=outcome),
                           save=Mock(side_effect=OSError('save failed')), close=Mock())
    import cst_solver
    monkeypatch.setattr(cst_solver, 'setup', Mock(return_value=app))
    path = tmp_path / 'fake.cst'
    path.write_text('offline fixture')
    result = CstBackend().solve(project={'path': str(path)}, params={}, job={})
    assert result['ok'] is False and result['saved'] is False
    assert result['result_summary']['run_contract'] == outcome
    assert result['error']['details']['run_contract'] == outcome
    assert result['run_identity']['run_token'] == 'offline-token'
    app.close.assert_called_once()
