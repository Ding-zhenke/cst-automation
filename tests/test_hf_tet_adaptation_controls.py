import hashlib
import json
from types import SimpleNamespace
import pytest
from cst_solver.mesh.mesh import MeshMixin
from tpc_service.errors import ServiceError
from tpc_service.sessions.model_api import dispatch


def call(adaptation, *, keyword=False):
    return dict(method='configure_tetrahedral_mesh', **(
        {'kwargs': {'settings': {'adaptation': adaptation}}} if keyword else
        {'args': [{'adaptation': adaptation}]}))


def params(calls):
    return dict(project_id='p', stage_id='s', calls=calls,
        preview_digest=hashlib.sha256(json.dumps(calls,sort_keys=True,ensure_ascii=False).encode()).hexdigest())


@pytest.mark.parametrize('level', [0,1,2,3])
@pytest.mark.parametrize('snap', [False,True])
def test_native_controls_are_explicit_sparse_and_unverified(level, snap):
    class App(MeshMixin): pass
    app=App(); history=[]
    app.cst_file=SimpleNamespace(model3d=SimpleNamespace(add_to_history=lambda *a:history.append(a)))
    result=dispatch(app,[call(dict(singular_edge_refinement=level,
        refinement_type='automatic',snap_to_geometry=snap))])
    assert history[0][1].splitlines()==[
        'MeshAdaption3D.SetType "HighFrequencyTet"',
        'MeshAdaption3D.RefinementType "Automatic"',
        f'MeshAdaption3D.SingularEdgeRefinement "{level}"',
        f'MeshAdaption3D.SnapToGeometry {snap}']
    receipt=result['configuration_receipts'][0]['receipt']
    assert not receipt['readback_verified'] and not receipt['mesh_verified']
    assert receipt['warnings'] if level else not receipt['warnings']


BAD=[{'singular_edge_refinement':x,'refinement_type':'automatic'}
     for x in [-1,4,True,False,1.0,'3',None,float('nan'),float('inf')]] + [
    {'singular_edge_refinement':3}, {'refinement_type':'Automatic'},
    {'refinement_type':'manual'}, {'refinement_type':True},
    *[{'snap_to_geometry':x} for x in [0,1,'True',None]]]


@pytest.mark.parametrize('adaptation',BAD)
def test_invalid_batch_never_performs_earlier_native_write(adaptation):
    seen=[]
    app=SimpleNamespace(new_component=lambda name:seen.append(name))
    with pytest.raises(ServiceError):
        dispatch(app,[{'method':'new_component','args':['never']},call(adaptation)])
    assert not seen


@pytest.mark.parametrize('keyword',[False,True])
@pytest.mark.parametrize('mixed',[False,True])
def test_old_worker_refused_before_queue_or_launch(tmp_path,monkeypatch,keyword,mixed):
    from tpc_service.sessions import manager as module
    from tpc_service.sessions.store import read,write
    manager=module.SessionManager(str(tmp_path),backend='fake')
    ref=manager.ensure('tet','tet');folder=tmp_path/ref['session_id'];state=read(folder/'session.json')
    state.update(status='ready',worker={'pid':123},worker_capabilities=[
        'content-bound-settings-history-v1','parameter-em-hb-v1','solver-settings-no-rebuild-v1','mesh-settings-no-rebuild-v1','model-band-no-rebuild-v1'])
    write(folder/'session.json',state)
    monkeypatch.setattr(module,'alive',lambda *a:True)
    monkeypatch.setattr(manager,'_launch',lambda *a:pytest.fail('Must not launch'))
    calls=[call({'snap_to_geometry':True},keyword=keyword)]
    if mixed: calls.insert(0,{'method':'new_component','args':['never']})
    with pytest.raises(ServiceError) as caught:
        manager.submit(ref['session_id'],ref['credential'],'r','model_api',params(calls))
    assert caught.value.code=='workflow_worker_upgrade_required'
    assert not list((folder/'jobs').glob('*.json'))


@pytest.mark.parametrize('valid',[False,True])
def test_registered_mcp_route_validates_and_preserves_controls(tmp_path,monkeypatch,valid):
    from cst_mcp import tools
    from cst_mcp.session_tools import register_session_tools
    from tpc_service.sessions import SessionManager
    for name in ('TOOL_SPECS','HANDLERS','READ_TOOLS','WRITE_TOOLS'):
        old=getattr(tools,name);monkeypatch.setattr(tools,name,old.copy())
    launches=[]
    monkeypatch.setattr(SessionManager,'_launch',lambda *a,**k:launches.append(True))
    register_session_tools(str(tmp_path.resolve()),backend='fake')
    ref=tools.dispatch('ensure_cst_session',{'binding':'tet','request_id':'e'})['session']
    calls=[call({'singular_edge_refinement':3 if valid else 4,
        'refinement_type':'automatic','snap_to_geometry':True})]
    result=tools.dispatch('submit_cst_session_operation',dict(
        session_id=ref['session_id'],credential=ref['credential'],request_id='r',
        operation='model_api',params=params(calls)))
    assert result['ok'] is valid
    if valid:
        assert result['job']['params']['calls']==calls
        assert result['job']['status']=='queued'
    else:
        assert not launches
        assert not list((tmp_path/ref['session_id']/'jobs').glob('*.json'))
