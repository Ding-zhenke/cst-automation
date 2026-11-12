import copy
import hashlib
from pathlib import Path
import pytest
from cst_solver.circuit.static_sp import prepare_static_sp
from cst_solver.circuit.static_sp_gate import validate_static_network
from test_static_sp_prepare import fixture


def setup_gate(tmp_path,monkeypatch):
    adapter,spec=fixture(tmp_path,monkeypatch)
    prepare_static_sp(adapter,spec)
    snapshot=adapter.inspect()
    network=next(b for b in snapshot['blocks'] if b['name']=='N')
    network['pins']=[{'port_index':i} for i in range(4)]
    path=__import__('pathlib').Path(network['files'][0]);row=' '.join(['0']*32)
    path.write_text('# Hz S RI R 50\n'+'\n'.join(f'{v} {row}' for v in (0,110000000000,170000000000)),encoding='ascii')
    spec['network_sha256']=hashlib.sha256(path.read_bytes()).hexdigest()
    diode=next(b for b in snapshot['blocks'] if b['name']=='D');diode['type']='SPICE block'
    spice=tmp_path/'diode.cir';spice.write_text('.model d D\n',encoding='ascii');diode['files']=[str(spice)]
    project=tmp_path/'device.cst'
    deps={'complete':True,'unknown':[],'files':[{'path':str(p),'exists':True,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
        for p in (project,path,spice)]}
    task={'task_name':'SP','properties':{'maximum frequency range':'false','circuit simulator':'cst',
        'broadband sweep':'false','logarithmic sweep':'false','fmin':'110','fmax':'170'},
        'ports':{'A':{'impedance_type':'Constant','source_type':'unsupported'},'Z':{'impedance_type':'Constant','source_type':'unsupported'}},
        'frequency_unit':'GHz','resistance_unit':'Ohm'}
    impedance={'ports':{'A':{'real':100,'imaginary':0,'impedance_type':'Constant'},
                        'Z':{'real':100,'imaginary':0,'impedance_type':'Constant'}}}
    return snapshot,spec,task,deps,impedance,str(project)


def test_static_network_gate_accepts_only_pure_leaf_with_matching_loads(tmp_path,monkeypatch):
    snapshot,spec,task,deps,impedance,project=setup_gate(tmp_path,monkeypatch)
    report=validate_static_network(snapshot,spec,task,deps,impedance,project_path=project,task_enabled=True)
    assert report['structural_no_em_dependency_verified'] and not report['solver_verified']
    assert report['network_coverage']['fmax_hz']==170e9


@pytest.mark.parametrize('fault',['self_mws','child','source','port','control','impedance','dependency','task','network_hash','disabled','extra_port','missing_dc','wrong_block_file'])
def test_static_network_gate_refuses_invalid_or_3d_dependent_circuits(tmp_path,monkeypatch,fault):
    snapshot,spec,task,deps,impedance,project=setup_gate(tmp_path,monkeypatch)
    if fault=='self_mws': snapshot['blocks'].append({'name':'mws','type':'CST MICROWAVE STUDIO schematic block','files':[]})
    if fault=='child': snapshot['tasks'].append({'name':'SP\\child','type':'block simulation'})
    if fault=='source': next(b for b in snapshot['blocks'] if b['name']=='P')['properties']['ACAmplitude']='1'
    if fault=='port': snapshot['nets'][0]['subnets'][0].append(['Block','D',1])
    if fault=='control': next(b for b in snapshot['blocks'] if b['name']=='P')['properties']['Ri']='75'
    if fault=='impedance': impedance['ports']['A']['real']=50
    if fault=='dependency': deps['files'].append({'path':str(tmp_path/'other.cst'),'exists':True,'sha256':'a'*64})
    if fault=='task': task['properties']['circuit simulator']='cosimulation'
    if fault=='network_hash': spec['network_sha256']='0'*64
    if fault=='extra_port': snapshot['external_ports'].append({'name':'unexpected'})
    if fault=='wrong_block_file': next(b for b in snapshot['blocks'] if b['name']=='D')['files']=[project]
    if fault=='missing_dc':
        path=Path(next(b for b in snapshot['blocks'] if b['name']=='N')['files'][0])
        lines=path.read_text(encoding='ascii').splitlines();path.write_text('\n'.join([lines[0]]+lines[2:]),encoding='ascii')
        spec['network_sha256']=hashlib.sha256(path.read_bytes()).hexdigest()
        next(f for f in deps['files'] if Path(f['path'])==path)['sha256']=spec['network_sha256']
    with pytest.raises(ValueError): validate_static_network(snapshot,spec,task,deps,impedance,project_path=project,task_enabled=fault!='disabled')
