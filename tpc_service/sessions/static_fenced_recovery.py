"""Narrow recovery of a returned, partially applied static preparation."""
from pathlib import Path

from tpc_service.errors import ServiceError
from .job_index import JobIndex
from .native import file_digest
from .store import alive, digest, identifier, read

CAPABILITY = 'static-sp-fenced-recovery-v1'
CAPTURE = 'capture_failed_static'
COMPLETE = 'complete_failed_static_task'
INSPECT = 'inspect_failed_static_task'


def validate(params):
    if (not isinstance(params, dict) or set(params) != {'project_id','failed_job_id','expected_disk_digest',
            'snapshot_digest','confirm_idle'} or params['confirm_idle'] is not True):
        raise ValueError('Exact recovery identity and explicit idle review required')
    identifier(params['project_id']); identifier(params['failed_job_id'])
    for key in ('expected_disk_digest','snapshot_digest'):
        value = params[key]
        if not isinstance(value,str) or len(value)!=64 or any(c not in '0123456789abcdef' for c in value):
            raise ValueError('Explicit lowercase SHA256 required')


def preflight(folder, state, params, job=None):
    def require(value, message):
        if not value: raise ServiceError('session_static_recovery_refused', message)
    validate(params)
    require(state.get('backend')=='cst' and state.get('status')=='needs_reconcile'
            and not state.get('worker_upgrade') and not state.get('uncertain_jobs')
            and not state.get('launch_intent') and not state.get('close_requested'), 'Original failure fence required')
    require(not any(j['job_id'] != (job or {}).get('job_id') for j in JobIndex.load(folder).active_jobs()),
            'No other active job allowed')
    require(state.get('worker') and alive(state['worker']) and CAPABILITY in state.get('worker_capabilities',[]),
            'Compatible existing worker required')
    require(state.get('environment') and alive(state['environment']), 'Original live DE required')
    original=read(Path(folder)/'jobs'/(params['failed_job_id']+'.json')) or {}
    error=original.get('error') or {}
    require(original.get('session_id')==state.get('session_id') and original.get('job_id')==params['failed_job_id']
            and original.get('operation')=='prepare_static_sp' and original.get('status')=='failed'
            and original.get('params',{}).get('project_id')==params['project_id']
            and error==state.get('last_error') and error.get('code')=='session_static_sp_prepare_failed',
            'Original failed preparation receipt differs')
    handoff=state.get('last_worker_upgrade') or {}; partial=handoff.get('static_partial') or {}
    require(handoff.get('mode')=='preserve_native_de_v1' and handoff.get('phase')=='complete'
            and handoff.get('return_to_fence') is True and partial.get('failed_job_id')==params['failed_job_id']
            and handoff.get('environment')==state.get('environment') and handoff.get('new_worker')==state.get('worker')
            and partial.get('project_id')==params['project_id'] and partial.get('snapshot_digest')==params['snapshot_digest']
            and partial.get('failed_job_digest')==digest(original) and partial.get('saved_disk_only') is True
            and handoff.get('release_native',{}).get('static_partial',{}).get(params['project_id'])==params['snapshot_digest'],
            'Completed handoff did not preserve the reviewed dirty circuit')
    project=state.get('projects',{}).get(params['project_id']) or {}
    require(project.get('saved') is True and not project.get('tab_closed')
            and project.get('saved_digest')==params['expected_disk_digest']
            and handoff.get('project_digests',{}).get(params['project_id'])==params['expected_disk_digest'],
            'Registered disk baseline differs')
    try:
        require(file_digest(project['path'])==params['expected_disk_digest'],'Disk baseline changed')
    except (OSError, KeyError) as exc:
        raise ServiceError('session_static_recovery_refused','Disk baseline unavailable') from exc
    return partial


def capture(runtime, job):
    """Save the reviewed dirty tab after exact fenced worker handoff; never resume it."""
    import json
    import os
    from cst_solver.dialogs import check_dialogs
    from cst_solver.circuit.adapter import NativeAdapter
    params=job['params']; state=runtime.state()
    partial=preflight(runtime.folder,state,params,job=job)
    project=state['projects'][params['project_id']]
    app=getattr(runtime,'app',None); handle=getattr(runtime,'handles',{}).get(params['project_id'])
    if (runtime.backend!='cst' or app is None or handle is None or not alive(state.get('environment'))
            or Path(handle.filename()).resolve()!=Path(project['path']).resolve()):
        raise ServiceError('session_static_recovery_refused','Existing exact project handle required')
    runtime.check_saved(project)
    check_dialogs(label=job['job_id'],pid=state['environment']['pid'])
    if handle.model3d.is_solver_running(timeout=5) is not False:
        raise ServiceError('session_static_recovery_refused','Native 3D idle not proven')
    app.cst_file=handle
    adapter=NativeAdapter(app)
    first=adapter.inspect(); second=adapter.inspect()
    if (first!=second or digest(first)!=params['snapshot_digest'] or
            any(u!={'field':'parameter_dimensions','status':'unknown'} for u in first.get('unknown',[]))):
        raise ServiceError('session_static_recovery_refused','Reviewed in-memory circuit changed or is incomplete')
    check_dialogs(label=job['job_id']+'-before-save',pid=state['environment']['pid'])
    if not alive(state['environment']) or file_digest(project['path'])!=params['expected_disk_digest']:
        raise ServiceError('session_static_recovery_refused','Environment or disk baseline changed')
    audit=Path(runtime.folder)/'static_sp_recovery'/(identifier(job['job_id'])+'.before.json')
    audit.parent.mkdir(parents=True,exist_ok=True)
    with audit.open('x',encoding='utf-8') as stream:
        json.dump({'job_id':job['job_id'],'params':params,'handoff':partial,'snapshot':first},
                  stream,ensure_ascii=False,indent=2,allow_nan=False)
        stream.flush(); os.fsync(stream.fileno())
    try:
        saved=runtime.save(app,params['project_id'])
        if (adapter.inspect()!=first or file_digest(project['path'])!=saved['saved_digest']
                or not alive(state['environment'])):
            raise ValueError('Saved snapshot or environment changed')
    except Exception as exc:
        raise ServiceError('session_static_capture_uncertain',str(exc),mutation_may_have_occurred=True,
                           audit_path=str(audit),original_failed_job_id=params['failed_job_id']) from exc
    return {'saved':True,'saved_digest':saved['saved_digest'],'snapshot_digest':params['snapshot_digest'],
            'original_failed_job_id':params['failed_job_id'],'before_audit':str(audit),
            'idle_asserted_by_caller':True,'schematic_idle_verified':False,'solver_verified':False}


def validate_completion(params):
    if (not isinstance(params,dict) or set(params)!={'project_id','failed_job_id','capture_job_id',
            'expected_saved_digest','snapshot_digest','expected_task','confirm_idle'}
            or params['confirm_idle'] is not True or not isinstance(params['expected_task'],dict)):
        raise ValueError('Exact captured project and reviewed task required')
    for key in ('project_id','failed_job_id','capture_job_id'): identifier(params[key])
    for key in ('expected_saved_digest','snapshot_digest'):
        value=params[key]
        if not isinstance(value,str) or len(value)!=64 or any(c not in '0123456789abcdef' for c in value):
            raise ValueError('Explicit lowercase SHA256 required')


def completion_preflight(folder,state,params,job=None):
    def require(value,message):
        if not value: raise ServiceError('session_static_recovery_refused',message)
    validate_completion(params)
    require(state.get('backend')=='cst' and state.get('status')=='needs_reconcile'
            and not state.get('worker_upgrade') and not state.get('uncertain_jobs')
            and not state.get('launch_intent') and not state.get('close_requested'), 'Original failure fence required')
    require(not any(j['job_id']!=(job or {}).get('job_id') for j in JobIndex.load(folder).active_jobs()), 'No other active job allowed')
    require(state.get('worker') and alive(state['worker']) and CAPABILITY in state.get('worker_capabilities',[]),
            'Compatible existing worker required')
    require(state.get('environment') and alive(state['environment']), 'Original live DE required')
    original=read(Path(folder)/'jobs'/(params['failed_job_id']+'.json')) or {}
    captured=read(Path(folder)/'jobs'/(params['capture_job_id']+'.json')) or {}
    handoff=state.get('last_worker_upgrade') or {}; partial=handoff.get('static_partial') or {}
    error=original.get('error') or {}; result=captured.get('result') or {}
    require(original.get('job_id')==params['failed_job_id'] and original.get('session_id')==state.get('session_id')
            and original.get('operation')=='prepare_static_sp' and original.get('status')=='failed'
            and original.get('params',{}).get('project_id')==params['project_id']
            and error==state.get('last_error') and error.get('code')=='session_static_sp_prepare_failed'
            and partial.get('failed_job_digest')==digest(original), 'Original failure receipt differs')
    require(handoff.get('phase')=='complete' and handoff.get('return_to_fence') is True
            and handoff.get('environment')==state.get('environment') and handoff.get('new_worker')==state.get('worker')
            and partial.get('failed_job_id')==params['failed_job_id'] and partial.get('project_id')==params['project_id']
            and partial.get('snapshot_digest')==params['snapshot_digest'], 'Reviewed handoff differs')
    require(captured.get('job_id')==params['capture_job_id'] and captured.get('session_id')==state.get('session_id')
            and captured.get('operation')==CAPTURE and captured.get('status')=='succeeded'
            and captured.get('params',{}).get('project_id')==params['project_id']
            and result.get('saved') is True and result.get('saved_digest')==params['expected_saved_digest']
            and result.get('snapshot_digest')==params['snapshot_digest']
            and result.get('original_failed_job_id')==params['failed_job_id'], 'Successful captured state required')
    project=state.get('projects',{}).get(params['project_id']) or {}
    require(project.get('saved') is True and not project.get('tab_closed')
            and project.get('saved_digest')==params['expected_saved_digest'], 'Captured saved identity differs')
    try: require(file_digest(project['path'])==params['expected_saved_digest'], 'Captured file changed')
    except (OSError,KeyError) as exc: raise ServiceError('session_static_recovery_refused','Captured file unavailable') from exc
    return {'original':original,'capture':captured}


def complete_task(runtime,job):
    """Complete only the existing SP task, retaining the original failure fence."""
    import json
    import os
    from cst_solver.dialogs import check_dialogs
    from cst_solver.circuit.linear_sp import complete_existing_linear_sp_task
    from cst_solver.circuit.adapter import NativeAdapter
    from cst_solver.circuit.static_sp import validate_prepare_spec, _sha
    params=job['params'];state=runtime.state()
    evidence=completion_preflight(runtime.folder,state,params,job=job)
    spec=evidence['original']['params'].get('spec')
    try: validate_prepare_spec(spec)
    except (ValueError,TypeError,KeyError) as exc:
        raise ServiceError('session_static_recovery_refused','Original task intent invalid') from exc
    project=state['projects'][params['project_id']]
    app=getattr(runtime,'app',None);handle=getattr(runtime,'handles',{}).get(params['project_id'])
    if (runtime.backend!='cst' or app is None or handle is None or not alive(state.get('environment'))
            or Path(handle.filename()).resolve()!=Path(project['path']).resolve()):
        raise ServiceError('session_static_recovery_refused','Existing exact project handle required')
    runtime.check_saved(project);check_dialogs(label=job['job_id'],pid=state['environment']['pid'])
    if handle.model3d.is_solver_running(timeout=5) is not False:
        raise ServiceError('session_static_recovery_refused','Native 3D idle not proven')
    app.cst_file=handle; adapter=NativeAdapter(app)
    before=adapter.inspect()
    if (digest(before)!=params['snapshot_digest'] or adapter.inspect()!=before
            or any(u!={'field':'parameter_dimensions','status':'unknown'} for u in before.get('unknown',[]))):
        raise ServiceError('session_static_recovery_refused','Captured circuit changed or is incomplete')
    network=Path(str(adapter.select('Block',spec['network_block']).GetFile())).resolve()
    root=Path(project['path']).with_suffix('')/'Model'/'DS'/'Block'
    if not network.is_relative_to(root.resolve()) or _sha(network)!=spec['network_sha256']:
        raise ServiceError('session_static_recovery_refused','Embedded network identity changed')
    dependencies=adapter.dependencies()
    if (dependencies.get('complete') is not True or dependencies.get('unknown')
            or any(not f.get('exists') or not f.get('sha256') for f in dependencies.get('files',[]))):
        raise ServiceError('session_static_recovery_refused','Circuit dependencies incomplete')
    task=spec['task']; task_name=task['task_name']
    if len([t for t in before.get('tasks',[]) if t.get('name')==task_name])!=1:
        raise ServiceError('session_static_recovery_refused','Exact existing task required')
    audit=Path(runtime.folder)/'static_sp_recovery'/(identifier(job['job_id'])+'.before.json')
    audit.parent.mkdir(parents=True,exist_ok=True)
    with audit.open('x',encoding='utf-8') as stream:
        json.dump({'job_id':job['job_id'],'params':params,'original_job_id':params['failed_job_id'],
                   'snapshot':before,'dependencies':dependencies},stream,ensure_ascii=False,indent=2,allow_nan=False)
        stream.flush();os.fsync(stream.fileno())
    check_dialogs(label=job['job_id']+'-before-task-write',pid=state['environment']['pid'])
    if (not alive(state['environment']) or file_digest(project['path'])!=params['expected_saved_digest']
            or adapter.inspect()!=before or handle.model3d.is_solver_running(timeout=5) is not False):
        raise ServiceError('session_static_recovery_refused','Project changed immediately before task write')
    try:
        task_report=complete_existing_linear_sp_task(adapter.schematic,task_name,expected=params['expected_task'],
            frequency_unit=task['frequency_unit'],fmin=task['fmin'],fmax=task['fmax'],
            samples=task['samples'],port_impedances=task['port_impedances'])
        after=adapter.inspect()
        if (any(after.get(k)!=v for k,v in before.items() if k!='tasks')
                or [t for t in after['tasks'] if t['name']!=task_name]!=[t for t in before['tasks'] if t['name']!=task_name]
                or len([t for t in after['tasks'] if t['name']==task_name])!=1
                or adapter.dependencies()!=dependencies or _sha(network)!=spec['network_sha256']):
            raise ValueError('Unrelated circuit state or network changed')
        saved=runtime.save(app,params['project_id'])
        if adapter.inspect()!=after or file_digest(project['path'])!=saved['saved_digest'] or not alive(state['environment']):
            raise ValueError('Saved task state or environment changed')
    except Exception as exc:
        raise ServiceError('session_static_task_completion_partial',str(exc),mutation_may_have_occurred=True,
                           original_details=getattr(exc,'details',{}),audit_path=str(audit),
                           original_failed_job_id=params['failed_job_id']) from exc
    return {'saved':True,'saved_digest':saved['saved_digest'],'original_failed_job_id':params['failed_job_id'],
            'capture_job_id':params['capture_job_id'],'task_report':task_report,'after':after,
            'network_sha256':spec['network_sha256'],'before_audit':str(audit),
            'sample_count_readback':'unsupported','impedance_value_readback':'unsupported',
            'schematic_idle_verified':False,'solver_verified':False}


def inspect_task(runtime,job):
    """Read the existing target task on the captured fenced circuit, without writes."""
    from cst_solver.dialogs import check_dialogs
    from cst_solver.circuit.linear_sp import inspect_existing_linear_sp
    from cst_solver.circuit.adapter import NativeAdapter
    from cst_solver.circuit.static_sp import validate_prepare_spec
    params=job['params'];state=runtime.state()
    evidence=completion_preflight(runtime.folder,state,params,job=job)
    if params['expected_task'] != {}:
        raise ServiceError('session_static_recovery_refused','Inspection requires an empty expected task')
    spec=evidence['original']['params'].get('spec')
    try: validate_prepare_spec(spec)
    except (ValueError,TypeError,KeyError) as exc:
        raise ServiceError('session_static_recovery_refused','Original task intent invalid') from exc
    project=state['projects'][params['project_id']]
    app=getattr(runtime,'app',None);handle=getattr(runtime,'handles',{}).get(params['project_id'])
    if (runtime.backend!='cst' or app is None or handle is None or not alive(state.get('environment'))
            or Path(handle.filename()).resolve()!=Path(project['path']).resolve()):
        raise ServiceError('session_static_recovery_refused','Existing exact project handle required')
    runtime.check_saved(project);check_dialogs(label=job['job_id'],pid=state['environment']['pid'])
    if handle.model3d.is_solver_running(timeout=5) is not False:
        raise ServiceError('session_static_recovery_refused','Native 3D idle not proven')
    app.cst_file=handle;adapter=NativeAdapter(app)
    before=adapter.inspect()
    if digest(before)!=params['snapshot_digest']:
        raise ServiceError('session_static_recovery_refused','Captured circuit changed')
    task=spec['task']
    report=inspect_existing_linear_sp(adapter.schematic,task['task_name'],list(task['port_impedances']))
    if adapter.inspect()!=before or file_digest(project['path'])!=params['expected_saved_digest']:
        raise ServiceError('session_static_recovery_refused','Circuit or disk changed during task readback')
    return {'expected_task':report,'original_failed_job_id':params['failed_job_id'],
            'capture_job_id':params['capture_job_id'],'saved':False,'solver_verified':False,
            'schematic_idle_verified':False}
