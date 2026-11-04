"""Known circuit returns remain unverified without fencing an otherwise ready session."""
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
import hashlib

import pytest

from cst_solver.circuit.run import run_checked
from tpc_service.errors import ServiceError
from tpc_service.sessions.operations import circuit
from tpc_service.sessions.worker import _finish_failed_job


def setup_case(tmp_path, *, failure=None, reuse='never'):
    path = tmp_path/'synthetic.cst'; path.write_bytes(b'original')
    def update(task):
        if failure == 'update': raise RuntimeError('interrupted call')
    def save():
        if failure == 'save': raise OSError('save interrupted')
        path.write_bytes(b'known saved result')
    def proof(task, token):
        if failure == 'proof': raise OSError('log unavailable')
        return {'completed': False, 'log_changed': False, 'log_evidence_state': 'no_new_log_evidence'}
    dependencies = lambda: {'files': [], 'unknown': [], 'complete': True}
    app = SimpleNamespace(cst_file=SimpleNamespace(filename=lambda: str(path)), save=save,
                          get_messages=lambda: [], close=Mock())
    api = SimpleNamespace(app=app, adapter=SimpleNamespace(update_task=update, execution_evidence=proof),
        validate=lambda **kw: {'ok': True, 'task': {'type': 'network', 'properties': {}},
                               'dependencies': dependencies()}, inspect_dependencies=dependencies)
    api.run_checked = lambda *a, **kw: run_checked(api, *a, **kw)
    app.circuit = api
    record = {'project_id': 'p', 'path': str(path), 'saved': True,
              'saved_digest': hashlib.sha256(path.read_bytes()).hexdigest()}
    state = {'projects': {'p': record}, 'status': 'ready', 'uncertain_jobs': [], 'launch_intent': False}
    runtime = SimpleNamespace(folder=tmp_path, state=lambda: state, update=lambda **kw: state.update(kw))
    params = {'project_id': 'p', 'kind': 'solve', 'settings': {'operation': 'run_task', 'task_name': 'Leaf',
        'mode': 'network', 'reuse': reuse, 'expected_results': [{'tree_path': 'Tasks\\Leaf\\V', 'run_id': 1}]}}
    job = {'operation': 'circuit', 'params': params, 'job_id': 'synthetic'}
    return runtime, app, record, state, job


def route_failure(case):
    runtime, app, record, state, job = case
    with pytest.raises(ServiceError) as caught:
        circuit(runtime, app, record, job['params'])
    return caught.value.to_dict()


def test_returned_saved_leaf_stays_failed_unverified_and_session_ready(tmp_path):
    case = setup_case(tmp_path)
    error = route_failure(case)
    runtime, app, record, state, job = case
    _finish_failed_job(job, error, state)
    assert state['status'] == 'ready'
    assert job['status'] == 'failed'
    assert job['result']['execution_state'] == 'returned_saved'
    assert job['result']['review_required'] is True
    assert job['result']['solver_outcome']['status'] == 'unverified'
    assert job['result']['solver_outcome']['execution_evidence']['log_evidence_state'] == 'no_new_log_evidence'
    assert job['error'] == state['last_error'] == error
    assert job['result']['circuit_outcome'] == error['details']['outcome']
    app.close.assert_not_called()


def test_raw_return_receipt_is_saved_before_postprocessing(tmp_path):
    case = setup_case(tmp_path, failure='proof')
    error = route_failure(case)
    outcome = error['details']['outcome']['result_summary']['circuit_outcome']
    assert outcome['submitted'] is outcome['execution_returned'] is outcome['saved'] is True
    assert outcome['project'] == case[2]['path']
    assert outcome['saved_digest'] == hashlib.sha256(Path(outcome['project']).read_bytes()).hexdigest()
    import json
    audit = json.loads(Path(outcome['audit_path']).read_text(encoding='utf-8'))
    assert audit['execution_returned'] is audit['saved'] is True
    assert audit['saved_digest'] == outcome['saved_digest']
    _finish_failed_job(case[4], error, case[3])
    assert case[3]['status'] == 'ready'
    assert case[4]['result']['solver_outcome']['status'] == 'failed'


@pytest.mark.parametrize('failure,reuse', [('update','never'), ('save','never'), (None,'verified')])
def test_missing_return_or_save_cannot_release_session(tmp_path, failure, reuse):
    case = setup_case(tmp_path, failure=failure, reuse=reuse)
    error = route_failure(case)
    _finish_failed_job(case[4], error, case[3])
    assert case[3]['status'] == 'needs_reconcile'
    assert not case[4].get('result')


@pytest.mark.parametrize('change', ['digest', 'disk', 'project', 'return', 'submission', 'saved',
    'missing_receipt', 'prior_fence', 'uncertain', 'launch', 'dialog', 'other_operation', 'sequence',
    'task', 'mode', 'run_token'])
def test_saved_circuit_receipt_cannot_override_unknown_or_foreign_work(tmp_path, change):
    case = setup_case(tmp_path); error = route_failure(case)
    runtime, app, record, state, job = case
    receipt = error['details'].get('execution_receipt', {})
    monitor = None
    if change == 'digest': receipt['saved_digest'] = '0'*64
    if change == 'disk': Path(record['path']).write_bytes(b'changed afterwards')
    if change == 'project': receipt['project'] = str(tmp_path/'foreign.cst')
    if change == 'return': receipt['execution_returned'] = False
    if change == 'submission': receipt['submitted'] = False
    if change == 'saved': receipt['saved'] = False
    if change == 'missing_receipt': error['details'].pop('execution_receipt', None)
    if change == 'prior_fence': state['status'] = 'needs_reconcile'
    if change == 'uncertain': state['uncertain_jobs'] = ['previous']
    if change == 'launch': state['launch_intent'] = True
    if change == 'dialog': monitor = {'state': 'unknown'}
    if change == 'other_operation': job['operation'] = 'history'
    if change == 'sequence': job['params']['settings']['operation'] = 'parameter_sequence'
    if change == 'task': receipt['task_name'] = 'AnotherLeaf'
    if change == 'mode': receipt['mode'] = 'transient_cosim'
    if change == 'run_token': receipt['run_token'] = 'another-run'
    _finish_failed_job(job, error, state, monitor_failure=monitor)
    assert state['status'] == 'needs_reconcile'
    assert job['status'] == 'failed'
    assert not job.get('result')
