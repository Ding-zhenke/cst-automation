"""Bind native host-network zero-bias SP to the current accepted EM result."""
from pathlib import Path

from tpc_service.errors import ServiceError
from .job_index import JobIndex
from .native import file_digest
from .store import alive,identifier,read


CAPABILITY='native-static-sp-v2'
REVIEW='review_native_static_sp'


def validate(params):
    keys={'project_id','em_job_id','expected_saved_digest','snapshot_digest','spec','confirm_idle','sample_observation'}
    if not isinstance(params,dict) or set(params)!=keys or params['confirm_idle'] is not True:
        raise ValueError('Exact project, current EM, reviewed circuit and idle confirmation required')
    for key in ('project_id','em_job_id'): identifier(params[key])
    for key in ('expected_saved_digest','snapshot_digest'):
        value=params[key]
        if not isinstance(value,str) or len(value)!=64 or any(c not in '0123456789abcdef' for c in value):
            raise ValueError('Explicit lowercase SHA256 required')
    spec=params['spec']
    if not isinstance(spec,dict) or set(spec)!={'host_block','host_pins','task','expected_nets','control','diode_blocks'}:
        raise ValueError('Explicit host mapping, task and full nets required')
    if not isinstance(spec['host_block'],str) or not spec['host_block'].strip() or not isinstance(spec['host_pins'],list) or not spec['host_pins']:
        raise ValueError('Explicit native host and pins required')
    if not isinstance(spec['expected_nets'],list) or not spec['expected_nets']:
        raise ValueError('Explicit reviewed native nets required')
    control=spec['control']
    if (not isinstance(control,dict) or set(control)!={'network_pin','probe','source','bias','ground','resistance_ohms'}
            or type(control['network_pin']) is not int or control['network_pin']<0
            or any(not isinstance(control[k],str) or not control[k].strip() for k in ('probe','source','bias','ground'))
            or type(control['resistance_ohms']) not in (int,float) or control['resistance_ohms']!=50):
        raise ValueError('Explicit 50 ohm control chain required')
    if (not isinstance(spec['diode_blocks'],list) or not spec['diode_blocks']
            or any(not isinstance(n,str) or not n.strip() for n in spec['diode_blocks'])
            or len(set(spec['diode_blocks']))!=len(spec['diode_blocks'])):
        raise ValueError('Explicit unique diode block names required')
    task=spec['task']
    if not isinstance(task,dict) or set(task)!={'task_name','frequency_unit','fmin','fmax','samples','port_impedances'}:
        raise ValueError('Exact native SP task settings required')
    import math
    if (not isinstance(task['task_name'],str) or not task['task_name'].strip() or '\\' in task['task_name']
            or task['frequency_unit'] not in ('Hz','kHz','MHz','GHz')
            or any(type(task[k]) not in (int,float) or not math.isfinite(task[k]) for k in ('fmin','fmax'))
            or not 0<=task['fmin']<task['fmax'] or type(task['samples']) is not int or not 2<=task['samples']<=100000
            or not isinstance(task['port_impedances'],dict) or len(task['port_impedances'])!=2
            or any(not isinstance(k,str) or not k.strip() or type(v) not in (int,float) or not math.isfinite(v) or v<=0
                   for k,v in task['port_impedances'].items())):
        raise ValueError('Invalid native SP task or port settings')
    evidence=params['sample_observation']
    if (not isinstance(evidence,dict) or set(evidence)!={'path','sha256'}
            or not isinstance(evidence['path'],str) or not Path(evidence['path']).is_absolute()
            or not isinstance(evidence['sha256'],str) or len(evidence['sha256'])!=64
            or any(c not in '0123456789abcdef' for c in evidence['sha256'])):
        raise ValueError('Explicit sample observation artifact and digest required')


def validate_prepare(params):
    keys={'project_id','em_job_id','expected_saved_digest','snapshot_digest','spec','confirm_idle'}
    if not isinstance(params,dict) or set(params)!=keys:
        raise ValueError('Exact native host preparation fields required')
    placeholder=dict(params,sample_observation={'path':str(Path.cwd().resolve()/'unused-observation.json'),'sha256':'0'*64})
    validate(placeholder)


def read_sample_observation(params):
    import json
    from datetime import datetime
    evidence=params['sample_observation'];path=Path(evidence['path'])
    if not path.is_file() or path.is_symlink() or path.stat().st_size>1000000 or file_digest(path)!=evidence['sha256']:
        raise ValueError('Sample observation artifact unavailable or changed')
    report=json.loads(path.read_text(encoding='utf-8-sig'))
    keys={'source','task_name','frequency_unit','fmin','fmax','samples','observed_at','review_note'}
    task=params['spec']['task']
    if (not isinstance(report,dict) or set(report)!=keys or report['source']!='gui_observation'
            or type(report['samples']) is not int or any(type(report[k]) not in (int,float) for k in ('fmin','fmax'))
            or any(report[k]!=task[k] for k in ('task_name','frequency_unit','fmin','fmax','samples'))
            or any(not isinstance(report[k],str) or not report[k].strip() for k in ('observed_at','review_note'))):
        raise ValueError('Sample observation does not match reviewed task')
    if datetime.fromisoformat(report['observed_at']).tzinfo is None:
        raise ValueError('Sample observation time must include timezone')
    return report


def preflight(folder,state,params,job=None,*,require_sample=True):
    from .workflow import marker,check_evidence
    from .em_network import current_em
    def require(value,message):
        if not value: raise ServiceError('session_native_static_refused',message)
    (validate if require_sample else validate_prepare)(params)
    require(state.get('backend')=='cst' and state.get('status')=='ready' and not state.get('worker_upgrade')
            and not state.get('uncertain_jobs') and not state.get('launch_intent') and not state.get('close_requested')
            and not any(j['job_id']!=(job or {}).get('job_id') for j in JobIndex.load(folder).active_jobs()),
            'Idle ready session required')
    require(state.get('worker') and alive(state['worker']) and CAPABILITY in state.get('worker_capabilities',[])
            and 'static-sp-guarded-run-v1' in state.get('worker_capabilities',[])
            and state.get('environment') and alive(state['environment']),'Compatible existing worker and DE required')
    project=state.get('projects',{}).get(params['project_id']) or {};workflow=project.get('workflow') or {}
    require(project.get('saved') is True and not project.get('tab_closed') and project.get('saved_digest')==params['expected_saved_digest']
            and workflow.get('revision') and type(workflow.get('em_generation')) is int,'Saved protected project required')
    try:
        require(file_digest(project['path'])==params['expected_saved_digest'],'Saved project changed')
        require(read(marker(project['path']))=={'session_folder':str(Path(folder).resolve()),'project_id':params['project_id']},
                'Workflow ownership differs')
        current_em(folder,project,params['em_job_id']);check_evidence(folder,project)
        sample_observation=read_sample_observation(params) if require_sample else None
    except (OSError,ValueError,TypeError,KeyError) as exc:
        raise ServiceError('session_native_static_refused',str(exc)) from exc
    return {'workflow_revision':workflow['revision'],'em_generation':workflow['em_generation'],
            'em_job_id':params['em_job_id'],'em_receipt':workflow['em_receipt'],
            'sample_observation':sample_observation}


def prepare(runtime,job):
    """Zero reviewed source amplitudes while preserving the native host circuit."""
    import copy
    import json
    import os
    from cst_solver.dialogs import check_dialogs
    from cst_solver.circuit.adapter import NativeAdapter
    from cst_solver.circuit.linear_sp import inspect_existing_linear_sp,complete_existing_linear_sp_task,configure_linear_sp_task
    from cst_solver.circuit.native import read_project_sp_impedances
    from cst_solver.circuit.native_static_gate import validate_native_static
    from cst_solver.circuit.static_sp import _scalar
    from .static_fenced_recovery import _model3d_files
    from .store import digest
    from .workflow import live_checks,invalidate
    params=job['params'];state=runtime.state();evidence=preflight(runtime.folder,state,params,job=job,require_sample=False)
    project=state['projects'][params['project_id']];handle=getattr(runtime,'handles',{}).get(params['project_id'])
    app=getattr(runtime,'app',None);spec=params['spec'];task=spec['task'];name=task['task_name']
    if (runtime.backend!='cst' or app is None or handle is None or not alive(state.get('environment'))
            or Path(handle.filename()).resolve()!=Path(project['path']).resolve()):
        raise ServiceError('session_native_static_refused','Existing exact project handle required')
    runtime.check_saved(project);check_dialogs(label=job['job_id'],pid=state['environment']['pid'])
    if handle.model3d.is_solver_running(timeout=5) is not False:
        raise ServiceError('session_native_static_refused','Native 3D idle not proven')
    app.cst_file=handle;adapter=NativeAdapter(app);before=adapter.inspect()
    if digest(before)!=params['snapshot_digest']:
        raise ServiceError('session_native_static_refused','Reviewed circuit identity differs')
    live_checks(app,project['workflow'],'em')
    scene_files=_model3d_files(project['path'])
    tasks=before.get('tasks',[]);existing=[row for row in tasks if row.get('name')==name]
    if (len(existing)>1 or (existing and str(existing[0].get('type','')).casefold()!='s-parameters')
            or any(str(row.get('name','')).startswith(name+'\\') for row in tasks)):
        raise ServiceError('session_native_static_refused','Target must be a unique SP leaf or a new name')
    native_before=inspect_existing_linear_sp(adapter.schematic,name,list(task['port_impedances'])) if existing else None
    if (native_before is not None and (native_before.get('frequency_unit')!=task['frequency_unit']
            or native_before.get('resistance_unit')!='Ohm'
            or str(native_before.get('properties',{}).get('circuit simulator','')).casefold()!='cst')):
        raise ServiceError('session_native_static_refused','Existing task units or circuit simulator differ')
    planned=copy.deepcopy(before);changes=[]
    for block in planned.get('blocks',[]):
        kind=str(block.get('type','')).casefold()
        if kind in ('voltage dc source','current dc source'): fields=('DC',)
        elif kind in ('voltage signal source','current signal source'): fields=('ACAmplitude','HBAmplitude')
        elif 'source' in kind: raise ServiceError('session_native_static_refused','Unsupported source type')
        else: continue
        for field in fields:
            props=block.get('properties',{})
            if field not in props: raise ServiceError('session_native_static_refused','Source property missing')
            if _scalar(props[field],before.get('parameters',{}))!=0:
                changes.append((block['name'],field))
            props[field]='0'
    if not existing:
        planned['tasks'].append({'name':name,'type':'S-Parameters'})
    planned_task={'task_name':name,'frequency_unit':task['frequency_unit'],'resistance_unit':'Ohm',
        'properties':{'circuit simulator':'cst','maximum frequency range':'false','broadband sweep':'false',
                      'logarithmic sweep':'false','fmin':str(task['fmin']),'fmax':str(task['fmax'])},
        'ports':{n:{'impedance_type':'Constant'} for n in task['port_impedances']}}
    planned_impedance={'ports':{n:{'impedance_type':'Constant','real':v,'imaginary':0} for n,v in task['port_impedances'].items()}}
    try:
        gate=validate_native_static(planned,spec,planned_task,adapter.dependencies(),planned_impedance,
                                    project_path=project['path'],task_enabled=True)
    except (OSError,ValueError,TypeError,KeyError,RuntimeError) as exc:
        raise ServiceError('session_native_static_refused',str(exc)) from exc
    audit=Path(runtime.folder)/'native_static_prepare'/(identifier(job['job_id'])+'.before.json')
    audit.parent.mkdir(parents=True,exist_ok=True)
    with audit.open('x',encoding='utf-8') as stream:
        json.dump({'job_id':job['job_id'],'params':params,'before':before,'planned_changes':changes,
                   'native_task_before':native_before,'planned_gate_only':gate,'3d_files_before':scene_files},stream,ensure_ascii=False,indent=2,allow_nan=False)
        stream.flush();os.fsync(stream.fileno())
    check_dialogs(label=job['job_id']+'-before-write',pid=state['environment']['pid'])
    if (not alive(state['environment']) or handle.model3d.is_solver_running(timeout=5) is not False
            or adapter.inspect()!=before or file_digest(project['path'])!=params['expected_saved_digest']
            or _model3d_files(project['path'])!=scene_files
            or preflight(runtime.folder,runtime.state(),params,job=job,require_sample=False)!=evidence):
        raise ServiceError('session_native_static_refused','Project or EM changed before source preparation')
    try:
        invalidate(runtime,job)
        for block,field in changes:
            adapter.select('Block',block).SetDoubleProperty(field,'0')
        options={k:task[k] for k in ('frequency_unit','fmin','fmax','samples','port_impedances')}
        if existing:
            task_report=complete_existing_linear_sp_task(adapter.schematic,name,expected=native_before,**options)
        else:
            task_report=configure_linear_sp_task(adapter.schematic,name,**options)
        adapter.select('SimulationTask',name).SetProperty('enabled','True')
        native_task=inspect_existing_linear_sp(adapter.schematic,name,list(task['port_impedances']))
        enabled=str(adapter.select('SimulationTask',name).GetProperty('enabled')).casefold()=='true'
        impedance=read_project_sp_impedances(handle,name,list(task['port_impedances']),expected_project_path=project['path'],
            receipt_root=Path(runtime.folder)/'sp_impedance_queries',confirm_idle=True)
        after=adapter.inspect();normalized=copy.deepcopy(after)
        for block in normalized.get('blocks',[]):
            kind=str(block.get('type','')).casefold()
            fields=('DC',) if kind in ('voltage dc source','current dc source') else (
                ('ACAmplitude','HBAmplitude') if kind in ('voltage signal source','current signal source') else ())
            for field in fields:
                if _scalar(block['properties'][field],after.get('parameters',{}))!=0:
                    raise ValueError('Source zero readback differs')
                block['properties'][field]='0'
        normalized['tasks']=[row for row in normalized['tasks'] if row.get('name')!=name]
        planned['tasks']=[row for row in planned['tasks'] if row.get('name')!=name]
        if normalized!=planned:
            raise ValueError('Native circuit changed outside reviewed source amplitudes')
        validate_native_static(after,spec,native_task,adapter.dependencies(),impedance,
                               project_path=project['path'],task_enabled=enabled)
        saved=runtime.save(app,params['project_id'])
        if (file_digest(project['path'])!=saved['saved_digest'] or adapter.inspect()!=after
                or _model3d_files(project['path'])!=scene_files):
            raise ValueError('Saved circuit identity changed')
    except Exception as exc:
        raise ServiceError('session_native_static_prepare_partial',str(exc),mutation_may_have_occurred=True,
                           before_audit=str(audit),original_type=type(exc).__name__) from exc
    return {'saved':True,'saved_digest':saved['saved_digest'],'after':after,'snapshot_digest':digest(after),
            'em_job_id':params['em_job_id'],'em_generation':evidence['em_generation'],'changes':changes,
            'before_audit':str(audit),'native_host_present':True,'control_50_verified':True,'diode_model_verified':False,
            '3d_files_unchanged':True,
            'task_report':task_report,'impedances':impedance,
            'sample_count_native_readback':'unsupported','solver_verified':False,'em_reuse_verified':False}


def review(runtime,job):
    """Inspect the current host-network static task without running it."""
    from cst_solver.dialogs import check_dialogs
    from cst_solver.circuit.adapter import NativeAdapter
    from cst_solver.circuit.linear_sp import inspect_existing_linear_sp
    from cst_solver.circuit.native import read_project_sp_impedances
    from cst_solver.circuit.native_static_gate import validate_native_static
    from .store import digest
    from .workflow import live_checks
    params=job['params'];state=runtime.state();evidence=preflight(runtime.folder,state,params,job=job)
    project=state['projects'][params['project_id']];handle=getattr(runtime,'handles',{}).get(params['project_id'])
    app=getattr(runtime,'app',None);task=params['spec']['task'];name=task['task_name']
    if (runtime.backend!='cst' or app is None or handle is None or not alive(state.get('environment'))
            or Path(handle.filename()).resolve()!=Path(project['path']).resolve()):
        raise ServiceError('session_native_static_refused','Existing exact project handle required')
    runtime.check_saved(project);check_dialogs(label=job['job_id'],pid=state['environment']['pid'])
    if handle.model3d.is_solver_running(timeout=5) is not False:
        raise ServiceError('session_native_static_refused','Native 3D idle not proven')
    app.cst_file=handle;adapter=NativeAdapter(app);snapshot=adapter.inspect()
    if digest(snapshot)!=params['snapshot_digest']:
        raise ServiceError('session_native_static_refused','Reviewed circuit identity differs')
    live_checks(app,project['workflow'],'em')
    native_task=inspect_existing_linear_sp(adapter.schematic,name,list(task['port_impedances']))
    enabled=str(adapter.select('SimulationTask',name).GetProperty('enabled')).casefold()=='true'
    impedance=read_project_sp_impedances(handle,name,list(task['port_impedances']),expected_project_path=project['path'],
        receipt_root=Path(runtime.folder)/'sp_impedance_queries',confirm_idle=True)
    dependencies=adapter.dependencies()
    try:
        gate=validate_native_static(snapshot,params['spec'],native_task,dependencies,impedance,
                                    project_path=project['path'],task_enabled=enabled)
        if (adapter.inspect()!=snapshot or file_digest(project['path'])!=params['expected_saved_digest']
                or not alive(state['environment']) or preflight(runtime.folder,runtime.state(),params,job=job)!=evidence):
            raise ValueError('Project or accepted EM identity changed during review')
    except (OSError,ValueError,TypeError,KeyError,RuntimeError) as exc:
        raise ServiceError('session_native_static_refused',str(exc)) from exc
    return {'em_job_id':params['em_job_id'],'snapshot_digest':params['snapshot_digest'],
            'saved_digest':params['expected_saved_digest'],'after':snapshot,'spec':params['spec'],
            'task_report':native_task,'impedances':impedance,'dependencies':dependencies,
            'workflow_revision':evidence['workflow_revision'],'em_generation':evidence['em_generation'],
            'em_receipt':evidence['em_receipt'],'native_host_present':gate['native_host_present'],'diode_model_verified':False,
            'sample_observation':evidence['sample_observation'],'sample_count_native_readback':'unsupported',
            'em_reuse_verified':False,'saved':False,'solver_verified':False,'formal_hb_gate_satisfied':False}


def validate_run(params):
    keys={'project_id','review_job_id','expected_saved_digest','confirm_idle','confirm_run'}
    if not isinstance(params,dict) or set(params)!=keys or params['confirm_idle'] is not True or params['confirm_run'] is not True:
        raise ValueError('Exact static review and explicit idle/run confirmation required')
    for key in ('project_id','review_job_id'): identifier(params[key])
    value=params['expected_saved_digest']
    if not isinstance(value,str) or len(value)!=64 or any(c not in '0123456789abcdef' for c in value):
        raise ValueError('Explicit lowercase SHA256 required')


def run_preflight(folder,state,params,job=None):
    from .store import digest
    from .static_sp_run import verified_impedance_artifact
    from cst_solver.circuit.links import dependency_manifest
    from cst_solver.circuit.native_static_gate import validate_native_static
    def require(value,message):
        if not value: raise ServiceError('session_native_static_refused',message)
    validate_run(params)
    reviewed=read(Path(folder)/'jobs'/(params['review_job_id']+'.json')) or {};result=reviewed.get('result') or {}
    require(reviewed.get('job_id')==params['review_job_id'] and reviewed.get('session_id')==state.get('session_id')
            and reviewed.get('operation')==REVIEW and reviewed.get('status')=='succeeded'
            and reviewed.get('params',{}).get('project_id')==params['project_id']
            and result.get('saved_digest')==params['expected_saved_digest'] and result.get('native_host_present') is True,
            'Matching successful native static review required')
    evidence=preflight(folder,state,reviewed['params'],job=job)
    require(reviewed['params']['expected_saved_digest']==params['expected_saved_digest']
            and result.get('em_job_id')==reviewed['params']['em_job_id'] and result.get('spec')==reviewed['params']['spec']
            and result.get('workflow_revision')==evidence['workflow_revision'] and result.get('em_generation')==evidence['em_generation']
            and result.get('em_receipt')==evidence['em_receipt'] and result.get('sample_observation')==evidence['sample_observation']
            and isinstance(result.get('after'),dict)
            and digest(result['after'])==reviewed['params']['snapshot_digest'],'Review or EM identity changed')
    try:
        project=state['projects'][params['project_id']]['path'];spec=result['spec'];task=spec['task']
        impedance=verified_impedance_artifact(folder,project,task['task_name'],result['impedances'])
        dependencies=dependency_manifest(project,result['after'])
        gate=validate_native_static(result['after'],spec,result['task_report'],dependencies,impedance,
                                    project_path=project,task_enabled=True)
    except (OSError,ValueError,TypeError,KeyError,RuntimeError) as exc:
        raise ServiceError('session_native_static_refused',str(exc)) from exc
    return dict(evidence,review=reviewed,parsed_impedance=impedance,gate=gate,dependencies=dependencies)


def execute(runtime, job):
    """Recheck the reviewed host-network task, then use the shared SP kernel."""
    import json
    import os
    from cst_solver.dialogs import check_dialogs
    from cst_solver.circuit.adapter import NativeAdapter
    from cst_solver.circuit.linear_sp import inspect_existing_linear_sp
    from cst_solver.circuit.native import read_project_sp_impedances
    from cst_solver.circuit.native_static_gate import validate_native_static
    from .static_fenced_recovery import _model3d_files
    from .static_sp_run import run_and_archive
    from .workflow import live_checks

    params=job['params'];state=runtime.state();evidence=run_preflight(runtime.folder,state,params,job=job)
    review=evidence['review'];spec=review['result']['spec'];task=spec['task'];name=task['task_name']
    project=state['projects'][params['project_id']];handle=getattr(runtime,'handles',{}).get(params['project_id'])
    app=getattr(runtime,'app',None)
    if (runtime.backend!='cst' or app is None or handle is None or not alive(state.get('environment'))
            or Path(handle.filename()).resolve()!=Path(project['path']).resolve()):
        raise ServiceError('session_native_static_refused','Existing exact project handle required')
    runtime.check_saved(project);check_dialogs(label=job['job_id'],pid=state['environment']['pid'])
    if handle.model3d.is_solver_running(timeout=5) is not False:
        raise ServiceError('session_native_static_refused','Native 3D idle not proven')
    app.cst_file=handle;adapter=NativeAdapter(app);snapshot=adapter.inspect()
    if snapshot!=review['result']['after']:
        raise ServiceError('session_native_static_refused','Native circuit changed since review')
    live_checks(app,project['workflow'],'em')
    native_task=inspect_existing_linear_sp(adapter.schematic,name,list(task['port_impedances']))
    enabled=str(adapter.select('SimulationTask',name).GetProperty('enabled')).casefold()=='true'
    impedance=read_project_sp_impedances(handle,name,list(task['port_impedances']),expected_project_path=project['path'],
        receipt_root=Path(runtime.folder)/'sp_impedance_queries',confirm_idle=True)
    if impedance.get('ports')!=evidence['parsed_impedance'].get('ports'):
        raise ServiceError('session_native_static_refused','Fresh native impedance observation differs')
    try:
        gate=validate_native_static(snapshot,spec,native_task,adapter.dependencies(),impedance,
                                    project_path=project['path'],task_enabled=enabled)
        if native_task!=review['result']['task_report']:
            raise ValueError('Native static task changed since review')
    except (OSError,ValueError,TypeError,KeyError,RuntimeError) as exc:
        raise ServiceError('session_native_static_refused',str(exc)) from exc
    scene_files=_model3d_files(project['path'])
    log=Path(project['path']).with_suffix('')/'Result'/'Model.log'
    before_log=file_digest(log) if log.is_file() else None
    output=Path(runtime.folder)/'static_sp_runs'/identifier(job['job_id'])
    output.mkdir(parents=True,exist_ok=False);audit=output/'before.json'
    with audit.open('x',encoding='utf-8') as stream:
        json.dump({'job_id':job['job_id'],'params':params,'gate':gate,'native_task':native_task,
                   'fresh_impedance':impedance,'3d_files':scene_files,'3d_log_sha256':before_log},
                  stream,ensure_ascii=False,indent=2,allow_nan=False)
        stream.flush();os.fsync(stream.fileno())
    check_dialogs(label=job['job_id']+'-before-run',pid=state['environment']['pid'])
    if (not alive(state['environment']) or handle.model3d.is_solver_running(timeout=5) is not False
            or adapter.inspect()!=snapshot or file_digest(project['path'])!=params['expected_saved_digest']
            or _model3d_files(project['path'])!=scene_files
            or run_preflight(runtime.folder,runtime.state(),params,job=job)!=evidence):
        raise ServiceError('session_native_static_refused','Project or accepted EM changed before task update')
    return run_and_archive(runtime=runtime,job=job,project=project,spec=spec,snapshot=snapshot,
        output=output,audit=audit,adapter=adapter,scene_files=scene_files,before_log=before_log,log=log,
        require_no_3d=False,context={'review_job_id':params['review_job_id'],
                                    'em_job_id':review['params']['em_job_id'],
                                    'em_generation':evidence['em_generation'],'em_reuse_verified':False,
                                    'diode_model_verified':False,
                                    'sample_observation':evidence['sample_observation'],
                                    'sample_observation_sha256':review['params']['sample_observation']['sha256'],
                                    'sample_count_native_readback':'unsupported'})


def validate_read(params):
    keys={'project_id','run_job_id','expected_saved_digest','positive_run_id','confirm_idle'}
    if (not isinstance(params,dict) or set(params)!=keys or params['confirm_idle'] is not True
            or type(params['positive_run_id']) is not int or params['positive_run_id']<=0):
        raise ValueError('Explicit saved run, positive native result ID and idle review required')
    for key in ('project_id','run_job_id'): identifier(params[key])
    value=params['expected_saved_digest']
    if not isinstance(value,str) or len(value)!=64 or any(c not in '0123456789abcdef' for c in value):
        raise ValueError('Explicit lowercase SHA256 required')


def read_preflight(folder,state,params,job=None):
    from .store import digest
    from .em_network import current_em
    def require(value,message):
        if not value: raise ServiceError('session_native_static_read_refused',message)
    validate_read(params)
    require(state.get('backend')=='cst' and state.get('status')=='ready' and not state.get('worker_upgrade')
            and not state.get('uncertain_jobs') and not state.get('launch_intent') and not state.get('close_requested')
            and not any(j['job_id']!=(job or {}).get('job_id') for j in JobIndex.load(folder).active_jobs()),
            'Idle ready session required')
    require(state.get('worker') and alive(state['worker']) and CAPABILITY in state.get('worker_capabilities',[])
            and state.get('environment') and alive(state['environment']), 'Compatible existing worker and DE required')
    run=read(Path(folder)/'jobs'/(params['run_job_id']+'.json')) or {};result=run.get('result') or {}
    require(run.get('job_id')==params['run_job_id'] and run.get('session_id')==state.get('session_id')
            and run.get('operation')=='run_native_static_sp' and run.get('status')=='succeeded'
            and run.get('params',{}).get('project_id')==params['project_id'] and result.get('saved') is True
            and result.get('saved_digest')==params['expected_saved_digest'] and result.get('solver_verified') is True
            and result.get('actual_grid_verified') is True and result.get('run_token'), 'Matching successful static run required')
    review=read(Path(folder)/'jobs'/(identifier(result['review_job_id'])+'.json')) or {};observed=review.get('result') or {}
    require(review.get('job_id')==result.get('review_job_id') and review.get('session_id')==state.get('session_id')
            and review.get('operation')==REVIEW and review.get('status')=='succeeded'
            and review.get('params',{}).get('project_id')==params['project_id']
            and isinstance(observed.get('after'),dict) and digest(observed['after'])==review['params']['snapshot_digest']
            and result.get('em_job_id')==review['params']['em_job_id'], 'Original host review differs')
    receipt=result.get('circuit_outcome') or {}
    require(receipt.get('status')=='succeeded' and receipt.get('submitted') is True
            and receipt.get('execution_returned') is True and receipt.get('update_call_state')=='returned'
            and receipt.get('saved') is True and receipt.get('saved_digest')==params['expected_saved_digest']
            and receipt.get('task_name')==result.get('task_name') and receipt.get('mode')=='network'
            and receipt.get('run_token')==result.get('run_token')
            and (receipt.get('execution_evidence') or {}).get('completed') is True,
            'Native target-task run receipt is incomplete')
    project=state.get('projects',{}).get(params['project_id']) or {};workflow=project.get('workflow') or {}
    require(project.get('saved') is True and not project.get('tab_closed') and project.get('saved_digest')==params['expected_saved_digest']
            and workflow.get('em_generation')==result.get('em_generation')
            and workflow.get('revision')==observed.get('workflow_revision')
            and workflow.get('em_receipt')==observed.get('em_receipt'), 'Saved project, workflow or EM identity differs')
    try:
        current_em(folder,project,result['em_job_id'])
        require(file_digest(project['path'])==params['expected_saved_digest'], 'Saved file changed')
        root=(Path(folder)/'static_sp_runs'/params['run_job_id']).resolve()
        raw=Path(result['current_curves_path']).resolve()
        require(raw.is_relative_to(root) and raw.is_file() and file_digest(raw)==result['current_curves_sha256'],
                'Current-run curve archive changed')
    except (OSError,KeyError,ValueError,TypeError) as exc:
        raise ServiceError('session_native_static_read_refused',str(exc)) from exc
    return {'run':run,'review':review,'raw':raw}


def read_positive(runtime,job):
    from cst_solver.dialogs import check_dialogs
    from cst_solver.circuit.adapter import NativeAdapter
    from .static_sp_run import read_archived_positive
    params=job['params'];state=runtime.state();evidence=read_preflight(runtime.folder,state,params,job=job)
    project=state['projects'][params['project_id']];handle=getattr(runtime,'handles',{}).get(params['project_id'])
    app=getattr(runtime,'app',None)
    if (runtime.backend!='cst' or app is None or handle is None or not alive(state.get('environment'))
            or Path(handle.filename()).resolve()!=Path(project['path']).resolve()):
        raise ServiceError('session_native_static_read_refused','Existing exact project handle required')
    runtime.check_saved(project);check_dialogs(label=job['job_id'],pid=state['environment']['pid'])
    if handle.model3d.is_solver_running(timeout=5) is not False:
        raise ServiceError('session_native_static_read_refused','Native 3D idle not proven')
    app.cst_file=handle;adapter=NativeAdapter(app);expected=evidence['review']['result']['after']
    if adapter.inspect()!=expected:
        raise ServiceError('session_native_static_read_refused','Native circuit changed after run')
    task=evidence['review']['result']['spec']['task'];result=evidence['run']['result']
    return read_archived_positive(runtime=runtime,job=job,project=project,expected=expected,task=task,
        name=task['task_name'],paths=result['resolved_result_paths'],raw=evidence['raw'],adapter=adapter,
        positive_run_id=params['positive_run_id'],context={'run_job_id':params['run_job_id'],
        'em_job_id':result['em_job_id'],'em_reuse_verified':False})
