"""Baseline acceptance uses synthetic getters; never opens or writes a CST file."""
import copy
from pathlib import Path
from types import SimpleNamespace

import pytest

from test_workflow_enforcement import setup, prepare_em_evidence, submit, native_app
from tpc_service.sessions import saved_baseline as baseline
from tpc_service.sessions import store, operations
from tpc_service.errors import ServiceError


@pytest.fixture
def reviewed(setup, monkeypatch):
    runtime, em, _, _ = prepare_em_evidence(setup)
    state = runtime.state(); record = state['projects']['p']; old = record['saved_digest']
    setup[3].write_bytes(b'reviewed external save')
    review = setup[2]/'review.json'; store.write(review, {'review': 'synthetic native readback'})
    identity = {'pid': 12345, 'started': 67890, 'image': 'synthetic-CST.exe'}
    state.update(environment=identity, worker={'pid': 54321, 'started': 67890, 'image':'synthetic-worker.exe'},
                 worker_capabilities=[baseline.CAPABILITY],
                 last_error={'code': 'preserved_old_error'}, last_resolution={'old': 'preserve'})
    workflow = record['workflow']
    workflow.update(network_fit={'old': 'fit'}, network_update={'old': 'update'},
                    network_required=True, evidence={'old': 'analysis'})
    store.write(setup[2]/'session.json', state)
    monkeypatch.setattr(baseline, 'alive', lambda value: bool(value))
    monkeypatch.setattr(store, 'alive', lambda value: bool(value))
    from cst_solver import environment, dialogs
    monkeypatch.setattr(environment, 'environment_pid', lambda project: project.pid)
    monkeypatch.setattr(dialogs, 'check_dialogs', lambda *a, **k: None)
    parameters = {k: {'value': v, 'expression': str(v)} for k,v in workflow['values'].items()}
    blocks = {'EM': 'CST MICROWAVE STUDIO schematic block', 'Source': 'voltage source'}
    properties = {'Source': {'Resistance': 75}}
    class Block:
        def StartBlockNameIteration(self): self.names = iter(blocks)
        def GetNextBlockName(self): return next(self.names, '')
        def GetTypeName(self): return blocks[self.name]
        def GetProperty(self, name): return properties[self.name][name]
    block = Block()
    def select(kind, name): block.name = name; return block
    app = native_app()
    model = app.cst_file.model3d
    model.GetNumberOfParameters = lambda: len(parameters)
    model.GetParameterName = lambda i: list(parameters)[i]
    model.RestoreParameterExpression = lambda n: parameters[n]['expression']
    model.is_solver_running = lambda **k: False
    app.get_parameter = lambda n: parameters[n]['value']
    handle = app.cst_file
    handle.filename = lambda: str(setup[3])
    handle.schematic = SimpleNamespace(Block=block)
    app.circuit.adapter = SimpleNamespace(select=select)
    app.project = SimpleNamespace(pid=identity['pid'], list_open_projects=lambda: [str(setup[3])],
                                  get_open_project=lambda path: handle)
    runtime.app = app
    runtime.project = lambda *a: pytest.fail('Normal acquisition must not run on mismatched baseline')
    runtime.save = lambda *a: pytest.fail('Baseline adoption must not save CST')
    p = dict(project_id='p', old_digest=old, new_digest=baseline.file_digest(setup[3]),
             environment_identity=identity, expected_parameters=copy.deepcopy(parameters),
             expected_blocks=copy.deepcopy(blocks), expected_block_properties=copy.deepcopy(properties),
             review_path=str(review), review_sha256=baseline.file_digest(review),
             review_note='Reviewed original idle tab and saved parameters',
             authorization_note='Authorized to accept this reviewed save',
             confirm_idle=True, confirm_saved_tab=True, accept_external_save=True)
    setup[-1].clear()
    return runtime, p, app, parameters, blocks, properties, em


def queue(setup, p, request='baseline'):
    return submit(setup, baseline.OPERATION, {k:v for k,v in p.items() if k != 'project_id'}, request)


def test_accepts_atomically_invalidates_and_preserves_old_errors(setup, reviewed):
    runtime, p, app, *_, em = reviewed
    before = runtime.state(); original_job = store.read(setup[2]/'jobs'/(em['job_id']+'.json'))
    job = queue(setup, p)
    assert not setup[-1]  # even a valid review must not launch/restart the worker
    result = operations.execute(runtime, job)
    after = runtime.state(); old_w = before['projects']['p']['workflow']; new_w = after['projects']['p']['workflow']
    assert after['projects']['p']['saved_digest'] == p['new_digest']
    assert after['baseline_acceptances'] == [result['audit']]
    for key in ('em_receipt','evidence','network_fit','network_update'): assert new_w[key] is None
    for key in ('em_generation','hb_generation'): assert new_w[key] == old_w[key]+1
    assert new_w['network_required'] is True and new_w['spec'] == old_w['spec']
    assert result['invalidated_workflow'] == old_w and result['saved'] is False
    assert after['last_error'] == before['last_error'] and after['last_resolution'] == before['last_resolution']
    assert after['status'] == 'ready' and after['environment'] == before['environment'] and after['worker'] == before['worker']
    assert store.read(setup[2]/'jobs'/(em['job_id']+'.json')) == original_job
    assert baseline.file_digest(setup[3]) == p['new_digest']
    job.update(status='succeeded', result=result); store.write(setup[2]/'jobs'/(job['job_id']+'.json'), job)
    assert queue(setup, p)['result'] == result
    assert len(runtime.state()['baseline_acceptances']) == 1


@pytest.mark.parametrize('bad', ['old_digest','new_digest','review','confirm_idle','confirm_saved_tab',
    'accept_external_save','authorization_note','expression','parameter_target','identity',
    'worker','capability','fence','uncertain','launch','closing','diagnostic','closed_tab','busy'])
def test_bad_review_cannot_queue_or_launch(setup, reviewed, bad):
    runtime, p, *_ = reviewed
    state = runtime.state()
    if bad in ('old_digest','new_digest'): p[bad] = 'f'*64
    elif bad == 'review': Path(p['review_path']).write_text('{}')
    elif bad in ('confirm_idle','confirm_saved_tab','accept_external_save'): p[bad] = False
    elif bad == 'authorization_note': p[bad] = ''
    elif bad == 'expression': p['expected_parameters']['width'].pop('expression')
    elif bad == 'parameter_target': p['expected_parameters']['width']['value'] = 99
    elif bad == 'identity': p['environment_identity'] = dict(p['environment_identity'], started=999)
    elif bad == 'worker': state['worker'] = None
    elif bad == 'capability': state['worker_capabilities'] = []
    elif bad == 'fence': state['status'] = 'needs_reconcile'
    elif bad == 'uncertain': state['uncertain_jobs'] = ['unknown']
    elif bad == 'launch': state['launch_intent'] = True
    elif bad == 'closing': state['close_requested'] = True
    elif bad == 'diagnostic': state['runtime_diagnostics'] = {'state':'blocked'}
    elif bad == 'closed_tab': state['projects']['p']['tab_closed'] = True
    elif bad == 'busy':
        store.write(setup[2]/'jobs'/'other.json', dict(job_id='other', status='running', sequence=100,
                                                     request_id='other', operation_id='other'))
    store.write(setup[2]/'session.json', state)
    with pytest.raises(ServiceError): queue(setup, p)
    assert not setup[-1]
    assert runtime.state()['projects']['p']['saved_digest'] == p['old_digest'] or bad == 'old_digest'
    assert 'baseline_acceptances' not in runtime.state()


@pytest.mark.parametrize('bad', ['disk','review','workflow','environment'])
def test_stale_queued_review_stops_before_native_access(setup, reviewed, monkeypatch, bad):
    runtime, p, *_ = reviewed
    job = queue(setup, p)
    if bad == 'disk': setup[3].write_bytes(b'another later save')
    elif bad == 'review': Path(p['review_path']).write_text('{}')
    else:
        state = runtime.state()
        if bad == 'workflow': state['projects']['p']['workflow']['em_generation'] += 1
        else: state['environment']['started'] = 999
        store.write(setup[2]/'session.json', state)
    from tpc_service.sessions import read_review
    monkeypatch.setattr(read_review, 'borrow_open_project', lambda *a: pytest.fail('Must reject before native access'))
    with pytest.raises(ServiceError): operations.execute(runtime, job)
    assert 'baseline_acceptances' not in runtime.state()


@pytest.mark.parametrize('bad', ['value','expression','extra_parameter','missing_parameter', 'block','extra_block',
                                 'property','running','unknown_idle','closed_native_tab','wrong_pid','wrong_path'])
def test_native_refusals_preserve_ready_and_baseline(setup, reviewed, bad):
    from tpc_service.sessions.worker import _finish_failed_job
    runtime, p, app, parameters, blocks, props, _ = reviewed
    job = queue(setup, p)
    if bad == 'value': parameters['width']['value'] = 7
    if bad == 'expression': parameters['width']['expression'] = 'length/2'
    if bad == 'extra_parameter': parameters['new'] = dict(value=1, expression='1')
    if bad == 'missing_parameter': parameters.pop('width')
    if bad == 'block': blocks['Source'] = 'different'
    if bad == 'extra_block': blocks['other'] = 'resistor'
    if bad == 'property': props['Source']['Resistance'] = 50
    if bad in ('running','unknown_idle'): app.cst_file.model3d.is_solver_running = lambda **k: True if bad == 'running' else None
    if bad == 'closed_native_tab': app.project.list_open_projects = lambda: []
    if bad == 'wrong_pid': app.project.pid += 1
    if bad == 'wrong_path': app.cst_file.filename = lambda: str(setup[3].with_name('other.cst'))
    with pytest.raises((ValueError, ServiceError)): operations.execute(runtime, job)
    state = runtime.state()
    _finish_failed_job(job, {'code':'native_review_refused','details':{}}, state)
    assert state['status'] == 'ready' and state['projects']['p']['saved_digest'] == p['old_digest']
    assert 'baseline_acceptances' not in state


def test_late_disk_change_cannot_commit(setup, reviewed, monkeypatch):
    runtime, p, *_ = reviewed
    job = queue(setup, p); original = baseline.native_review
    def changed(*args):
        result = original(*args); setup[3].write_bytes(b'changed while reviewing'); return result
    monkeypatch.setattr(baseline, 'native_review', changed)
    with pytest.raises(ServiceError): operations.execute(runtime, job)
    assert runtime.state()['projects']['p']['saved_digest'] == p['old_digest']


def test_persistence_failure_never_masquerades_as_read_only_refusal(setup, reviewed, monkeypatch):
    from tpc_service.sessions.worker import _finish_failed_job
    runtime, p, *_ = reviewed
    job = queue(setup, p)
    monkeypatch.setattr(baseline, 'write', lambda *a: (_ for _ in ()).throw(OSError('write failed')))
    with pytest.raises(OSError): operations.execute(runtime, job)
    state = runtime.state()
    _finish_failed_job(job, {'code':'state_write_failed','details':{}}, state)
    assert state['status'] == 'needs_reconcile'
    assert runtime.state()['projects']['p']['saved_digest'] == p['old_digest']


def test_normal_writes_still_refuse_external_save(setup, reviewed):
    with pytest.raises(ServiceError): submit(setup, 'set_parameters', {'values': {'length': 5}}, 'change')
    assert not setup[-1]


def test_native_monitor_failure_keeps_fence(setup, reviewed):
    from tpc_service.sessions.worker import _finish_failed_job
    runtime, p, *_ = reviewed
    job = queue(setup, p); job['baseline_acceptance_read_only'] = True
    state = runtime.state()
    _finish_failed_job(job, {'code':'dialog','details':{}}, state, monitor_failure={'state':'blocked'})
    assert state['status'] == 'needs_reconcile'


@pytest.mark.parametrize('failure_call', [1, 2])
@pytest.mark.parametrize('error_type', ['timeout', 'inspection'])
def test_synchronous_dialog_inspection_failure_fences_without_background_event(setup, reviewed, monkeypatch, failure_call, error_type):
    from cst_solver import dialogs
    from tpc_service.sessions.worker import _finish_failed_job
    runtime, p, *_ = reviewed; job = queue(setup, p); count = []
    def check(*a, **k):
        count.append(1)
        if len(count) == failure_call:
            if error_type == 'timeout': raise dialogs.CstDialogTimeout('Synthetic blocking dialog')
            raise RuntimeError('Dialog inspection unavailable')
    monkeypatch.setattr(dialogs, 'check_dialogs', check)
    with pytest.raises((RuntimeError, dialogs.CstDialogTimeout)): operations.execute(runtime, job)
    state = runtime.state()
    _finish_failed_job(job, {'code':'session_operation_failed','details':{}}, state)
    assert state['status'] == 'needs_reconcile' and 'baseline_acceptances' not in state


def test_late_native_parameter_change_is_rejected(setup, reviewed, monkeypatch):
    from cst_solver import dialogs
    runtime, p, _, parameters, *_ = reviewed; job = queue(setup, p); count = []
    def check(*a, **k):
        count.append(1)
        if len(count) == 2: parameters['width']['value'] = 8
    monkeypatch.setattr(dialogs, 'check_dialogs', check)
    with pytest.raises(ValueError): operations.execute(runtime, job)
    assert runtime.state()['projects']['p']['saved_digest'] == p['old_digest']


def test_other_session_environment_claim_rejected_before_borrow(setup, reviewed, monkeypatch):
    from tpc_service.sessions import read_review
    runtime, p, *_ = reviewed; job = queue(setup, p)
    store.write(setup[2].parent/'ses-other'/'session.json', dict(session_id='ses-other',
                 environment=p['environment_identity'], status='ready'))
    monkeypatch.setattr(read_review, 'borrow_open_project', lambda *a: pytest.fail('Must not borrow another session environment'))
    with pytest.raises(ServiceError): operations.execute(runtime, job)
    assert 'baseline_acceptances' not in runtime.state()


def test_commit_then_write_error_keeps_audit_and_requires_reconcile(setup, reviewed, monkeypatch):
    from tpc_service.sessions.worker import _finish_failed_job
    runtime, p, *_ = reviewed; job = queue(setup, p)
    original_write = baseline.write
    def wrote_then_failed(path, state):
        original_write(path, state)
        raise OSError('Synthetic error after replacement')
    monkeypatch.setattr(baseline, 'write', wrote_then_failed)
    with pytest.raises(OSError): operations.execute(runtime, job)
    state = runtime.state()
    assert state['projects']['p']['saved_digest'] == p['new_digest']
    assert state['baseline_acceptances'][0]['job_id'] == job['job_id']
    _finish_failed_job(job, {'code':'state_write_uncertain','details':{}}, state)
    assert state['status'] == 'needs_reconcile'
