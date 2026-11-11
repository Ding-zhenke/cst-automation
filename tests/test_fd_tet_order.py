import hashlib
import json
from types import SimpleNamespace
import pytest
from cst_automation.fd_linear import linear_solver_code
from cst_solver.simulation.solver import SolverMixin
from tpc_service.errors import ServiceError
from tpc_service.sessions.model_api import dispatch

@pytest.mark.parametrize('order',['First','Second','Third'])
@pytest.mark.parametrize('mixed',[False,True])
def test_tet_order_sparse_commands_and_unverified_receipt(order,mixed):
    history=[]
    class App(SolverMixin):pass
    app=App();app.cst_file=SimpleNamespace(model3d=SimpleNamespace(add_to_history=lambda *a:history.append(a)))
    result=dispatch(app,[{'method':'configure_fd_linear_solver','kwargs':{'settings':{'tet_order':order,'mixed_order':mixed}}}])
    assert history[0][1].splitlines()==['With FDSolver',f' .OrderTet "{order}"',f' .MixedOrderTet "{mixed}"','End With']
    receipt=result['configuration_receipts'][0]['receipt']
    assert not receipt['readback_verified'] and not receipt['result_preservation_verified']

@pytest.mark.parametrize('settings',[
    *[{'tet_order':x} for x in [None,1,2,True,'second','Fourth','Second"\n.Start']],
    *[{'tet_order':'Second','mixed_order':x} for x in [None,0,1,'True']],
    {'mixed_order':True}])
def test_bad_order_rejected_before_entire_batch(settings):
    app=SimpleNamespace(new_component=lambda *a:pytest.fail('No earlier native write'))
    with pytest.raises(ServiceError):dispatch(app,[{'method':'new_component','args':['bad']},
        {'method':'configure_fd_linear_solver','args':[settings]}])

@pytest.mark.parametrize('setting',[{'tet_order':'Second','mixed_order':True},{'tet_order':'First'},{'mixed_order':False}])
@pytest.mark.parametrize('keyword',[False,True])
@pytest.mark.parametrize('mixed',[False,True])
def test_old_worker_refuses_tet_order_before_queue(tmp_path,monkeypatch,keyword,mixed,setting):
    from tpc_service.sessions import manager as module
    from tpc_service.sessions.store import read,write
    m=module.SessionManager(str(tmp_path),backend='fake');r=m.ensure('tetorder','one');f=tmp_path/r['session_id']
    s=read(f/'session.json');s.update(status='ready',worker={'pid':123},worker_capabilities=['solver-settings-no-rebuild-v1'])
    write(f/'session.json',s);monkeypatch.setattr(module,'alive',lambda *a:True)
    monkeypatch.setattr(m,'_launch',lambda *a:pytest.fail('No launch'))
    calls=[dict(method='configure_fd_linear_solver',**({'kwargs':{'settings':setting}} if keyword else {'args':[setting]}))]
    if mixed:calls.insert(0,{'method':'new_component','args':['never']})
    params=dict(project_id='p',stage_id='tet',calls=calls,preview_digest=hashlib.sha256(json.dumps(calls,sort_keys=True,ensure_ascii=False).encode()).hexdigest())
    with pytest.raises(ServiceError) as error:m.submit(r['session_id'],r['credential'],'r','model_api',params)
    assert error.value.code=='workflow_worker_upgrade_required'
    assert not list((f/'jobs').glob('*.json'))

def test_sparse_disable_mixed_does_not_reset_order():
    assert linear_solver_code({'mixed_order':False})=='With FDSolver\n .MixedOrderTet "False"\nEnd With'

@pytest.mark.parametrize('keyword',[False,True])
def test_execute_rechecks_order_capability_before_project_access(tmp_path,keyword):
    from tpc_service.sessions.operations import execute
    setting={'tet_order':'Second','mixed_order':True}
    call=dict(method='configure_fd_linear_solver',**({'kwargs':{'settings':setting}} if keyword else {'args':[setting]}))
    runtime=SimpleNamespace(folder=tmp_path,backend='cst',state=lambda:{'worker_capabilities':[]},
        project=lambda *a:pytest.fail('No native acquisition'))
    job={'operation':'model_api','params':{'project_id':'p','calls':[call]}}
    with pytest.raises(ServiceError) as error:execute(runtime,job)
    assert error.value.code=='workflow_worker_upgrade_required'
    assert job['workflow_preflight_rejected'] is True

@pytest.mark.parametrize('valid',[False,True])
def test_mcp_order_settings_share_typed_guard(tmp_path,monkeypatch,valid):
    from cst_mcp import tools
    from cst_mcp.session_tools import register_session_tools
    from tpc_service.sessions import SessionManager
    for name in ('TOOL_SPECS','HANDLERS','READ_TOOLS','WRITE_TOOLS'):
        monkeypatch.setattr(tools,name,getattr(tools,name).copy())
    monkeypatch.setattr(SessionManager,'_launch',lambda *a,**k:None)
    register_session_tools(str(tmp_path.resolve()),backend='fake')
    r=tools.dispatch('ensure_cst_session',{'binding':'order','request_id':'e'})['session']
    calls=[{'method':'configure_fd_linear_solver','args':[{'tet_order':'Second','mixed_order':True if valid else 'True'}]}]
    p=dict(project_id='p',stage_id='order',calls=calls,preview_digest=hashlib.sha256(json.dumps(calls,sort_keys=True,ensure_ascii=False).encode()).hexdigest())
    result=tools.dispatch('submit_cst_session_operation',dict(session_id=r['session_id'],credential=r['credential'],
        request_id='r',operation='model_api',params=p))
    assert result['ok'] is valid
    if valid:assert result['job']['params']['calls']==calls
    else:assert not list((tmp_path/r['session_id']/'jobs').glob('*.json'))


def test_order_only_preserves_mixed_setting():
    assert linear_solver_code({"tet_order":"First"}) == 'With FDSolver\n .OrderTet "First"\nEnd With'
