"""Separate saved-result qualification; never rewrites a failed solver receipt."""
from pathlib import Path
import hashlib
import json
import math
from cst_automation.em_qualification import CAPABILITY, log_proof
from cst_automation.workflow import digest
from .native import file_digest
from .store import read,identifier,alive
from .workflow import reject


def source_identity(job):
    return digest({k:job.get(k) for k in ('job_id','operation','params','workflow_guard','started_at','finished_at','error','completion_evidence')})


def preflight(folder,state,p,job=None):
    from .job_index import JobIndex
    project=state['projects'][p['project_id']];w=project['workflow']
    if (state['status']!='ready' or state.get('uncertain_jobs') or state.get('launch_intent')
            or any(j['job_id']!=(job or {}).get('job_id') for j in JobIndex.load(folder).active_jobs())):
        reject('qualification_idle_required','Resolve and confirm the owning session idle before qualification')
    if state.get('worker') and alive(state['worker']) and CAPABILITY not in state.get('worker_capabilities',[]):
        reject('worker_upgrade_required','Saved-result qualification requires an upgraded idle worker')
    original=read(Path(folder)/'jobs'/(identifier(p['em_job_id'])+'.json'))
    if not original or original.get('operation')!='solve' or original.get('status') not in ('failed','resolved') or original.get('params',{}).get('project_id')!=p['project_id']:
        reject('qualification_source_invalid','Original failed owning solve required')
    error=original.get('error') or {};details=error.get('details',{});outcome=details.get('outcome',{})
    errors=outcome.get('errors',[]);completion=original.get('completion_evidence',{})
    if (error.get('code')!='session_solve_unverified' or len(errors)!=1 or errors[0].get('code')!='run_exception'
            or errors[0].get('details',{}).get('error')!='RuntimeError: An error occurred while trying to execute run_solver:\nAborted by user'
            or completion.get('monitor_failure_seen') is not False or completion.get('launch_intent') is not False
            or completion.get('uncertain_job_count')!=0 or details.get('saved') is not True
            or details.get('saved_digest')!=p['expected_digest']):
        reject('qualification_source_invalid','Failure is not the supported contradictory SDK abort case')
    guard=original.get('workflow_guard') or {}
    if guard.get('revision')!=w['revision'] or any(w[k]!=guard.get(k,-2)+1 for k in ('em_generation','hb_generation')):
        reject('qualification_stale','Workflow inputs changed since the failed execution')
    resolution=state.get('last_resolution') or {}
    if (resolution.get('human_reviewed') is not True or resolution.get('at',0)<original.get('finished_at',float('inf'))
            or resolution.get('project_digests',{}).get(p['project_id'])!=p['expected_digest']):
        reject('qualification_idle_required','Normal explicit idle reconciliation of this saved baseline required')
    if project['saved_digest']!=p['expected_digest'] or file_digest(project['path'])!=p['expected_digest']:
        reject('qualification_changed','Saved project differs from the failed run baseline')
    return original


def saved_curves(path,p,values, *, consume=None):
    """Only the saved-results SDK, never setup/DesignEnvironment/model3d."""
    from cst_solver import Result
    from cst_solver.circuit.results import quantity_values,axis_unit
    reader=Result(str(path));module=reader.result_module
    import re
    pairs=set()
    for tree in reader.get_tree_items():
        match=re.fullmatch(r'1D Results\\S-Parameters\\S(\d+),(\d+)',str(tree))
        if match and p['run_id'] in reader.get_run_ids(str(tree)):
            pairs.add(tuple(map(int,match.groups())))
    if pairs!={(a,b) for a in p['port_ids'] for b in p['port_ids']}:
        raise ValueError('Requested ports do not cover the complete saved S-matrix')
    stored=dict(module.get_parameter_combination(p['run_id']))
    for name,value in values.items():
        actual=float(stored[name])
        if not math.isfinite(actual) or not math.isclose(actual,value,rel_tol=1e-10,abs_tol=1e-12):raise ValueError('Saved run parameter mismatch: '+name)
    grid=None;matrix_hash=hashlib.sha256();count=0
    def curve(tree):
        if p['run_id'] not in reader.get_run_ids(tree):raise ValueError('Required positive run missing: '+tree)
        item=reader.get_result_item(tree,run_id=p['run_id'])
        x,xunit=quantity_values(item.get_xdata(),axis_unit(item,'x',tree))
        y,yunit=quantity_values(item.get_ydata(),axis_unit(item,'y',tree))
        if xunit not in ('Hz','kHz','MHz','GHz') or yunit not in ('1','') or len(x)!=len(y) or any(v.imag for v in x):raise ValueError('Unknown result units or inconsistent axes')
        scale={'Hz':1,'kHz':1e3,'MHz':1e6,'GHz':1e9}[xunit]
        xs=[v.real*scale for v in x]
        if (not xs or any(a>=b for a,b in zip(xs,xs[1:])) or xs[0]>p['fmin_hz']+p['frequency_atol_hz']
                or xs[-1]<p['fmax_hz']-p['frequency_atol_hz']):raise ValueError('Saved frequency coverage incomplete')
        if any(not any(abs(v-required)<=p['frequency_atol_hz'] for v in xs) for required in p['required_frequencies_hz']):raise ValueError('Required frequency sample missing')
        return xs,y
    for row in p['port_ids']:
        for col in p['port_ids']:
            tree=f'1D Results\\S-Parameters\\S{row},{col}'
            xs,ys=curve(tree);count+=len(xs)
            if count>2_000_000:raise ValueError('Matrix exceeds bounded qualification size')
            if grid is not None and xs!=grid:raise ValueError('S-matrix grids differ')
            grid=xs
            if consume is not None: consume(row, col, xs, ys)
            matrix_hash.update(json.dumps([tree,xs,[[v.real,v.imag] for v in ys]],allow_nan=False).encode())
    return {'run_id':p['run_id'],'port_ids':p['port_ids'],'samples':len(grid),'matrix_sha256':matrix_hash.hexdigest(),
            'fmin_hz':grid[0],'fmax_hz':grid[-1],'parameters':stored}


def execute(runtime,job):
    p=job['params'];state=runtime.state();original=preflight(runtime.folder,state,p,job)
    project=state['projects'][p['project_id']];w=project['workflow']
    paths=[Path(project['path']),*(Path(project['path']).with_suffix('')/'Result'/name for name in ('Model.log','output.txt','Storage.sdb'))]
    before={str(path):file_digest(path) for path in paths}
    try:
        log=log_proof(paths[1].read_text(encoding='utf-8-sig'),original,p)
        data=saved_curves(project['path'],p,w['values'])
    except Exception as exc:reject('qualification_evidence_invalid',str(exc))
    after={str(path):file_digest(path) for path in paths}
    if before!=after:reject('qualification_changed','Native saved data changed during qualification')
    proof={'source_job_id':original['job_id'],'source_job_identity':source_identity(original),
        'project_digest':p['expected_digest'],'em_generation':w['em_generation'],'revision':w['revision'],
        'native_files':before,'required_parameters':dict(w['values']),'native_log':log,'saved_matrix':data,'sdk_success':False,'independent_dc_verified':False}
    # The original job remains failed/resolved with its original exception.
    w['em_receipt']={'job_id':original['job_id'],'saved_digest':p['expected_digest'],
        'em_generation':w['em_generation'],'qualification_job_id':job['job_id'],'qualification_digest':digest(proof)}
    w['evidence']=None
    runtime.update(projects=state['projects'])
    return proof


def qualified_source(folder,project,source_job):
    w=project['workflow'];receipt=w.get('em_receipt') or {};qid=receipt.get('qualification_job_id')
    if not qid:return False
    qualification=read(Path(folder)/'jobs'/(identifier(qid)+'.json'))
    if not qualification or qualification.get('status')!='succeeded' or qualification.get('operation')!='qualify_saved_em':return False
    proof=qualification.get('result') or {}
    valid = (digest(proof)==receipt.get('qualification_digest') and proof.get('source_job_id')==source_job['job_id']
        and proof.get('source_job_identity')==source_identity(source_job) and proof.get('em_generation')==w['em_generation']
        and proof.get('revision')==w['revision'] and proof.get('project_digest')==receipt['saved_digest'])

    if not valid:return False
    try:
        # Logs must still identify the qualified run. Storage may grow after a
        # legitimate circuit save, so re-read the fixed positive EM run itself.
        logpath=str(Path(project['path']).with_suffix('')/'Result'/'Model.log')
        if file_digest(logpath)!=proof['native_files'][logpath]:return False
        storage=Path(project['path']).with_suffix('')/'Result'/'Storage.sdb'
        before=file_digest(storage)
        actual=saved_curves(project['path'],qualification['params'],proof['required_parameters'])
        return actual==proof['saved_matrix'] and file_digest(storage)==before
    except (OSError,ValueError,KeyError,RuntimeError):
        return False
