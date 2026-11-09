"""Bounded worker exceptions retain evidence without replaying side effects."""
from pathlib import Path
from types import SimpleNamespace
import json
import pytest

from tpc_service.errors import ServiceError
from tpc_service.sessions.worker import _error_for_exception, _finish_failed_job
from tpc_service.sessions.diagnostics import mark_stage


def test_permission_error_keeps_os_filename_stage_and_restricted_frames(tmp_path):
    runtime=SimpleNamespace(); mark_stage(runtime,'checkpoint.write')
    job={'job_id':'j','operation':'history','params':{'secret':'must-not-copy'}}
    try:
        local_secret='must-not-copy'
        raise PermissionError(13,'Permission denied',str(tmp_path/'check.json'))
    except PermissionError as exc:
        error=_error_for_exception(exc,runtime,job)
    info=error['details']['diagnostics']
    assert error['code']=='session_operation_failed'
    assert info['exception_type']=='PermissionError' and info['errno']==13
    assert info['filename']==str(tmp_path/'check.json')
    assert info['stage']=='checkpoint.write'
    assert info['traceback'][-1]['function']==test_permission_error_keeps_os_filename_stage_and_restricted_frames.__name__
    assert set(info['traceback'][-1])=={'file','function','line'}
    assert local_secret not in json.dumps(error)
    state={'status':'ready','projects':{},'uncertain_jobs':[],'launch_intent':False}
    _finish_failed_job(job,error,state)
    assert state['status']=='needs_reconcile' and job['status']=='failed'
    assert not job.get('result')


def test_service_error_receipts_are_not_reclassified():
    exc=ServiceError('existing','saved evidence',outcome={'saved':True})
    assert _error_for_exception(exc,SimpleNamespace(),{'operation':'solve'})==exc.to_dict()


def test_traceback_and_message_are_bounded_without_source_or_locals():
    def recurse(depth):
        if depth: return recurse(depth-1)
        raise RuntimeError('x'*10000)
    try: recurse(30)
    except RuntimeError as exc:
        error=_error_for_exception(exc,SimpleNamespace(),{'operation':'history','job_id':'j'})
    info=error['details']['diagnostics']
    assert len(info['traceback'])==12 and info['frames_omitted']>0
    assert len(info['message'])<=4096 and info['message_truncated'] is True
    assert info['stage']=='worker.execute'
    assert len(error['message'])<=4096


def test_exception_chain_retains_cause_os_fields():
    try:
        try: raise OSError(13,'denied','first','unused','second')
        except OSError as cause: raise RuntimeError('wrapper') from cause
    except RuntimeError as exc:
        error=_error_for_exception(exc,SimpleNamespace(),{'operation':'history'})
    cause=error['details']['diagnostics']['causes'][0]
    assert cause['exception_type']=='PermissionError' and cause['filename']=='first'
    assert cause['filename2']=='second'


def test_checkpoint_failure_is_tagged_after_one_history_submission(tmp_path, monkeypatch):
    import hashlib
    from tpc_service.sessions import operations
    calls=[]; record={'path':str(tmp_path/'p.cst'),'saved_digest':'synthetic'}
    app=SimpleNamespace(cst_file=SimpleNamespace(schematic=SimpleNamespace(
        execute_vba_code=lambda *args,**kw: calls.append('history'))))
    runtime=SimpleNamespace(backend='cst', folder=tmp_path, project=lambda p:(app,record),
                            save=lambda *args: calls.append('save') or record)
    def fail_write(path,value): raise PermissionError(13,'denied',str(path))
    monkeypatch.setattr(operations,'write',fail_write)
    code='synthetic code'; job={'operation':'history','job_id':'j','operation_id':'o','fingerprint':'f',
        'params':{'project_id':'p','domain':'schematic','vba':code,'preview_digest':hashlib.sha256(code.encode()).hexdigest(),
                  'name':'stage','stage_id':'stage'}}
    try: operations._execute_operation(runtime,job)
    except PermissionError as exc: error=_error_for_exception(exc,runtime,job)
    assert calls==['history','save']
    assert error['details']['diagnostics']['stage']=='checkpoint.write'
    assert error['details']['diagnostics']['filename']==str(tmp_path/'checkpoints'/'j.json')


@pytest.mark.parametrize('boundary',['native_save','digest','persist'])
def test_runtime_save_failure_stage_is_precise(tmp_path, monkeypatch,boundary):
    from tpc_service.sessions import native
    runtime=native.Runtime(tmp_path,'fake'); path=tmp_path/'p.cst'; path.write_bytes(b'synthetic')
    record={'path':str(path)}; runtime.state=lambda:{'projects':{'p':record}}
    def denied(*a,**kw): raise PermissionError(13,'denied',str(path))
    app=SimpleNamespace(save=denied if boundary=='native_save' else lambda *a,**kw:None)
    monkeypatch.setattr(native,'file_digest',denied if boundary=='digest' else lambda p:'digest')
    runtime.update=denied if boundary=='persist' else lambda **kw:None
    with pytest.raises(PermissionError) as caught: runtime.save(app,'p')
    info=_error_for_exception(caught.value,runtime,{'operation':'history'})['details']['diagnostics']
    assert info['stage']=={'native_save':'project.save_native','digest':'project.digest_after_save',
                           'persist':'project.persist_saved_record'}[boundary]


@pytest.mark.parametrize('broken', ['str', 'repr', 'cause'])
def test_broken_exception_formatters_do_not_prevent_failure_fence(broken):
    class BrokenError(RuntimeError):
        def __str__(self): raise ValueError('text formatter failed')
        def __repr__(self):
            if broken == 'repr': raise ValueError('repr formatter failed')
            return 'BrokenError()'
    try:
        if broken == 'cause':
            try: raise BrokenError()
            except BrokenError as cause: raise RuntimeError('wrapper') from cause
        raise BrokenError()
    except Exception as exc:
        job={'operation':'history'}
        error=_error_for_exception(exc,SimpleNamespace(),job)
    state={'status':'ready','projects':{},'uncertain_jobs':[],'launch_intent':False}
    _finish_failed_job(job,error,state)
    assert state['status']=='needs_reconcile' and job['status']=='failed'
    assert error['code']=='session_operation_failed'
    json.dumps(error)
