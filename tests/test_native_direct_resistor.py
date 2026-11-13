import copy

import pytest

from test_native_static_gate import setup_native


def direct_setup(tmp_path, monkeypatch):
    snapshot,spec,task,deps,impedance,project=setup_native(tmp_path,monkeypatch)
    snapshot['blocks']=[b for b in snapshot['blocks'] if b['name'] not in ('P','B','SL','SR')]
    snapshot['blocks'].append({'name':'R50','type':'Resistor','properties':{'Resistance':'50'},
                               'pins':[{'port_index':0},{'port_index':1}],'files':[]})
    snapshot['nets']=[row for row in snapshot['nets'] if row['name'] not in ('C','CS','B','G','LS','RS')]
    snapshot['nets'].extend([
        {'name':'control','subnets':[[['Block','N',2],['Block','R50',0]]]},
        {'name':'ground','subnets':[[['Block','R50',1],['Block','G',0],['Block','D',1]]]}
    ])
    snapshot['units']['Resistance']='Ohm'
    spec['expected_nets']=copy.deepcopy(snapshot['nets'])
    spec['control']={'kind':'resistor_to_ground','network_pin':2,'resistor':'R50','resistor_pin':0,
                     'ground':'G','ground_pin':0,'resistance_ohms':50}
    return snapshot,spec,task,deps,impedance,project


def test_direct_resistor_control_matches_reviewed_native_topology(tmp_path,monkeypatch):
    from cst_solver.circuit.native_static_gate import validate_native_static
    snapshot,spec,task,deps,impedance,project=direct_setup(tmp_path,monkeypatch)
    report=validate_native_static(snapshot,spec,task,deps,impedance,project_path=project,task_enabled=True)
    assert report['native_host_present'] and report['control_50_verified']
    assert not report['diode_model_verified'] and not report['solver_verified']


def test_direct_resistor_prepare_never_creates_or_changes_source_blocks(tmp_path,monkeypatch):
    from pathlib import Path
    from types import SimpleNamespace
    from cst_solver import dialogs
    from cst_solver.circuit import adapter,linear_sp,native as bridge
    from tpc_service.sessions import workflow
    from tpc_service.sessions.store import digest
    from test_native_static_run import setup_case
    (tmp_path/'base').mkdir();(tmp_path/'direct').mkdir()
    native,state,params,*_=setup_case(tmp_path/'base',monkeypatch)
    snapshot,spec,task,deps,impedance,project=direct_setup(tmp_path/'direct',monkeypatch)
    state['projects']['p']['path']=project
    params.pop('sample_observation');params.update(spec=spec,snapshot_digest=digest(snapshot))
    model=Path(project).with_suffix('')/'Model'/'3D';model.mkdir(parents=True);(model/'model.dat').write_bytes(b'model')
    obj=SimpleNamespace(inspect=lambda:copy.deepcopy(snapshot),schematic=SimpleNamespace(),dependencies=lambda:deps,
        select=lambda kind,name:SimpleNamespace(GetProperty=lambda key:'True',SetProperty=lambda *a:None)
            if kind=='SimulationTask' else pytest.fail('no source block changes expected'))
    handle=SimpleNamespace(filename=lambda:project,model3d=SimpleNamespace(is_solver_running=lambda **kw:False))
    app=SimpleNamespace(cst_file=handle)
    runtime=SimpleNamespace(folder=tmp_path,backend='cst',app=app,handles={'p':handle},state=lambda:state,
        check_saved=lambda p:None,save=lambda app,pid:{'saved_digest':params['expected_saved_digest']})
    monkeypatch.setattr(native,'preflight',lambda *a,**kw:{'em_generation':3})
    monkeypatch.setattr(dialogs,'check_dialogs',lambda **kw:None)
    monkeypatch.setattr(adapter,'NativeAdapter',lambda app:obj)
    monkeypatch.setattr(linear_sp,'inspect_existing_linear_sp',lambda *a:task)
    monkeypatch.setattr(linear_sp,'complete_existing_linear_sp_task',lambda *a,**kw:{'sample_count_readback':'unsupported'})
    monkeypatch.setattr(bridge,'read_project_sp_impedances',lambda *a,**kw:impedance)
    monkeypatch.setattr(workflow,'live_checks',lambda *a:None)
    monkeypatch.setattr(workflow,'invalidate',lambda *a:None)
    result=native.prepare(runtime,{'job_id':'prepare','operation':'prepare_native_static_sp','params':params})
    assert result['changes']==[] and result['control_50_verified'] and result['saved']
    assert not result['solver_verified']


@pytest.mark.parametrize('fault',['resistance','unit','extra_branch','wrong_ground','wrong_pin','bad_target'])
def test_direct_resistor_control_rejects_incorrect_physical_path(tmp_path,monkeypatch,fault):
    from cst_solver.circuit.native_static_gate import validate_native_static
    snapshot,spec,task,deps,impedance,project=direct_setup(tmp_path,monkeypatch)
    if fault=='resistance': next(b for b in snapshot['blocks'] if b['name']=='R50')['properties']['Resistance']='75'
    if fault=='unit': snapshot['units']['Resistance']='kOhm'
    if fault=='extra_branch': snapshot['nets'][-2]['subnets'][0].append(['Block','D',0]);spec['expected_nets']=copy.deepcopy(snapshot['nets'])
    if fault=='wrong_ground': spec['control']['ground']='missing'
    if fault=='wrong_pin': spec['control']['resistor_pin']=1
    if fault=='bad_target': spec['control']['resistance_ohms']=75
    with pytest.raises(ValueError): validate_native_static(snapshot,spec,task,deps,impedance,project_path=project,task_enabled=True)
