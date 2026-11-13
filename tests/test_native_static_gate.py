import copy
from pathlib import Path

import pytest

from test_static_sp_network_gate import setup_gate


def setup_native(tmp_path,monkeypatch):
    snapshot,spec,task,deps,impedance,project=setup_gate(tmp_path,monkeypatch)
    host=next(b for b in snapshot['blocks'] if b['name']=='N')
    host.update(type='CST MICROWAVE STUDIO schematic block',files=[project])
    next(row for row in snapshot['nets'] if row['name']=='G')['subnets'][0].append(['Block','D',1])
    deps['files']=[row for row in deps['files'] if Path(row['path']).suffix.lower()!='.s4p']
    request={'host_block':'N','host_pins':[{'pin_name':str(i+1),'port_index':i} for i in range(4)],
             'task':copy.deepcopy(spec['task']),'expected_nets':copy.deepcopy(snapshot['nets']),
             'control':copy.deepcopy(spec['control']), 'diode_blocks':['D']}
    host['pins']=copy.deepcopy(request['host_pins'])
    return snapshot,request,task,deps,impedance,project


def test_qualified_host_block_is_accepted_without_claiming_em_reuse(tmp_path,monkeypatch):
    from cst_solver.circuit.native_static_gate import validate_native_static
    snapshot,request,task,deps,impedance,project=setup_native(tmp_path,monkeypatch)
    result=validate_native_static(snapshot,request,task,deps,impedance,project_path=project,task_enabled=True)
    assert result['native_host_present'] and result['em_reuse_verified'] is False


@pytest.mark.parametrize('fault',['changed_mapping','source','child','other_project','impedance','net','control','missing_diode'])
def test_native_static_rejects_unreviewed_or_nonzero_conditions(tmp_path,monkeypatch,fault):
    from cst_solver.circuit.native_static_gate import validate_native_static
    snapshot,request,task,deps,impedance,project=setup_native(tmp_path,monkeypatch)
    if fault=='changed_mapping': request['host_pins'][0]['port_index']=9
    if fault=='source': next(b for b in snapshot['blocks'] if b['name']=='P')['properties']['ACAmplitude']='1'
    if fault=='child': snapshot['tasks'].append({'name':'SP\\EM','type':'block simulation'})
    if fault=='other_project': snapshot['blocks'].append({'name':'other','type':'CST MICROWAVE STUDIO schematic block','files':['other.cst'],'pins':[]})
    if fault=='impedance': impedance['ports']['A']['real']=50
    if fault=='net': snapshot['nets'][0]['subnets'][0].append(['Block','D',1])
    if fault=='control': next(b for b in snapshot['blocks'] if b['name']=='P')['properties']['Ri']='75'
    if fault=='missing_diode': request['diode_blocks']=['missing']
    with pytest.raises(ValueError):
        validate_native_static(snapshot,request,task,deps,impedance,project_path=project,task_enabled=True)
