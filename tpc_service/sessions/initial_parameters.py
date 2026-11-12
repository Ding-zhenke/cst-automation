"""Reviewed initial parameter batch, using the existing Python wrapper."""
import math
from pathlib import Path

from cst_solver.expressions import parse_expression,validate_expression,validate_parameter_name
from tpc_service.errors import ServiceError
from .job_index import JobIndex
from .native import file_digest
from .store import alive,digest,identifier


CAPABILITY='initial-parameters-v1'
OPERATION='initialize_parameters'


def normalize(values):
    if not isinstance(values,dict) or not 1<=len(values)<=10000:
        raise ValueError('Nonempty bounded parameter mapping required')
    names={}
    for name in values:
        if validate_parameter_name(name)!=name or name.casefold() in names:
            raise ValueError('Distinct canonical parameter names required')
        names[name.casefold()]=name
    formulas={};dependencies={}
    for name,value in values.items():
        if isinstance(value,bool) or not isinstance(value,(str,int,float)) or (isinstance(value,float) and not math.isfinite(value)):
            raise ValueError('Finite number or expression required')
        text=validate_expression(str(value),names.values())
        ids,_,calls=parse_expression(text)
        deps={names[token.casefold()] for token,is_call in zip(ids,calls)
              if not is_call and token.casefold() in names}
        formulas[name]=text;dependencies[name]=deps
    remaining=set(names.values());ordered={}
    while remaining:
        available=sorted((n for n in remaining if not (dependencies[n]&remaining)),key=str.casefold)
        if not available: raise ValueError('Cyclic parameter dependencies')
        for name in available:
            ordered[name]=formulas[name];remaining.remove(name)
    return ordered


def validate(params):
    required={'project_id','values','expected_saved_digest','preview_digest','confirm_idle'}
    if not isinstance(params,dict) or set(params)!=required or params['confirm_idle'] is not True:
        raise ValueError('Exact saved project, reviewed values and idle confirmation required')
    identifier(params['project_id']);values=normalize(params['values'])
    for key in ('expected_saved_digest','preview_digest'):
        value=params[key]
        if not isinstance(value,str) or len(value)!=64 or any(c not in '0123456789abcdef' for c in value):
            raise ValueError('Explicit lowercase SHA256 required')
    if params['preview_digest']!=digest(params['values']):
        raise ValueError('Reviewed parameter mapping digest differs')
    return values


def preflight(folder,state,params,job=None):
    from .workflow import marker
    def require(value,message):
        if not value: raise ServiceError('session_initial_parameters_refused',message)
    values=validate(params)
    require(state.get('backend')=='cst' and state.get('status')=='ready' and not state.get('worker_upgrade')
            and not state.get('uncertain_jobs') and not state.get('launch_intent') and not state.get('close_requested')
            and not any(j['job_id']!=(job or {}).get('job_id') for j in JobIndex.load(folder).active_jobs()),
            'Idle ready session required')
    require(state.get('worker') and alive(state['worker']) and CAPABILITY in state.get('worker_capabilities',[])
            and state.get('environment') and alive(state['environment']), 'Compatible existing worker and DE required')
    project=state.get('projects',{}).get(params['project_id']) or {}
    require(isinstance(project.get('path'),str) and project.get('saved') is True and not project.get('tab_closed')
            and not project.get('workflow') and project.get('saved_digest')==params['expected_saved_digest']
            and not marker(project['path']).exists(),
            'Unbound saved project required')
    try: require(file_digest(project['path'])==params['expected_saved_digest'],'Saved project changed')
    except OSError as exc: raise ServiceError('session_initial_parameters_refused','Saved project unavailable') from exc
    return values


def execute(runtime,job):
    """Apply a single reviewed batch through app.paras; never submit a solver."""
    import json
    import os
    from cst_solver.dialogs import check_dialogs
    from .inspection import inspect_native
    params=job['params'];state=runtime.state();values=preflight(runtime.folder,state,params,job=job)
    project=state['projects'][params['project_id']];handle=getattr(runtime,'handles',{}).get(params['project_id'])
    app=getattr(runtime,'app',None)
    if (runtime.backend!='cst' or app is None or handle is None or not alive(state.get('environment'))
            or Path(handle.filename()).resolve()!=Path(project['path']).resolve()):
        raise ServiceError('session_initial_parameters_refused','Existing exact project handle required')
    runtime.check_saved(project);check_dialogs(label=job['job_id'],pid=state['environment']['pid'])
    if handle.model3d.is_solver_running(timeout=5) is not False:
        raise ServiceError('session_initial_parameters_refused','Native 3D idle not proven')
    app.cst_file=handle;before=inspect_native(app,{})
    if (before.get('errors') or before.get('solids') or
            {n.casefold() for n in before.get('parameters',{})}.intersection(n.casefold() for n in values)):
        raise ServiceError('session_initial_parameters_refused','No existing solids or matching parameters allowed')
    audit=Path(runtime.folder)/'initial_parameters'/(identifier(job['job_id'])+'.before.json')
    audit.parent.mkdir(parents=True,exist_ok=True)
    with audit.open('x',encoding='utf-8') as stream:
        json.dump({'job_id':job['job_id'],'params':params,'before':before},stream,ensure_ascii=False,indent=2,allow_nan=False)
        stream.flush();os.fsync(stream.fileno())
    check_dialogs(label=job['job_id']+'-before-write',pid=state['environment']['pid'])
    if (not alive(state['environment']) or handle.model3d.is_solver_running(timeout=5) is not False
            or file_digest(project['path'])!=params['expected_saved_digest'] or inspect_native(app,{})!=before):
        raise ServiceError('session_initial_parameters_refused','Project changed immediately before parameter write')
    try:
        app.paras(list(values),list(values.values()),log_flag=0)
        validation=app.validate_model()
        if validation.get('status')!='success' or validation.get('rebuild_ok') is not True:
            raise ValueError('Parameter rebuild and messages are not verified')
        after=inspect_native(app,{})
        if after.get('errors') or after.get('solids'):
            raise ValueError('Native parameter readback incomplete or geometry changed')
        for name,expression in values.items():
            actual=after.get('parameters',{}).get(name) or {}
            if (str(actual.get('expression','')).strip()!=expression or type(actual.get('value')) not in (int,float)
                    or not math.isfinite(actual['value'])):
                raise ValueError('Native expression or finite value differs for '+name)
        saved=runtime.save(app,params['project_id'])
        if file_digest(project['path'])!=saved['saved_digest'] or inspect_native(app,{})!=after:
            raise ValueError('Saved parameter state changed')
    except Exception as exc:
        raise ServiceError('session_initial_parameters_partial',str(exc),mutation_may_have_occurred=True,
                           original_details=getattr(exc,'details',{}),before_audit=str(audit)) from exc
    return {'saved':True,'saved_digest':saved['saved_digest'],'before_audit':str(audit),
            'parameters':after['parameters'],'native_expression_readback_verified':True,
            'geometry_verified':False,'solver_verified':False}
