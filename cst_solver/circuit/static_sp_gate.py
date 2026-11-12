"""Observable no-3D-dependency checks for an explicitly prepared static circuit."""
import math
import re
from pathlib import Path
from cst_automation.em_network import touchstone
from .static_sp import _endpoint, _scalar, _sha, validate_prepare_spec


def validate_static_network(snapshot,spec,task_readback,dependencies,impedance,*,project_path,task_enabled):
    """Check the supported pure-circuit leaf; no CST connection or solve is made."""
    validate_prepare_spec(spec)
    if not isinstance(snapshot,dict) or any(u!={'field':'parameter_dimensions','status':'unknown'} for u in snapshot.get('unknown',[])):
        raise ValueError('Complete native circuit snapshot required')
    allowed={'ground','spice block','touchstone block','voltage signal source','voltage dc source',
             'current signal source','current dc source'}
    blocks=snapshot.get('blocks')
    if not isinstance(blocks,list) or any(not isinstance(b,dict) or str(b.get('type','')).casefold() not in allowed for b in blocks):
        raise ValueError('Unsupported block or potential 3D dependency')
    by_name={b['name']:b for b in blocks}
    if len(by_name)!=len(blocks) or sum(str(b['type']).casefold()=='touchstone block' for b in blocks)!=1:
        raise ValueError('Unique circuit block and network inventory required')
    network=by_name.get(spec['network_block']) or {}
    if str(network.get('type','')).casefold()!='touchstone block':
        raise ValueError('Original embedded network required')
    for block in blocks:
        kind=str(block['type']).casefold(); props=block.get('properties',{})
        fields=('DC',) if kind in ('voltage dc source','current dc source') else (
               ('ACAmplitude','HBAmplitude') if kind in ('voltage signal source','current signal source') else ())
        if any(field not in props or _scalar(props[field],{})!=0 for field in fields):
            raise ValueError('All independent source amplitudes must read back as zero')
        block_files=block.get('files')
        if not isinstance(block_files,list):
            raise ValueError('Complete block file readback required')
        if kind=='spice block' and (not block_files or any(Path(f).suffix.casefold() not in ('.cir','.lib','.sp','.spice','.mod') for f in block_files)):
            raise ValueError('SPICE block file dependency missing or unsupported')
        if kind=='touchstone block' and (len(block_files)!=1 or not re.fullmatch(r'\.s\d+p',Path(block_files[0]).suffix.casefold())):
            raise ValueError('Touchstone block file dependency missing or unsupported')
        if kind not in ('spice block','touchstone block') and block_files:
            raise ValueError('Unexpected file on an intrinsic source or ground')
    control=spec['control'];source=by_name.get(control['source'],{});bias=by_name.get(control['bias'],{})
    ground=by_name.get(control['ground'],{})
    if (str(source.get('type','')).casefold()!='voltage signal source'
            or str(bias.get('type','')).casefold()!='voltage dc source'
            or str(ground.get('type','')).casefold()!='ground'):
        raise ValueError('Control termination block types differ')
    for block,want in ((source,control['resistance_ohms']),(bias,0)):
        meta=block.get('property_metadata',{}).get('Ri',{})
        if meta.get('unit')!='Ohm' or not math.isclose(_scalar(block.get('properties',{}).get('Ri'),snapshot.get('parameters',{})),want,rel_tol=1e-12,abs_tol=0):
            raise ValueError('Control resistance differs')
    nets={}
    for row in snapshot.get('nets',[]):
        name=row.get('name');parts=row.get('subnets')
        if not isinstance(name,str) or not name or name in nets or not isinstance(parts,list) or not parts:
            raise ValueError('Complete unique native net inventory required')
        flat=[_endpoint(item) for part in parts for item in part]
        if not flat or len(flat)!=len(set(flat)):
            raise ValueError('Ambiguous native subnet membership')
        nets[name]=frozenset(flat)
    seen=set()
    for members in nets.values():
        if seen.intersection(members): raise ValueError('Endpoint appears in multiple nets')
        seen.update(members)
    for row in spec['ports']:
        probe=_endpoint(row['probe_endpoint']); original=frozenset(_endpoint(v) for v in row['expected_members'])
        desired=(original-{probe})|{('externalport',row['name'],0)}
        if nets.get(row['net_name'])!=desired:
            raise ValueError('Measurement port topology differs')
    chain=[(('block',spec['network_block'],control['network_pin']),('probe',control['probe'],1)),
           (('probe',control['probe'],0),('block',control['source'],0)),
           (('block',control['source'],1),('block',control['bias'],0)),
           (('block',control['bias'],1),('block',control['ground'],0))]
    for i,(a,b) in enumerate(chain):
        matches=[members for members in nets.values() if a in members and b in members]
        if len(matches)!=1 or (i<3 and matches[0]!=frozenset((a,b))):
            raise ValueError('Control termination topology differs')
    task=spec['task'];name=task['task_name'];tasks=snapshot.get('tasks',[])
    matches=[t for t in tasks if t.get('name')==name]
    if (len(matches)!=1 or str(matches[0].get('type','')).casefold()!='s-parameters'
            or any(str(t.get('name','')).startswith(name+'\\') for t in tasks) or task_enabled is not True):
        raise ValueError('Enabled S-parameter leaf task required')
    external=snapshot.get('external_ports',[])
    if (not isinstance(external,list) or len(external)!=len(task['port_impedances'])
            or {p.get('name') for p in external}!=set(task['port_impedances'])):
        raise ValueError('Exact measurement port inventory required')
    props=task_readback.get('properties',{});ports=task_readback.get('ports',{})
    if (task_readback.get('task_name')!=name or task_readback.get('frequency_unit')!=task['frequency_unit']
            or task_readback.get('resistance_unit')!='Ohm' or str(props.get('circuit simulator','')).casefold()!='cst'
            or any(str(props.get(k,'')).casefold()!='false' for k in ('maximum frequency range','broadband sweep','logarithmic sweep'))
            or not math.isclose(float(props.get('fmin','nan')),task['fmin'],rel_tol=1e-10,abs_tol=0)
            or not math.isclose(float(props.get('fmax','nan')),task['fmax'],rel_tol=1e-10,abs_tol=0)
            or set(ports)!=set(task['port_impedances'])
            or any(str(v.get('impedance_type','')).casefold()!='constant' for v in ports.values())):
        raise ValueError('Native task settings or port modes differ')
    observed=impedance.get('ports',{})
    if (set(observed)!=set(task['port_impedances']) or any(
            str(observed[k].get('impedance_type','')).casefold()!='constant'
            or not math.isclose(float(observed[k].get('real','nan')),v,rel_tol=1e-10,abs_tol=0)
            or not math.isclose(float(observed[k].get('imaginary','nan')),0,rel_tol=0,abs_tol=1e-12)
            for k,v in task['port_impedances'].items())):
        raise ValueError('Native numerical port impedances differ')
    project=Path(project_path).resolve();files=dependencies.get('files',[])
    if dependencies.get('complete') is not True or dependencies.get('unknown') or not isinstance(files,list):
        raise ValueError('Complete dependency inventory required')
    actual_files={}
    for item in files:
        path=Path(item['path']).resolve()
        if path!=project and not (re.fullmatch(r'\.s\d+p',path.suffix.casefold()) or path.suffix.casefold() in ('.cir','.lib','.sp','.spice','.mod')):
            raise ValueError('Unsupported or 3D project dependency')
        if (path in actual_files or not item.get('exists') or not item.get('sha256') or _sha(path)!=item['sha256']):
            raise ValueError('Dependency missing, duplicated or changed')
        actual_files[path]=item['sha256']
    if project not in actual_files:
        raise ValueError('Saved project dependency missing')
    network_files=network.get('files')
    if not isinstance(network_files,list) or len(network_files)!=1:
        raise ValueError('Exact embedded Touchstone file required')
    path=Path(network_files[0]).resolve();root=project.with_suffix('')/'Model'/'DS'/'Block'
    if not path.is_relative_to(root.resolve()) or actual_files.get(path)!=spec['network_sha256']:
        raise ValueError('Embedded network identity differs')
    for block in blocks:
        if any(Path(f).resolve() not in actual_files for f in block.get('files',[]) if f):
            raise ValueError('Block dependency is absent from inventory')
    header=next((line.split('!',1)[0].strip() for line in path.read_text(encoding='utf-8-sig').splitlines() if line.strip().startswith('#')),None)
    try: reference=float(header.split()[-1])
    except (AttributeError,IndexError,ValueError) as exc: raise ValueError('Touchstone reference unavailable') from exc
    pins=network.get('pins');n=len(pins) if isinstance(pins,list) else 0
    if n<2 or not math.isfinite(reference) or reference<=0:
        raise ValueError('Native network port count or reference unavailable')
    scale={'Hz':1,'kHz':1e3,'MHz':1e6,'GHz':1e9}[task['frequency_unit']]
    coverage=touchstone(path,n,reference,task['fmax']*scale)
    return {'structural_no_em_dependency_verified':True,'network_coverage':coverage,
            'network_sha256':spec['network_sha256'],'solver_verified':False,'native_no_em_execution_verified':False}
