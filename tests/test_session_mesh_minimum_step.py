from types import SimpleNamespace
from cst_solver.mesh.mesh import MeshMixin

def test_lower_mesh_limit_argument_emits_native_minimum_step_number():
    history=[]
    app=MeshMixin()
    app.cst_file=SimpleNamespace(model3d=SimpleNamespace(add_to_history=lambda name,code:history.append(code)))
    app.set_mesh_auto(lower_mesh_limit=20)
    assert '.MinimumStepNumber "20"' in history[0]
    assert '.LowerMeshLimit' not in history[0]


def test_mesh_requires_corrected_worker_capability(tmp_path):
    import pytest
    from tpc_service.errors import ServiceError
    from tpc_service.sessions.operations import execute
    runtime=SimpleNamespace(folder=tmp_path,backend='cst',state=lambda:{'worker_capabilities':['td-em-settings-v1']},project=lambda *_:pytest.fail('project accessed'))
    job={'operation':'model_api','params':{'project_id':'p','calls':[{'method':'set_mesh_auto'}]}}
    with pytest.raises(ServiceError) as exc: execute(runtime,job)
    assert exc.value.code=='workflow_worker_upgrade_required'
