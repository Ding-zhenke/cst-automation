"""Explicit closed process retirement never opens or deletes a real project."""
from pathlib import Path
from unittest.mock import Mock
import pytest
from tpc_service.errors import ServiceError
from tpc_service.sessions.store import write
from tpc_service.sessions.validation import validate
from tpc_service.tests.test_session_project_discipline import fixture, job


def closed(tmp_path):
    _,_,runtime,record=fixture(tmp_path)
    record.update(tab_closed=True,lifetime='working'); runtime.update(projects={'main':record},status='ready')
    runtime.project=Mock(side_effect=AssertionError('must not reopen'))
    runtime.environment=Mock(side_effect=AssertionError('must not connect'))
    runtime.save=Mock(side_effect=AssertionError('must not save'))
    return runtime,record


def params(record):
    return dict(project_id='main',retire=True,expected_digest=record['saved_digest'],
                confirm_idle=True,review_note='Formal delivery and dependencies separately reviewed; process no longer needed')


def test_already_closed_working_process_can_retire_without_native_calls_or_deletion(tmp_path):
    runtime,record=closed(tmp_path); path=Path(record['path']); original=path.read_bytes()
    resources=path.with_suffix(''); resources.mkdir(); (resources/'evidence.txt').write_text('keep')
    write(runtime.folder/'jobs'/'j.json',dict(job_id='j',status='running'))
    out=runtime.execute(job('close_project',**params(record)))
    assert out['retired'] is out['already_closed'] is out['saved'] is True
    assert out['environment_closed'] is out['files_deleted'] is False
    assert out['idle_verified'] is False
    assert 'main' not in runtime.state()['projects']
    retired=runtime.state()['retired_projects']['main']
    assert retired['lifetime']=='working' and retired['retirement_review']['expected_digest']==record['saved_digest']
    assert path.read_bytes()==original and (resources/'evidence.txt').read_text()=='keep'
    runtime.project.assert_not_called(); runtime.environment.assert_not_called(); runtime.save.assert_not_called()
    path.unlink()  # Synthetic caller cleanup; the API must not perform this.
    again=runtime.execute(job('close_project',**params(record)))
    assert again['retired'] and again['already_closed'] and not path.exists()


@pytest.mark.parametrize('issue',['missing_digest','missing_idle','missing_note','false_flag','nonbool'])
def test_retirement_input_is_explicit_and_validated_before_queue(issue):
    p={'project_id':'main','retire':True,'expected_digest':'a'*64,'confirm_idle':True,'review_note':'reviewed'}
    if issue=='missing_digest': p.pop('expected_digest')
    if issue=='missing_idle': p.pop('confirm_idle')
    if issue=='missing_note': p.pop('review_note')
    if issue=='false_flag': p['retire']=False
    if issue=='nonbool': p['retire']=1
    with pytest.raises(ServiceError): validate('close_project',p)


@pytest.mark.parametrize('issue',['open','unsaved','request_digest','disk','outside','foreign_id','cached',
    'fence','uncertain','launch','dialog','queued','running','unresolved'])
def test_unsafe_or_foreign_process_is_not_retired(tmp_path,issue):
    runtime,record=closed(tmp_path); p=params(record)
    if issue=='open': record['tab_closed']=False
    if issue=='unsaved': record['saved']=False
    if issue=='request_digest': p['expected_digest']='0'*64
    if issue=='disk': Path(record['path']).write_bytes(b'changed')
    if issue=='outside':
        outside=tmp_path/'formal.cst'; outside.write_bytes(Path(record['path']).read_bytes()); record['path']=str(outside)
    if issue=='foreign_id': record['project_id']='other'
    if issue=='cached': runtime.handles['main']=object()
    runtime.update(projects={'main':record})
    if issue=='fence': runtime.update(status='needs_reconcile')
    if issue=='uncertain': runtime.update(uncertain_jobs=['unknown'])
    if issue=='launch': runtime.update(launch_intent=True)
    if issue=='dialog': runtime.update(runtime_diagnostics={'state':'blocked_by_dialog'})
    if issue in ('queued','running','unresolved'):
        write(runtime.folder/'jobs'/'other.json',dict(job_id='other',status='needs_reconcile' if issue=='unresolved' else issue))
    with pytest.raises(ServiceError): runtime.execute(job('close_project',**p))
    assert 'main' in runtime.state()['projects'] and not runtime.state().get('retired_projects',{}).get('main')
    assert Path(record['path']).exists()
    runtime.project.assert_not_called(); runtime.environment.assert_not_called(); runtime.save.assert_not_called()


def test_default_closed_working_project_stays_active(tmp_path):
    runtime,record=closed(tmp_path)
    out=runtime.execute(job('close_project',project_id='main'))
    assert out['already_closed'] and not out['retired']
    assert 'main' in runtime.state()['projects']


def test_another_registration_prevents_process_retirement(tmp_path):
    runtime,record=closed(tmp_path)
    runtime.update(projects={'main':record,'reference':dict(record,project_id='reference')})
    with pytest.raises(ServiceError,match='shares this file'):
        runtime.execute(job('close_project',**params(record)))
    assert set(runtime.state()['projects'])=={'main','reference'}
