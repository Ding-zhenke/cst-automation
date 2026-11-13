"""Checks for zero-bias SP using the explicitly reviewed native host network."""
import math
import re
from pathlib import Path

from .static_sp import _endpoint,_scalar,_sha


def validate_control_spec(control):
    if not isinstance(control,dict): raise ValueError('Explicit control termination required')
    direct=control.get('kind')=='resistor_to_ground'
    keys=({'kind','network_pin','resistor','resistor_pin','ground','ground_pin','resistance_ohms'} if direct
          else {'network_pin','probe','source','bias','ground','resistance_ohms'})
    names=('resistor','ground') if direct else ('probe','source','bias','ground')
    if (set(control)!=keys or type(control['network_pin']) is not int or control['network_pin']<0
            or any(not isinstance(control[k],str) or not control[k].strip() for k in names)
            or type(control['resistance_ohms']) not in (int,float) or control['resistance_ohms']!=50
            or (direct and (type(control['resistor_pin']) is not int or control['resistor_pin'] not in (0,1)
                            or type(control['ground_pin']) is not int or control['ground_pin']<0))):
        raise ValueError('Explicit 50 ohm control termination required')
    return direct


def validate_native_static(snapshot,spec,task_readback,dependencies,impedance,*,project_path,task_enabled):
    if not isinstance(snapshot,dict) or any(v!={'field':'parameter_dimensions','status':'unknown'}
            for v in snapshot.get('unknown',[])):
        raise ValueError('Complete native circuit snapshot required')
    if not isinstance(spec,dict) or set(spec)!={'host_block','host_pins','task','expected_nets','control','diode_blocks'}:
        raise ValueError('Explicit host, port map, task and reviewed nets required')
    blocks=snapshot.get('blocks')
    if not isinstance(blocks,list): raise ValueError('Complete block inventory required')
    names={b.get('name'):b for b in blocks}
    if len(names)!=len(blocks): raise ValueError('Unique block names required')
    host=names.get(spec['host_block']) or {};project=Path(project_path).resolve()
    host_blocks=[b for b in blocks if 'microwave studio' in str(b.get('type','')).casefold()]
    if (len(host_blocks)!=1 or host_blocks[0]!=host
            or str(host.get('type','')).casefold()!='cst microwave studio schematic block'
            or len(host.get('files',[]))!=1 or Path(host['files'][0]).resolve()!=project
            or host.get('pins')!=spec['host_pins']):
        raise ValueError('Exact native self-host and port mapping required')
    allowed={'ground','spice block','touchstone block','voltage signal source','voltage dc source',
             'current signal source','current dc source','diode','resistor','capacitor','inductor'}
    if any(b is not host and str(b.get('type','')).casefold() not in allowed for b in blocks):
        raise ValueError('Unsupported circuit block or unreviewed native dependency')
    if snapshot.get('nets')!=spec['expected_nets']:
        raise ValueError('Native circuit connections differ from reviewed mapping')
    nets=snapshot['nets'];seen=set();host_connected=False
    for net in nets:
        parts=net.get('subnets')
        if not isinstance(parts,list) or not parts: raise ValueError('Complete net membership required')
        endpoints=[_endpoint(value) for part in parts for value in part]
        if not endpoints or len(endpoints)!=len(set(endpoints)) or seen.intersection(endpoints):
            raise ValueError('Ambiguous net membership')
        seen.update(endpoints)
        host_connected|=any(x[0]=='block' and x[1]==spec['host_block'] for x in endpoints)
    if not host_connected: raise ValueError('Native host is not connected to reviewed circuit')
    diodes=spec['diode_blocks']
    if (not isinstance(diodes,list) or not diodes or len(set(diodes))!=len(diodes)
            or any(not isinstance(n,str) or not n or str(names.get(n,{}).get('type','')).casefold() not in ('spice block','diode') for n in diodes)):
        raise ValueError('Explicit existing diode blocks required')
    if set(diodes)!={b['name'] for b in blocks if str(b.get('type','')).casefold() in ('spice block','diode')}:
        raise ValueError('Complete reviewed diode/SPICE block inventory required')
    for diode in diodes:
        connected=[row for row in nets if any(_endpoint(v)[:2]==('block',diode) for part in row['subnets'] for v in part)]
        if len(connected)<2:
            raise ValueError('Each reviewed diode requires at least two connected nets')
    control=spec['control'];direct=validate_control_spec(control)
    net_members=[frozenset(_endpoint(v) for part in row['subnets'] for v in part) for row in nets]
    if direct:
        resistor=names.get(control['resistor'],{});ground=names.get(control['ground'],{})
        pins=resistor.get('pins')
        unit=resistor.get('property_metadata',{}).get('Resistance',{}).get('unit') or snapshot.get('units',{}).get('Resistance')
        if (str(resistor.get('type','')).casefold()!='resistor' or str(ground.get('type','')).casefold()!='ground'
                or not isinstance(pins,list) or len(pins)!=2 or {p.get('port_index') for p in pins}!={0,1}
                or unit!='Ohm' or not math.isclose(_scalar(resistor.get('properties',{}).get('Resistance'),
                    snapshot.get('parameters',{})),50,rel_tol=1e-12,abs_tol=0)):
            raise ValueError('Native 50 ohm resistor or ground differs')
        chain=[(('block',spec['host_block'],control['network_pin']),('block',control['resistor'],control['resistor_pin'])),
               (('block',control['resistor'],1-control['resistor_pin']),('block',control['ground'],control['ground_pin']))]
    else:
        source=names.get(control['source'],{});bias=names.get(control['bias'],{});ground=names.get(control['ground'],{})
        if (str(source.get('type','')).casefold()!='voltage signal source'
                or str(bias.get('type','')).casefold()!='voltage dc source'
                or str(ground.get('type','')).casefold()!='ground'):
            raise ValueError('Control termination block types differ')
        for block,want in ((source,50),(bias,0)):
            if (block.get('property_metadata',{}).get('Ri',{}).get('unit')!='Ohm'
                    or not math.isclose(_scalar(block.get('properties',{}).get('Ri'),snapshot.get('parameters',{})),want,rel_tol=1e-12,abs_tol=0)):
                raise ValueError('Control resistance differs')
        chain=[(('block',spec['host_block'],control['network_pin']),('probe',control['probe'],1)),
               (('probe',control['probe'],0),('block',control['source'],0)),
               (('block',control['source'],1),('block',control['bias'],0)),
               (('block',control['bias'],1),('block',control['ground'],0))]
    for i,(a,b) in enumerate(chain):
        matches=[members for members in net_members if a in members and b in members]
        if len(matches)!=1 or (i<len(chain)-1 and matches[0]!=frozenset((a,b))):
            raise ValueError('Control termination topology differs')
    for block in blocks:
        kind=str(block.get('type','')).casefold()
        block_files=block.get('files')
        if not isinstance(block_files,list): raise ValueError('Complete block-file inventory required')
        if kind=='spice block' and (not block_files or any(Path(f).suffix.casefold() not in ('.cir','.lib','.sp','.spice','.mod') for f in block_files)):
            raise ValueError('SPICE file dependency missing or unsupported')
        if kind=='touchstone block' and (len(block_files)!=1 or not re.fullmatch(r'\.s\d+p',Path(block_files[0]).suffix.casefold())):
            raise ValueError('Touchstone file dependency missing or unsupported')
        if block is not host and kind not in ('spice block','touchstone block') and block_files:
            raise ValueError('Unexpected file dependency on intrinsic block')
        if 'source' not in kind: continue
        if kind in ('voltage dc source','current dc source'): fields=('DC',)
        elif kind in ('voltage signal source','current signal source'): fields=('ACAmplitude','HBAmplitude')
        else: raise ValueError('Unsupported independent source type')
        if any(_scalar(block.get('properties',{}).get(field),snapshot.get('parameters',{}))!=0 for field in fields):
            raise ValueError('All independent DC and pump amplitudes must be zero')
    task=spec['task'];name=task['task_name'];matches=[t for t in snapshot.get('tasks',[]) if t.get('name')==name]
    if (len(matches)!=1 or str(matches[0].get('type','')).casefold()!='s-parameters' or task_enabled is not True
            or any(str(t.get('name','')).startswith(name+'\\') for t in snapshot.get('tasks',[]))):
        raise ValueError('Enabled S-parameter leaf task required')
    external=snapshot.get('external_ports',[]);wanted=task['port_impedances']
    if len(external)!=len(wanted) or {p.get('name') for p in external}!=set(wanted):
        raise ValueError('Exact measurement ports required')
    measurement_nets=[]
    for port_name in wanted:
        matches=[members for members in net_members if ('externalport',port_name,0) in members]
        if len(matches)!=1 or len(matches[0])<2:
            raise ValueError('Each measurement port needs one connected native net')
        measurement_nets.append(matches[0])
    if measurement_nets[0]==measurement_nets[1]:
        raise ValueError('Measurement ports must use distinct native nets')
    props=task_readback.get('properties',{});ports=task_readback.get('ports',{})
    if (task_readback.get('task_name')!=name or task_readback.get('frequency_unit')!=task['frequency_unit']
            or task_readback.get('resistance_unit')!='Ohm' or str(props.get('circuit simulator','')).casefold()!='cst'
            or any(str(props.get(k,'')).casefold()!='false' for k in ('maximum frequency range','broadband sweep','logarithmic sweep'))
            or not math.isclose(float(props.get('fmin','nan')),task['fmin'],rel_tol=1e-10,abs_tol=0)
            or not math.isclose(float(props.get('fmax','nan')),task['fmax'],rel_tol=1e-10,abs_tol=0)
            or set(ports)!=set(wanted) or any(str(p.get('impedance_type','')).casefold()!='constant' for p in ports.values())):
        raise ValueError('Native task settings or port modes differ')
    actual=impedance.get('ports',{})
    if set(actual)!=set(wanted) or any(str(actual[n].get('impedance_type','')).casefold()!='constant'
            or not math.isclose(float(actual[n].get('real','nan')),value,rel_tol=1e-10,abs_tol=0)
            or not math.isclose(float(actual[n].get('imaginary','nan')),0,rel_tol=0,abs_tol=1e-12)
            for n,value in wanted.items()):
        raise ValueError('Numerical port impedances differ')
    if dependencies.get('complete') is not True or dependencies.get('unknown'):
        raise ValueError('Complete dependency inventory required')
    files={}
    for row in dependencies.get('files',[]):
        path=Path(row['path']).resolve()
        if path!=project and path.suffix.casefold()=='.cst': raise ValueError('External 3D project dependency not supported')
        if path in files or not row.get('exists') or not row.get('sha256') or _sha(path)!=row['sha256']:
            raise ValueError('Dependency missing or changed')
        files[path]=row['sha256']
    if project not in files or any(Path(f).resolve() not in files for block in blocks for f in block.get('files',[])):
        raise ValueError('Project or block file missing from dependency inventory')
    return {'native_host_present':True,'control_50_verified':True,'diode_model_verified':False,
            'em_reuse_verified':False,'solver_verified':False}
