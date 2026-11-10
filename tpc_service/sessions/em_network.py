"""Generation-bound preparation of a passive HB network in the owning session."""
from pathlib import Path
from cst_automation.em_network import CAPABILITY, OPERATIONS, touchstone
from .store import read, alive, identifier
from .native import file_digest
from .workflow import reject, check_evidence, live_checks, _hash_artifacts


def current_em(folder, project, em_job_id):
    w=project['workflow']; receipt=w.get('em_receipt')
    job=read(Path(folder)/'jobs'/(identifier(em_job_id)+'.json'))
    from .em_qualification import qualified_source
    if (not receipt or receipt['job_id']!=em_job_id or receipt['em_generation']!=w['em_generation']
            or not job or (job.get('status')!='succeeded' and not qualified_source(folder,project,job)) or job.get('operation')!='solve'
            or job.get('params',{}).get('project_id')!=project['project_id']):
        reject('network_em_required','Current successful EM job required')


def preflight(folder,state,operation,p):
    if state.get('worker') and alive(state['worker']) and CAPABILITY not in state.get('worker_capabilities',[]):
        reject('worker_upgrade_required','Network handoff requires an upgraded idle worker')
    project=state['projects'][p['project_id']];w=project['workflow']
    current_em(folder,project,p['em_job_id'])
    if operation=='fit_em_network':
        directory=Path(project['path']).with_suffix('')/'Export'/'ABCD'
        if any(directory.glob(p['block_name']+'*')):
            reject('network_export_exists','Existing block exports must be archived before fitting')
        for path in p['export_paths'].values():
            target=Path(path)
            if target.parent.resolve()!=directory.resolve() or not target.name.startswith(p['block_name']):
                reject('network_export_path','Exports must use the native block prefix in the owning Export/ABCD directory')
            if target.exists(): reject('network_export_exists','Archive prior exports before a new fit; no overwrite',path=str(target))
    else:
        fit=w.get('network_fit')
        job=read(Path(folder)/'jobs'/(identifier(p['fit_job_id'])+'.json'))
        if (not fit or fit['job_id']!=p['fit_job_id'] or fit['em_generation']!=w['em_generation']
                or not job or job.get('status')!='succeeded' or job.get('operation')!='fit_em_network'
                or job.get('params',{}).get('project_id')!=p['project_id']
                or fit['params']['expected_ports']!=p['expected_ports']):
            reject('network_fit_required','Matching successful native fitting receipt required')
        _hash_artifacts(fit['receipt']['artifacts'])
        check_evidence(folder,project)
        report=w['evidence']['report']
        items={(str(Path(a['path']).resolve()).casefold(),a['sha256']) for a in report['artifacts']}
        required=fit['receipt']['artifacts']+[{'path':p['path'],'sha256':p['sha256']}]
        if any((str(Path(a['path']).resolve()).casefold(),a['sha256']) not in items for a in required):
            reject('network_evidence_required','Accepted analysis must include fitting outputs and new Touchstone')
        metric=report['metrics'].get('mor_fit_max_abs_error')
        from cst_automation.workflow import number
        try:
            if not 0 <= number(metric) <= p['max_fit_error']: raise ValueError('MOR fit error outside limit')
            if file_digest(p['path'])!=p['sha256']: raise ValueError('New input digest changed')
            touchstone(p['path'],len(p['expected_ports']),p['reference_ohm'],p['fmax_hz'])
        except (ValueError,TypeError,OSError) as exc: reject('network_input_invalid',str(exc))


def check_hb(folder,project,app=None):
    w=project['workflow']
    if not w.get('network_required'): return
    update=w.get('network_update')
    if not update or update['em_generation']!=w['em_generation']:
        reject('network_update_required','Current fitted network update required before HB')
    job=read(Path(folder)/'jobs'/(identifier(update['job_id'])+'.json'))
    if not job or job.get('status')!='succeeded': reject('network_update_required','Network update job is not successful')
    if update.get('kind') == 'embedded':
        from .embedded_network import check_hb as check_embedded
        return check_embedded(folder,project,update,app)
    p=update['params']
    preflight(folder,{'projects':{project['project_id']:project}},'update_hb_network',p)
    if app is not None:
        from cst_solver.circuit.em_network import observe
        try:
            _,actual=observe(app,p,file_block=True)
            if actual!=update['receipt']['after']: raise ValueError('Native HB network differs from accepted input')
        except Exception as exc: reject('network_native_mismatch',str(exc))


def execute(runtime,job,app):
    from cst_solver.circuit import em_network as native
    from tpc_service.errors import ServiceError
    p=job['params'];operation=job['operation'];state=runtime.state()
    project=state['projects'][p['project_id']];w=project['workflow']
    live_checks(app,w,'em')
    w['network_required']=True
    w['network_update']=None
    if operation=='fit_em_network': w['network_fit']=None
    w['hb_generation']+=1
    runtime.update(projects=state['projects'])
    try:
        receipt=native.fit(app,p,project['path']) if operation=='fit_em_network' else native.update(app,p)
        # No model history rebuild, EM solve, HB solve, or source/load edits.
        runtime.save(app,p['project_id'])
    except Exception as exc:
        raise ServiceError('session_network_partial',str(exc),operation=operation,requested=p,
                           mutation_may_have_occurred=True) from exc
    state=runtime.state();w=state['projects'][p['project_id']]['workflow']
    key='network_fit' if operation=='fit_em_network' else 'network_update'
    w[key]={'job_id':job['job_id'],'em_generation':w['em_generation'],'params':p,'receipt':receipt}
    runtime.update(projects=state['projects'])
    return dict(receipt,saved=True,em_generation=w['em_generation'],solver_verified=False)
