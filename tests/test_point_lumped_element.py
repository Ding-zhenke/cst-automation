from types import SimpleNamespace

import pytest


def test_point_lumped_element_uses_named_native_type_and_explicit_points():
    from cst_solver import setup
    history=[];app=object.__new__(setup)
    app.cst_file=SimpleNamespace(model3d=SimpleNamespace(add_to_history=lambda name,code:history.append((name,code))))
    app.create_point_lumped_element('RTERM50',r=50,p1=[0,0,'h'],p2=[0,0,0])
    code=history[0][1]
    assert 'With LumpedElement' in code and 'LumpedFaceElement' not in code
    assert '.SetName "RTERM50"' in code and '.SetType "RLCSerial"' in code
    assert '.SetP1 False, "0", "0", "h"' in code and '.SetP2 False, "0", "0", "0"' in code
    assert '.SetR "50"' in code


@pytest.mark.parametrize('name,p1',[('x"\nSolver.Start',[0,0,1]),('R',[0,0,'1\nSolver.Start'])])
def test_point_lumped_invalid_input_rejected_before_native(name,p1):
    from cst_solver.simulation.lumped_elements import point_lumped_command
    with pytest.raises(ValueError): point_lumped_command(name,r=50,p1=p1,p2=[0,0,0])


def test_read_lumped_element_uses_native_coordinates_and_properties():
    from cst_solver.simulation.lumped_elements import read_lumped_elements
    native=SimpleNamespace(GetCoordinates=lambda name:(True,0,1,2,3,4,5),
                           GetProperties=lambda name:(True,'RLCSerial',50,0,0,0,0,0,0))
    app=SimpleNamespace(cst_file=SimpleNamespace(model3d=SimpleNamespace(LumpedElement=native)))
    result=read_lumped_elements(app,['RTERM50'])['RTERM50']
    assert result['start']==[0,1,2] and result['end']==[3,4,5]
    assert result['properties']['resistance_ohms']==50 and result['properties']['type']=='RLCSerial'


def test_unreadable_lumped_element_is_not_claimed_as_verified():
    from cst_solver.simulation.lumped_elements import read_lumped_elements
    native=SimpleNamespace(GetCoordinates=lambda name:True)
    app=SimpleNamespace(cst_file=SimpleNamespace(model3d=SimpleNamespace(LumpedElement=native)))
    with pytest.raises(ValueError): read_lumped_elements(app,['RTERM50'])


def test_point_element_is_exposed_through_validated_session_routes():
    from tpc_service.sessions.model_api import validate_calls
    from tpc_service.sessions.inspection import validate_options
    validate_calls([{'method':'create_point_lumped_element','args':['RTERM50'],
                    'kwargs':{'r':50,'p1':[0,0,1],'p2':[0,0,0]}}])
    validate_options({'project_id':'p','native_readback':True,'read_only_review':True,'confirm_idle':True,
                      'expected_digest':'a'*64,'lumped_element_names':['RTERM50']})
    with pytest.raises(Exception):
        validate_options({'project_id':'p','lumped_element_names':['RTERM50']})


def test_project_bound_lumped_byref_receipt_preserves_values_and_identity(tmp_path):
    from cst_automation.lumped_element_bridge import build_query,parse_receipt
    project=tmp_path/'model.cst';project.write_bytes(b'project')
    request=build_query(project,['RTERM50'],receipt_root=tmp_path/'queries')
    code=request['vba_code']
    assert 'LumpedElement.GetCoordinates' in code and 'LumpedElement.GetProperties' in code
    assert 'Solver.Start' not in code
    text='CST_LUMPED_V1\nrequest\t'+request['request_id']+'\ncount\t1\n'
    text+='item\t0\tRLCSerial\t0\t1\t2\t3\t4\t5\t50\t0\t0\t0\t0\t0\t0\nEND\t'+request['request_id']+'\n'
    report=parse_receipt(text.encode('ascii'),request=request)
    assert report['elements']['RTERM50']['start']==[0,1,2]
    assert report['elements']['RTERM50']['properties']['resistance_ohms']==50
    with pytest.raises(ValueError): parse_receipt(text.replace(request['request_id'],'wrong',1).encode('ascii'),request=request)


def test_lumped_bridge_requires_owned_project_and_idle(tmp_path,monkeypatch):
    import json
    from pathlib import Path
    from cst_solver.simulation.lumped_elements import read_lumped_elements_via_bridge
    from cst_solver import native
    project=tmp_path/'model.cst';project.write_bytes(b'project')
    handle=SimpleNamespace(filename=lambda:str(project))
    def execute(project,code,**kwargs):
        manifest=next((tmp_path/'queries').glob('*.request.json'))
        req=json.loads(manifest.read_text(encoding='utf-8'));token=req['request_id']
        content='CST_LUMPED_V1\nrequest\t'+token+'\ncount\t1\nitem\t0\tRLCSerial\t0\t0\t1\t0\t0\t0\t50\t0\t0\t0\t0\t0\t0\nEND\t'+token+'\n'
        Path(req['output_path']).write_text(content,encoding='ascii')
    monkeypatch.setattr(native,'execute_vba',execute)
    report=read_lumped_elements_via_bridge(handle,['RTERM50'],expected_project_path=project,
                                           receipt_root=tmp_path/'queries',confirm_idle=True)
    assert report['elements']['RTERM50']['properties']['resistance_ohms']==50
    assert report['native_bridge_verified'] is False
    with pytest.raises(ValueError):
        read_lumped_elements_via_bridge(handle,['RTERM50'],expected_project_path=project,
                                        receipt_root=tmp_path/'queries',confirm_idle=False)
