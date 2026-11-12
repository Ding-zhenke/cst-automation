"""Guard a static SP leaf by original receipts and observable circuit dependencies."""
import json
from pathlib import Path
from tpc_service.errors import ServiceError
from .native import file_digest
from .store import identifier, read
from .static_fenced_recovery import impedance_preflight

CAPABILITY='static-sp-guarded-run-v1'
OPERATION='run_fenced_static_sp'
READ_OPERATION='read_fenced_static_sp'


def validate(params):
    keys={'project_id','failed_job_id','exclude_job_id','impedance_job_id','expected_saved_digest',
          'snapshot_digest','confirm_idle','confirm_run'}
    if (not isinstance(params,dict) or set(params)!=keys or params['confirm_idle'] is not True
            or params['confirm_run'] is not True):
        raise ValueError('Exact static run identity and explicit run/idle review required')
    for key in ('project_id','failed_job_id','exclude_job_id','impedance_job_id'): identifier(params[key])
    for key in ('expected_saved_digest','snapshot_digest'):
        value=params[key]
        if not isinstance(value,str) or len(value)!=64 or any(c not in '0123456789abcdef' for c in value):
            raise ValueError('Explicit lowercase SHA256 required')


def preflight(folder,state,params,job=None):
    from cst_automation.sp_impedance_bridge import parse_impedance_receipt
    from cst_solver.circuit.links import dependency_manifest
    from cst_solver.circuit.static_sp_gate import validate_static_network
    def require(value,message):
        if not value: raise ServiceError('session_static_run_refused',message)
    validate(params)
    base={k:params[k] for k in ('project_id','failed_job_id','exclude_job_id','expected_saved_digest','snapshot_digest','confirm_idle')}
    evidence=impedance_preflight(folder,state,base,job=job)
    require(CAPABILITY in state.get('worker_capabilities',[]),'Compatible guarded-run worker required')
    original=evidence['original'];excluded=evidence['excluded'];spec=original.get('params',{}).get('spec') or {}
    task=spec.get('task') or {};name=task.get('task_name')
    require(isinstance(name,str) and bool(name),'Original target task required')
    completion_id=excluded.get('params',{}).get('completion_job_id')
    try: completion=read(Path(folder)/'jobs'/(identifier(completion_id)+'.json')) or {}
    except (ValueError,TypeError): completion={}
    task_readback=(completion.get('result') or {}).get('task_report',{}).get('after') or {}
    require(completion.get('operation')=='complete_failed_static_task' and completion.get('status')=='succeeded'
            and completion.get('params',{}).get('project_id')==params['project_id'], 'Original task completion required')
    item=read(Path(folder)/'jobs'/(params['impedance_job_id']+'.json')) or {};result=item.get('result') or {}
    report=result.get('impedances') or {}
    require(item.get('job_id')==params['impedance_job_id'] and item.get('session_id')==state.get('session_id')
            and item.get('operation')=='read_fenced_static_impedances' and item.get('status')=='succeeded'
            and item.get('params',{}).get('project_id')==params['project_id'] and result.get('matches_requested') is True
            and result.get('original_failed_job_id')==params['failed_job_id'] and result.get('exclude_job_id')==params['exclude_job_id']
            and result.get('saved_digest')==params['expected_saved_digest'] and result.get('snapshot_digest')==params['snapshot_digest'],
            'Matching successful native impedance observation required')
    try:
        root=(Path(folder)/'sp_impedance_queries').resolve();artifact=Path(report['artifact_path']).resolve()
        manifest=Path(report['manifest_path']).resolve()
        require(artifact.is_relative_to(root) and manifest.is_relative_to(root) and artifact.is_file() and manifest.is_file(),
                'Bound native impedance receipts required')
        request=json.loads(manifest.read_text(encoding='utf-8'))
        require(Path(request['output_path']).resolve()==artifact and Path(request['project_path']).resolve()==Path(state['projects'][params['project_id']]['path']).resolve()
                and request['task_name']==name, 'Native impedance request identity differs')
        parsed=parse_impedance_receipt(artifact.read_bytes(),request=request)
        require(parsed['ports']==report.get('ports'), 'Native impedance receipt changed')
        snapshot=excluded['result']['after'];project=state['projects'][params['project_id']]['path']
        dependencies=dependency_manifest(project,snapshot)
        gate=validate_static_network(snapshot,spec,task_readback,dependencies,parsed,project_path=project,task_enabled=True)
    except ServiceError:
        raise
    except (OSError,ValueError,TypeError,KeyError,OverflowError) as exc:
        raise ServiceError('session_static_run_refused',str(exc)) from exc
    return {'original':original,'excluded':excluded,'completion':completion,'impedance':item,
            'parsed_impedance':parsed,'gate':gate,'dependencies':dependencies}


def validate_read(params):
    if (not isinstance(params,dict) or set(params)!={'project_id','failed_job_id','run_job_id',
            'expected_saved_digest','positive_run_id','confirm_idle'} or params['confirm_idle'] is not True
            or type(params['positive_run_id']) is not int or params['positive_run_id']<=0):
        raise ValueError('Exact saved run, positive native ID and idle review required')
    for key in ('project_id','failed_job_id','run_job_id'): identifier(params[key])
    value=params['expected_saved_digest']
    if not isinstance(value,str) or len(value)!=64 or any(c not in '0123456789abcdef' for c in value):
        raise ValueError('Explicit lowercase SHA256 required')


def read_preflight(folder,state,params,job=None):
    from .job_index import JobIndex
    from .store import alive,digest
    def require(value,message):
        if not value: raise ServiceError('session_static_read_refused',message)
    validate_read(params)
    require(state.get('backend')=='cst' and state.get('status')=='needs_reconcile'
            and not state.get('worker_upgrade') and not state.get('uncertain_jobs')
            and not state.get('launch_intent') and not state.get('close_requested'), 'Original failure fence required')
    require(not any(j['job_id']!=(job or {}).get('job_id') for j in JobIndex.load(folder).active_jobs()),'No other active job allowed')
    require(state.get('worker') and alive(state['worker']) and CAPABILITY in state.get('worker_capabilities',[])
            and state.get('environment') and alive(state['environment']), 'Compatible existing worker and DE required')
    original=read(Path(folder)/'jobs'/(params['failed_job_id']+'.json')) or {}
    run=read(Path(folder)/'jobs'/(params['run_job_id']+'.json')) or {};result=run.get('result') or {}
    handoff=state.get('last_worker_upgrade') or {};partial=handoff.get('static_partial') or {}
    require(original.get('job_id')==params['failed_job_id'] and original.get('session_id')==state.get('session_id')
            and original.get('operation')=='prepare_static_sp' and original.get('status')=='failed'
            and original.get('params',{}).get('project_id')==params['project_id'] and original.get('error')==state.get('last_error')
            and partial.get('failed_job_digest')==digest(original), 'Original failure receipt differs')
    require(handoff.get('phase')=='complete' and handoff.get('return_to_fence') is True
            and handoff.get('environment')==state.get('environment') and handoff.get('new_worker')==state.get('worker')
            and partial.get('failed_job_id')==params['failed_job_id'] and partial.get('project_id')==params['project_id'],
            'Reviewed handoff differs')
    require(run.get('job_id')==params['run_job_id'] and run.get('session_id')==state.get('session_id')
            and run.get('operation')==OPERATION and run.get('status')=='succeeded'
            and run.get('params',{}).get('project_id')==params['project_id'] and result.get('saved') is True
            and result.get('saved_digest')==params['expected_saved_digest'] and result.get('solver_verified') is True
            and result.get('actual_grid_verified') is True and result.get('structural_no_em_dependency_verified') is True
            and result.get('original_failed_job_id')==params['failed_job_id'] and result.get('run_token'),
            'Successful matching static run required')
    native=result.get('circuit_outcome') or {}
    require(native.get('status')=='succeeded' and native.get('submitted') is True
            and native.get('execution_returned') is True and native.get('update_call_state')=='returned'
            and native.get('saved') is True and native.get('saved_digest')==params['expected_saved_digest']
            and native.get('task_name')==result.get('task_name') and native.get('mode')=='network'
            and native.get('run_token')==result['run_token'] and (native.get('execution_evidence') or {}).get('completed') is True,
            'Native target-task run receipt is incomplete')
    project=state.get('projects',{}).get(params['project_id']) or {}
    require(project.get('saved') is True and not project.get('tab_closed')
            and project.get('saved_digest')==params['expected_saved_digest'], 'Saved run identity differs')
    try:
        require(file_digest(project['path'])==params['expected_saved_digest'], 'Saved run file changed')
        root=(Path(folder)/'static_sp_runs'/params['run_job_id']).resolve()
        raw=Path(result['current_curves_path']).resolve()
        require(raw.is_relative_to(root) and raw.is_file() and file_digest(raw)==result['current_curves_sha256'],
                'Current-run archived curves changed')
    except (OSError,KeyError) as exc:
        raise ServiceError('session_static_read_refused','Saved run or artifact unavailable') from exc
    return {'original':original,'run':run,'raw':raw}


def execute(runtime,job):
    """Run one explicitly authorized pure-network SP leaf on the owned fenced tab."""
    import os
    from cst_solver.dialogs import check_dialogs
    from cst_solver.circuit.adapter import NativeAdapter
    from cst_solver.circuit.linear_sp import inspect_existing_linear_sp
    from cst_solver.circuit.native import read_project_sp_impedances
    from cst_solver.circuit.results import CircuitResult
    from cst_solver.circuit.static_sp_gate import validate_static_network
    from cst_automation.static_sp_results import verify_curves
    from .operations import circuit
    from .static_fenced_recovery import _model3d_files
    from .store import alive
    params=job['params'];state=runtime.state();evidence=preflight(runtime.folder,state,params,job=job)
    spec=evidence['original']['params']['spec'];task=spec['task'];name=task['task_name']
    project=state['projects'][params['project_id']];app=getattr(runtime,'app',None)
    handle=getattr(runtime,'handles',{}).get(params['project_id'])
    if (runtime.backend!='cst' or app is None or handle is None or not alive(state.get('environment'))
            or Path(handle.filename()).resolve()!=Path(project['path']).resolve()):
        raise ServiceError('session_static_run_refused','Existing exact project handle required')
    runtime.check_saved(project);check_dialogs(label=job['job_id'],pid=state['environment']['pid'])
    if handle.model3d.is_solver_running(timeout=5) is not False:
        raise ServiceError('session_static_run_refused','Native 3D idle not proven')
    app.cst_file=handle;adapter=NativeAdapter(app);snapshot=adapter.inspect()
    if snapshot!=evidence['excluded']['result']['after']:
        raise ServiceError('session_static_run_refused','Native circuit changed since reviewed exclusion')
    native_task=inspect_existing_linear_sp(adapter.schematic,name,list(task['port_impedances']))
    obj=adapter.select('SimulationTask',name)
    enabled=str(obj.GetProperty('enabled')).casefold()=='true'
    fresh=read_project_sp_impedances(handle,name,list(task['port_impedances']),expected_project_path=project['path'],
        receipt_root=Path(runtime.folder)/'sp_impedance_queries',confirm_idle=True)
    if fresh.get('ports')!=evidence['parsed_impedance']['ports']:
        raise ServiceError('session_static_run_refused','Fresh native impedance observation differs')
    dependencies=adapter.dependencies()
    gate=validate_static_network(snapshot,spec,native_task,dependencies,fresh,project_path=project['path'],task_enabled=enabled)
    if adapter.inspect()!=snapshot or file_digest(project['path'])!=params['expected_saved_digest']:
        raise ServiceError('session_static_run_refused','Circuit or saved file changed during live review')
    scene_files=_model3d_files(project['path'])
    log=Path(project['path']).with_suffix('')/'Result'/'Model.log'
    before_log=file_digest(log) if log.is_file() else None
    output=Path(runtime.folder)/'static_sp_runs'/identifier(job['job_id'])
    output.mkdir(parents=True,exist_ok=False)
    audit=output/'before.json'
    with audit.open('x',encoding='utf-8') as stream:
        json.dump({'job_id':job['job_id'],'params':params,'gate':gate,'native_task':native_task,
                   'fresh_impedance':fresh,'3d_files':scene_files,'3d_log_sha256':before_log},
                  stream,ensure_ascii=False,indent=2,allow_nan=False)
        stream.flush();os.fsync(stream.fileno())
    check_dialogs(label=job['job_id']+'-before-run',pid=state['environment']['pid'])
    if (not alive(state['environment']) or handle.model3d.is_solver_running(timeout=5) is not False
            or adapter.inspect()!=snapshot or file_digest(project['path'])!=params['expected_saved_digest']
            or _model3d_files(project['path'])!=scene_files):
        raise ServiceError('session_static_run_refused','Project changed immediately before task update')
    api=app.circuit;api._adapter=NativeAdapter(app);api._spec=None
    request={'project_id':params['project_id'],'kind':'solve','settings':{
        'operation':'run_task','task_name':name,'mode':'network','reuse':'never',
        'expected_results':[],'result_selectors':['11','12','21','22']}}
    outcome=None
    try:
        outcome=circuit(runtime,app,project,request)
        receipt=(outcome.get('result_summary') or {}).get('circuit_outcome') or {}
        if (receipt.get('status')!='succeeded' or receipt.get('execution_returned') is not True
                or receipt.get('submitted') is not True or receipt.get('update_call_state')!='returned'
                or receipt.get('task_name')!=name or receipt.get('mode')!='network' or not receipt.get('run_token')
                or receipt.get('saved') is not True or (receipt.get('execution_evidence') or {}).get('completed') is not True):
            raise ValueError('Target task completion not proven')
        paths=receipt.get('resolved_result_paths')
        from cst_solver.circuit.results import task_result_path
        if (not isinstance(paths,dict) or set(paths)!={'11','12','21','22'} or len(set(paths.values()))!=4
                or any(not isinstance(path,str) or not task_result_path(path,name)
                       or not path.endswith('\\S-Parameters\\S'+key[0]+','+key[1]) for key,path in paths.items())):
            raise ValueError('Four unique native task-scoped result paths not proven')
        current_state=runtime.state();saved=current_state['projects'][params['project_id']]['saved_digest']
        if (receipt.get('saved_digest')!=saved or file_digest(project['path'])!=saved
                or adapter.inspect()!=snapshot or _model3d_files(project['path'])!=scene_files):
            raise ValueError('Saved circuit or 3D model inventory changed during task')
        after_log=file_digest(log) if log.is_file() else None
        if before_log!=after_log:
            raise ValueError('3D solver log changed during static task')
        reader=CircuitResult(project['path'])
        curves={key:reader.read_curve(path,run_id=0) for key,path in paths.items()}
        params0=curves['11']['parameters']
        def dump_curves(path,values):
            data={}
            for key,curve in values.items():
                data[key]={k:v for k,v in curve.items() if k!='y'}
                data[key]['y']=[[v.real,v.imag] for v in curve['y']]
            with path.open('x',encoding='utf-8') as stream:
                json.dump(data,stream,ensure_ascii=False,indent=2,allow_nan=False);stream.flush();os.fsync(stream.fileno())
        raw=output/'current-curves.json';dump_curves(raw,curves)
        validation=verify_curves(curves,task_name=name,run_id=0,project_path=project['path'],parameters=params0,
            frequency_unit=task['frequency_unit'],fmin=task['fmin'],fmax=task['fmax'],samples=task['samples'],allow_current=True)
        common=None
        for path in paths.values():
            ids={v for v in reader.get_run_ids(path) if type(v) is int and v>0}
            common=ids if common is None else common.intersection(ids)
        candidates=[];positive={}
        if len(common or ())<=64:
            for rid in sorted(common or ()):
                rows={key:reader.read_curve(path,run_id=rid) for key,path in paths.items()}
                if all(rows[k]['sample_digest']==curves[k]['sample_digest'] and rows[k]['parameters']==curves[k]['parameters']
                       and rows[k]['x_unit']==curves[k]['x_unit'] and rows[k]['y_unit']==curves[k]['y_unit'] for k in curves):
                    candidates.append(rid);positive[rid]=rows
        positive_path=None
        if len(candidates)==1:
            rid=candidates[0]
            verify_curves(positive[rid],task_name=name,run_id=rid,project_path=project['path'],parameters=params0,
                frequency_unit=task['frequency_unit'],fmin=task['fmin'],fmax=task['fmax'],samples=task['samples'])
            positive_path=output/'positive-curves.json';dump_curves(positive_path,positive[rid])
        return {'saved':True,'saved_digest':saved,'original_failed_job_id':params['failed_job_id'],
                'exclude_job_id':params['exclude_job_id'],'impedance_job_id':params['impedance_job_id'],
                'task_name':name,'run_token':receipt.get('run_token'),'circuit_outcome':receipt,'resolved_result_paths':paths,
                'structural_no_em_dependency_verified':True,'3d_files_unchanged':True,'3d_log_unchanged':True,
                'native_no_em_execution_verified':False,'network_sha256':spec['network_sha256'],
                'actual_grid_verified':True,'validation':validation,'current_curves_path':str(raw),
                'current_curves_sha256':file_digest(raw),'matching_positive_run_ids':candidates,
                'positive_search_truncated':len(common or ())>64,
                'positive_curves_path':str(positive_path) if positive_path else None,
                'positive_curves_sha256':file_digest(positive_path) if positive_path else None,
                'positive_run_id':candidates[0] if len(candidates)==1 else None,
                'positive_fresh_attribution_verified':False,'solver_verified':True,
                'formal_hb_gate_satisfied':False,'source_qualification':'not_assessed','before_audit':str(audit)}
    except Exception as exc:
        raise ServiceError('session_static_run_unverified',str(exc),run_may_have_started=True,
                           original_type=type(exc).__name__,original_details=getattr(exc,'details',{}),
                           before_audit=str(audit),run_directory=str(output),
                           circuit_result=outcome) from exc


def read_positive(runtime,job):
    """Read one actual positive run ID and compare it with the archived current run."""
    import os
    from cst_solver.dialogs import check_dialogs
    from cst_solver.circuit.adapter import NativeAdapter
    from cst_solver.circuit.results import CircuitResult
    from cst_automation.static_sp_results import verify_curves
    from .store import alive,digest
    params=job['params'];state=runtime.state();evidence=read_preflight(runtime.folder,state,params,job=job)
    prior=evidence['run'];run_result=prior['result'];original=evidence['original'];spec=original['params']['spec']
    task=spec['task'];name=task['task_name'];paths=run_result['resolved_result_paths']
    excluded=read(Path(runtime.folder)/'jobs'/(identifier(run_result['exclude_job_id'])+'.json')) or {}
    expected=(excluded.get('result') or {}).get('after')
    if not isinstance(expected,dict) or digest(expected)!=prior['params']['snapshot_digest']:
        raise ServiceError('session_static_read_refused','Original excluded circuit receipt differs')
    project=state['projects'][params['project_id']];app=getattr(runtime,'app',None)
    handle=getattr(runtime,'handles',{}).get(params['project_id'])
    if (runtime.backend!='cst' or app is None or handle is None or not alive(state.get('environment'))
            or Path(handle.filename()).resolve()!=Path(project['path']).resolve()):
        raise ServiceError('session_static_read_refused','Existing exact project handle required')
    runtime.check_saved(project);check_dialogs(label=job['job_id'],pid=state['environment']['pid'])
    if handle.model3d.is_solver_running(timeout=5) is not False:
        raise ServiceError('session_static_read_refused','Native 3D idle not proven')
    app.cst_file=handle;adapter=NativeAdapter(app)
    if adapter.inspect()!=expected:
        raise ServiceError('session_static_read_refused','Native circuit changed after run')
    archived=json.loads(evidence['raw'].read_text(encoding='utf-8'))
    if not isinstance(archived,dict) or set(archived)!={'11','12','21','22'}:
        raise ServiceError('session_static_read_refused','Current-run archive incomplete')
    reader=CircuitResult(project['path'])
    current={key:reader.read_curve(path,run_id=0) for key,path in paths.items()}
    positive={key:reader.read_curve(path,run_id=params['positive_run_id']) for key,path in paths.items()}
    for key,curve in current.items():
        stored=archived[key]
        if (stored.get('sample_digest')!=curve['sample_digest'] or stored.get('parameters')!=curve['parameters']
                or stored.get('tree_path')!=curve['tree_path'] or stored.get('x_unit')!=curve['x_unit']
                or stored.get('y_unit')!=curve['y_unit'] or stored.get('x')!=curve['x']
                or stored.get('y')!=[[v.real,v.imag] for v in curve['y']]):
            raise ServiceError('session_static_read_refused','Current native curves changed after recorded run')
        selected=positive[key]
        if (selected['sample_digest']!=curve['sample_digest'] or selected['parameters']!=curve['parameters']
                or selected['x_unit']!=curve['x_unit'] or selected['y_unit']!=curve['y_unit']):
            raise ServiceError('session_static_read_refused','Positive ID does not match recorded current curves')
    validation=verify_curves(positive,task_name=name,run_id=params['positive_run_id'],project_path=project['path'],
        parameters=current['11']['parameters'],frequency_unit=task['frequency_unit'],fmin=task['fmin'],
        fmax=task['fmax'],samples=task['samples'])
    if (adapter.inspect()!=expected or file_digest(project['path'])!=params['expected_saved_digest']
            or not alive(state['environment'])):
        raise ServiceError('session_static_read_refused','Project changed during result read')
    output=evidence['raw'].parent/('positive-'+identifier(job['job_id'])+'.json')
    data={}
    for key,curve in positive.items():
        data[key]={k:v for k,v in curve.items() if k!='y'}
        data[key]['y']=[[v.real,v.imag] for v in curve['y']]
    with output.open('x',encoding='utf-8') as stream:
        json.dump(data,stream,ensure_ascii=False,indent=2,allow_nan=False);stream.flush();os.fsync(stream.fileno())
    return {'original_failed_job_id':params['failed_job_id'],'run_job_id':params['run_job_id'],
            'saved_digest':params['expected_saved_digest'],'positive_run_id':params['positive_run_id'],
            'task_name':name,'positive_curves_path':str(output),'positive_curves_sha256':file_digest(output),
            'validation':validation,'current_content_matches_positive':True,
            'positive_fresh_attribution_verified':False,'saved':False,'solver_verified':False}
