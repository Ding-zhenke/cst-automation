"""Sticky monitor evidence must survive a primary operation exception."""
import copy
import os
from tpc_service.sessions import worker
from tpc_service.tests.test_geometry_saved_review import receipt,error_receipt


def test_primary_error_retains_latched_failure_even_if_latest_snapshot_is_clear(tmp_path):
    case=receipt(tmp_path); error=error_receipt(case); original=copy.deepcopy(error)
    runtime,app,record,state,job=case
    first={'state':'monitor_error','label':'j','error':{'code':'cst_dialog_monitor_failed','message':'synthetic failure'}}
    final={'state':'clear','attention_required':False,'dialogs':[]}
    worker._finish_failed_job(job,error,state,monitor_failure=first,monitor_snapshot=final)
    assert state['status']=='needs_reconcile' and job['status']=='failed'
    assert job['error']['code']==original['code']
    assert job['error']['details']['geometry_outcome']==original['details']['geometry_outcome']
    assert job['error']['details']['session_monitor']['first_failure']==first
    assert job['error']['details']['session_monitor']['final_snapshot']==final
    assert error==original
    assert job['completion_evidence']['reason']=='monitor_failure_latched'
    assert job['completion_evidence']['prior_status']=='ready'
    assert job['completion_evidence']['decision']=='needs_reconcile'
    assert not job.get('result')
    assert worker._known_saved_geometry(job,job['error'],dict(state,status='ready'),None) is False


def test_clear_monitor_evidence_does_not_change_primary_unverified_status(tmp_path):
    case=receipt(tmp_path); error=error_receipt(case)
    worker._finish_failed_job(case[4],error,case[3],monitor_snapshot={'state':'clear'})
    assert case[3]['status']=='ready' and case[4]['status']=='failed'
    assert case[4]['completion_evidence']['reason']=='verified_returned_saved'
    assert case[4]['result']['geometry_outcome']['geometry_verified'] is False
    assert case[4]['error']['details']['session_monitor']['failure_latched'] is False


def test_prior_fence_is_distinct_from_monitor_or_receipt_failure(tmp_path):
    case=receipt(tmp_path); error=error_receipt(case); case[3]['status']='needs_reconcile'
    worker._finish_failed_job(case[4],error,case[3])
    assert case[4]['completion_evidence']['reason']=='prior_state_not_ready'
    assert case[4]['completion_evidence']['monitor_failure_seen'] is False


def test_worker_fingerprint_describes_loaded_code_objects():
    info=worker._worker_runtime_info()
    assert info['pid']==os.getpid() and info['executable']
    assert len(info['code_fingerprints']['known_saved_geometry'])==64
    assert info==worker._worker_runtime_info()
    def first(): return 1
    def second(): return 2
    assert worker._code_fingerprint(first)!=worker._code_fingerprint(second)


def test_unavailable_monitor_snapshot_is_not_assumed_clear(tmp_path):
    from types import SimpleNamespace
    def broken(): raise RuntimeError('snapshot unavailable')
    failure,snapshot=worker._monitor_completion(SimpleNamespace(failure=None,snapshot=broken))
    assert failure['state']=='monitor_error' and failure['evidence_source']=='worker_snapshot_error'
    case=receipt(tmp_path); error=error_receipt(case)
    worker._finish_failed_job(case[4],error,case[3],monitor_failure=failure,monitor_snapshot=snapshot)
    assert case[3]['status']=='needs_reconcile'


def test_first_snapshot_error_survives_later_successful_clear_snapshot():
    from types import SimpleNamespace
    attempts=[]
    def snapshot():
        attempts.append(1)
        if len(attempts)==1: raise RuntimeError('first snapshot failed')
        return {'state':'clear'}
    monitor=SimpleNamespace(failure=None,snapshot=snapshot)
    first,_=worker._monitor_completion(monitor)
    failure,final=worker._monitor_completion(monitor,prior_failure=first)
    assert failure==first and final=={'state':'clear'}
