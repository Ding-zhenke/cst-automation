import hashlib
from pathlib import Path
from types import SimpleNamespace
import pytest

from tpc_service.sessions.operations import execute
from tpc_service.sessions.validation import validate


def payload(domain):
    code = 'SimulationTask.Reset'
    return dict(project_id='p',stage_id='schematic-stage',name='schematic stage',
                vba=code,domain=domain,preview_digest=hashlib.sha256(code.encode()).hexdigest())


def test_invalid_history_domain_is_rejected_before_queue_acceptance():
    with pytest.raises(Exception,match='domain'):
        validate('history',payload('active-window'))


def test_schematic_history_uses_owned_schematic_and_does_not_rebuild_3d(tmp_path):
    events=[]
    class Runtime:
        backend='cst'
        folder=tmp_path
        def project(self,project_id):
            assert project_id=='p'
            return SimpleNamespace(cst_file=SimpleNamespace(
                schematic=SimpleNamespace(execute_vba_code=lambda code,**kw: events.append(('schematic',code))),
                model3d=SimpleNamespace(add_to_history=lambda *a: pytest.fail('3D routing'))),
                validate_model=lambda: pytest.fail('unrelated 3D rebuild')),{}
        def save(self,app,project_id):
            events.append(('save',project_id));return {'saved_digest':'test'}
    params=payload('schematic')
    result=execute(Runtime(),dict(operation='history',params=params,job_id='j',operation_id='o',fingerprint='f'))
    assert events==[('schematic','Sub Main\nSimulationTask.Reset\nEnd Sub'),('save','p')]
    assert result['saved'] and result['domain']=='schematic'
    assert result['geometry_validation'] is None
    assert not result['solver_verified']


def test_default_history_still_uses_modeler_and_rebuild(tmp_path):
    events=[]
    class Runtime:
        backend='cst'
        folder=tmp_path
        def project(self,project_id):
            return SimpleNamespace(cst_file=SimpleNamespace(
                model3d=SimpleNamespace(add_to_history=lambda *a: events.append(('3d',a)))),
                validate_model=lambda: events.append(('rebuild',)) or {'status':'success','rebuild_ok':True}),{}
        def save(self,app,project_id):return {'saved_digest':'test'}
    params=payload('model3d');params.pop('domain')
    execute(Runtime(),dict(operation='history',params=params,job_id='j',operation_id='o',fingerprint='f'))
    assert events==[('3d',('schematic stage','SimulationTask.Reset')),('rebuild',)]
