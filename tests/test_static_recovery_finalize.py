import hashlib
from pathlib import Path
from types import SimpleNamespace
import pytest
from tpc_service.errors import ServiceError
from tpc_service.sessions.manager import SessionManager
from tpc_service.sessions.store import read,write,digest


@pytest.fixture
def finalized_fixture(tmp_path,monkeypatch):
    from tpc_service.sessions import static_sp_finalize as finalizer, native_handoff
    from cst_solver.circuit import adapter as circuit_adapter
    manager=SessionManager(tmp_path,backend='cst');ref=manager.ensure('finalize','one')
    folder=tmp_path/ref['session_id'];project=folder/'model.cst';project.write_bytes(b'project')
    sha=hashlib.sha256(project.read_bytes()).hexdigest();error={'code':'session_static_sp_prepare_failed'}
    original={'job_id':'failed','session_id':ref['session_id'],'status':'failed','operation':'prepare_static_sp',
              'params':{'project_id':'p'},'error':error}
    write(folder/'jobs'/'failed.json',original)
    snapshot={'blocks':[],'unknown':[]}
    excluded={'job_id':'excluded','session_id':ref['session_id'],'status':'succeeded','operation':'exclude_unconnected_self_em',
              'params':{'project_id':'p'},'result':{'after':snapshot,'original_failed_job_id':'failed'}}
    write(folder/'jobs'/'excluded.json',excluded)
    output=folder/'static_sp_runs'/'run';output.mkdir(parents=True)
    current=output/'current-curves.json';current.write_text('{}');positive=output/'positive-read.json';positive.write_text('{}')
    run={'job_id':'run','session_id':ref['session_id'],'status':'succeeded','operation':'run_fenced_static_sp',
         'params':{'project_id':'p','snapshot_digest':digest(snapshot),'failed_job_id':'failed',
                   'exclude_job_id':'excluded','impedance_job_id':'impedance','confirm_run':True},'result':{'saved':True,'saved_digest':sha,
          'original_failed_job_id':'failed','exclude_job_id':'excluded','impedance_job_id':'impedance','solver_verified':True,'actual_grid_verified':True,
          'structural_no_em_dependency_verified':True,'3d_files_unchanged':True,'3d_log_unchanged':True,
          'task_name':'SP','run_token':'token','circuit_outcome':{'status':'succeeded','submitted':True,
          'execution_returned':True,'update_call_state':'returned','saved':True,'saved_digest':sha,
          'task_name':'SP','mode':'network','run_token':'token','execution_evidence':{'completed':True}},
          'current_curves_path':str(current),'current_curves_sha256':hashlib.sha256(current.read_bytes()).hexdigest()}}
    reading={'job_id':'read','session_id':ref['session_id'],'status':'succeeded','operation':'read_fenced_static_sp',
         'params':{'project_id':'p','failed_job_id':'failed','run_job_id':'run','expected_saved_digest':sha,
                   'positive_run_id':7,'confirm_idle':True},'result':{'original_failed_job_id':'failed','run_job_id':'run','saved_digest':sha,
          'positive_run_id':7,'current_content_matches_positive':True,'positive_curves_path':str(positive),
          'positive_curves_sha256':hashlib.sha256(positive.read_bytes()).hexdigest()}}
    write(folder/'jobs'/'run.json',run);write(folder/'jobs'/'read.json',reading)
    worker={'pid':11,'started':1,'image':'python.exe'};de={'pid':22,'started':2,'image':'cst.exe'}
    state=read(folder/'session.json');state.update(status='needs_reconcile',last_error=error,worker=worker,environment=de,
        worker_capabilities=['static-sp-guarded-run-v1'],
        projects={'p':{'project_id':'p','path':str(project),'saved':True,'saved_digest':sha}},
        last_worker_upgrade={'mode':'preserve_native_de_v1','phase':'complete','return_to_fence':True,
          'new_worker':worker,'environment':de,'static_partial':{'failed_job_id':'failed','project_id':'p',
          'failed_job_digest':digest(original)}})
    write(folder/'session.json',state)
    monkeypatch.setattr(finalizer,'alive',lambda identity:True)
    monkeypatch.setattr(finalizer.JobIndex,'load',lambda folder:SimpleNamespace(active_jobs=lambda:[]))
    monkeypatch.setattr(finalizer,'assert_environment_unclaimed',lambda *a:None)
    def verify(runtime,state):
        runtime.app=SimpleNamespace(cst_file=None);runtime.handles={'p':SimpleNamespace(filename=lambda:str(project))}
        return {'tabs':[str(project)]}
    monkeypatch.setattr(native_handoff,'verify_native',verify)
    monkeypatch.setattr(circuit_adapter,'NativeAdapter',lambda app:SimpleNamespace(inspect=lambda:snapshot))
    review={'failed_job_id':'failed','run_job_id':'run','read_job_id':'read','project_digests':{'p':sha},
            'environment_identity':de,'review_note':'Reviewed saved result and idle session','confirm_idle':True}
    return manager,ref,folder,review


def test_scoped_finalizer_clears_only_original_failure_fence(finalized_fixture):
    manager,ref,folder,review=finalized_fixture
    result=manager.accept_completed_static_recovery(ref['session_id'],ref['credential'],**review)
    assert result['status']=='ready' and not result['formal_hb_gate_satisfied']
    assert read(folder/'jobs'/'failed.json')['status']=='failed'
    assert read(folder/'session.json')['last_error'] is None
    assert manager.accept_completed_static_recovery(ref['session_id'],ref['credential'],**review)['read_job_id']=='read'


def test_changed_positive_artifact_rejects_before_native_review(finalized_fixture,monkeypatch):
    from tpc_service.sessions import native_handoff
    manager,ref,folder,review=finalized_fixture
    (folder/'static_sp_runs'/'run'/'positive-read.json').write_text('changed')
    monkeypatch.setattr(native_handoff,'verify_native',lambda *a:pytest.fail('No native review for bad receipt'))
    with pytest.raises(ServiceError): manager.accept_completed_static_recovery(ref['session_id'],ref['credential'],**review)
    assert read(folder/'session.json')['status']=='needs_reconcile'


def test_incomplete_native_run_receipt_cannot_clear_fence(finalized_fixture,monkeypatch):
    from tpc_service.sessions import native_handoff
    manager,ref,folder,review=finalized_fixture
    job=read(folder/'jobs'/'run.json');job['result']['circuit_outcome']['execution_returned']=False
    write(folder/'jobs'/'run.json',job)
    monkeypatch.setattr(native_handoff,'verify_native',lambda *a:pytest.fail('No native review for incomplete run'))
    with pytest.raises(ServiceError): manager.accept_completed_static_recovery(ref['session_id'],ref['credential'],**review)
    assert read(folder/'session.json')['status']=='needs_reconcile'


def test_mismatched_positive_request_cannot_clear_fence(finalized_fixture,monkeypatch):
    from tpc_service.sessions import native_handoff
    manager,ref,folder,review=finalized_fixture
    job=read(folder/'jobs'/'read.json');job['params']['positive_run_id']=8
    write(folder/'jobs'/'read.json',job)
    monkeypatch.setattr(native_handoff,'verify_native',lambda *a:pytest.fail('No native review for mismatched ID'))
    with pytest.raises(ServiceError): manager.accept_completed_static_recovery(ref['session_id'],ref['credential'],**review)
    assert read(folder/'session.json')['status']=='needs_reconcile'
