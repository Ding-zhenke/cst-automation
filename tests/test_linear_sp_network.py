from pathlib import Path

import pytest

from cst_automation import embedded_network
from tpc_service.errors import ServiceError
from tpc_service.sessions.linear_sp import network_preflight, execute_network, check_prepared_network, sp_solve_preflight, execute_sp_solve
from test_embedded_network import sample
from test_workflow_enforcement import setup, bind, submit


def test_network_preflight_rejects_existing_output_before_native(tmp_path, monkeypatch):
    p, *_ = sample(tmp_path)
    p['qualification_job_id'] = 'qual'
    Path(p['output_path']).write_bytes(b'keep')
    called = []
    monkeypatch.setattr('tpc_service.sessions.linear_sp.verify_exploratory_matrix',
                        lambda *args: called.append(True))
    state = {'status': 'ready', 'projects': {'p': {'project_id': 'p'}}}
    with pytest.raises(ServiceError): network_preflight(tmp_path, state, p)
    assert not called
    assert Path(p['output_path']).read_bytes() == b'keep'


def test_network_preflight_checks_source_and_rejects_invalid_matrix(tmp_path, monkeypatch):
    p, *_ = sample(tmp_path)
    p['qualification_job_id'] = 'qual'
    state = {'status': 'ready', 'projects': {'p': {'project_id': 'p'}}}
    called = []
    monkeypatch.setattr('tpc_service.sessions.linear_sp.verify_exploratory_matrix',
                        lambda *args: called.append(True) or {'source_job_id': 'em'})
    network_preflight(tmp_path, state, p)
    assert called == [True]
    p['matrix_sha256'] = 'f'*64
    with pytest.raises(ServiceError): network_preflight(tmp_path, state, p)
    assert called == [True]


def test_network_failure_invalidates_hb_before_native_write(tmp_path, monkeypatch):
    p, *_ = sample(tmp_path)
    p['qualification_job_id'] = 'qual'
    project = {'project_id': 'p', 'path': str(tmp_path/'project.cst'),
               'workflow': {'hb_generation': 1, 'em_generation': 2,
                            'evidence': {'old': True}, 'network_update': {'old': True}}}
    class Runtime:
        folder = tmp_path
        def state(self): return {'projects': {'p': project}}
        def update(self, **kw): pass
        def save(self, *args): pass
    monkeypatch.setattr('tpc_service.sessions.linear_sp.verify_exploratory_matrix', lambda *args: {'source': 'ok'})
    monkeypatch.setattr('tpc_service.sessions.workflow.live_checks', lambda *args: None)
    def fail(*args): raise RuntimeError('native failed')
    monkeypatch.setattr('cst_solver.circuit.embedded_network.prepare', fail)
    with pytest.raises(ServiceError) as exc:
        execute_network(Runtime(), {'job_id': 'j', 'params': p}, object())
    assert exc.value.code == 'session_exploratory_sp_network_partial'
    assert project['workflow']['network_required'] is True
    assert project['workflow']['network_update'] is None and project['workflow']['evidence'] is None


def test_network_success_keeps_formal_hb_gate_closed(tmp_path, monkeypatch):
    p, *_ = sample(tmp_path); p['qualification_job_id'] = 'qual'
    project = {'project_id': 'p', 'path': str(tmp_path/'project.cst'),
               'workflow': {'hb_generation': 1, 'em_generation': 2, 'evidence': {'old': True}}}
    class Runtime:
        folder = tmp_path
        def state(self): return {'projects': {'p': project}}
        def update(self, **kw): pass
        def save(self, *args): pass
    monkeypatch.setattr('tpc_service.sessions.linear_sp.verify_exploratory_matrix', lambda *args: {'source': 'ok'})
    monkeypatch.setattr('tpc_service.sessions.workflow.live_checks', lambda *args: None)
    monkeypatch.setattr('cst_solver.circuit.embedded_network.prepare', lambda *args: {'after': {'sha256': 'new'}})
    result = execute_network(Runtime(), {'job_id': 'j', 'params': p}, object())
    assert project['workflow']['sp_network']['job_id'] == 'j'
    assert project['workflow']['network_required'] is True
    assert project['workflow']['network_update'] is None
    assert result['formal_hb_gate_satisfied'] is False


def test_prepared_network_rejects_stale_generation_before_native_readback(tmp_path):
    project = {'project_id': 'p', 'workflow': {'em_generation': 3,
               'sp_network': {'job_id': 'job', 'em_generation': 2}}}
    with pytest.raises(ServiceError): check_prepared_network(tmp_path, project, 'job')


def test_sp_solve_rejects_missing_reviewed_setup(tmp_path):
    state = {'status': 'ready', 'projects': {'p': {'project_id': 'p',
             'workflow': {'em_generation': 2}}}}
    p = {'project_id': 'p', 'network_job_id': 'net', 'setup_job_id': 'setup',
         'task_name': 'SP', 'expected_results': [{'tree_path': 'Tasks\\SP\\S-Parameters\\S1,1', 'run_id': 0}]}
    with pytest.raises(ServiceError): sp_solve_preflight(tmp_path, state, p)


def test_sp_solve_refuses_unverified_frequency_unit_or_sample_count(tmp_path, monkeypatch):
    import json
    folder = tmp_path; (folder/'jobs').mkdir()
    setup = {'job_id': 'setup', 'network_job_id': 'net', 'em_generation': 2,
             'task_name': 'SP', 'saved_digest': 'digest', 'task': {},
             'task_report': {'frequency_unit_readback': 'unsupported', 'sample_count_readback': 'unsupported'}}
    state = {'status': 'ready', 'projects': {'p': {'project_id': 'p', 'saved_digest': 'digest',
             'workflow': {'em_generation': 2, 'sp_setup': setup}}}}
    source = {'status': 'succeeded', 'operation': 'configure_exploratory_linear_sp',
              'params': {'project_id': 'p', 'network_job_id': 'net', 'task': {}},
              'result': {'saved_digest': 'digest'}}
    (folder/'jobs'/'setup.json').write_text(json.dumps(source))
    monkeypatch.setattr('tpc_service.sessions.job_index.JobIndex.load',
                        lambda *a: type('Index', (), {'active_jobs': lambda self: []})())
    p = {'project_id': 'p', 'network_job_id': 'net', 'setup_job_id': 'setup', 'task_name': 'SP'}
    with pytest.raises(ServiceError) as exc: sp_solve_preflight(folder, state, p)
    assert exc.value.code == 'workflow_exploratory_sp_setup_unverified'


def test_sp_solve_refuses_changed_topology_before_solver(tmp_path, monkeypatch):
    p = {'project_id': 'p', 'network_job_id': 'net', 'setup_job_id': 'setup',
         'task_name': 'SP', 'expected_results': [{'tree_path': 'Tasks\\SP\\S-Parameters\\S1,1', 'run_id': 0}]}
    setup = {'task_name': 'SP', 'topology': {'different': True},
             'task': {'fmin': 1, 'fmax': 2}}
    update = {'params': {'block_name': 'N'}}
    project = {'project_id': 'p', 'path': str(tmp_path/'project.cst'), 'workflow': {}}
    class Runtime:
        folder = tmp_path
        def state(self): return {'projects': {'p': project}}
    monkeypatch.setattr('tpc_service.sessions.linear_sp.sp_solve_preflight', lambda *a, **k: setup)
    monkeypatch.setattr('tpc_service.sessions.linear_sp.check_prepared_network', lambda *a, **k: update)
    monkeypatch.setattr('tpc_service.sessions.workflow.live_checks', lambda *a, **k: None)
    monkeypatch.setattr('cst_solver.circuit.embedded_network.snapshot', lambda *a: {'different': False})
    with pytest.raises(ServiceError): execute_sp_solve(Runtime(), {'params': p}, object())


def test_protected_network_submit_refuses_old_worker(setup, monkeypatch):
    from tpc_service.sessions.store import read, write
    bind(setup)
    manager, ref, folder, _, launches = setup
    state = read(folder/'session.json')
    state['worker'] = {'pid': 123, 'started': 1, 'image': 'worker'}
    state['worker_capabilities'] = ['parameter-em-hb-v1']
    write(folder/'session.json', state)
    monkeypatch.setattr('tpc_service.sessions.workflow.alive', lambda _: True)
    monkeypatch.setattr('tpc_service.sessions.linear_sp.alive', lambda _: True, raising=False)
    monkeypatch.setattr('tpc_service.sessions.store.alive', lambda _: True)
    p, *_ = sample(folder)
    p['qualification_job_id'] = 'qual'
    with pytest.raises(ServiceError) as exc:
        submit(setup, 'prepare_exploratory_sp_network', {k: v for k, v in p.items() if k != 'project_id'})
    assert exc.value.code == 'workflow_worker_upgrade_required'
    assert not launches
