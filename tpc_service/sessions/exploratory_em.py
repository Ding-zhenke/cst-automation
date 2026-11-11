"""Separate warning-bearing saved EM evidence for external exploration."""
from pathlib import Path

from cst_automation.em_qualification import EXPLORATORY_CAPABILITY, exploratory_log_proof
from .em_qualification import saved_curves, source_identity
from .native import file_digest
from .store import alive, identifier, read
from .workflow import reject


def preflight(folder, state, p, job=None):
    from .job_index import JobIndex
    project=state['projects'][p['project_id']]; workflow=project['workflow']
    if (state['status']!='ready' or state.get('uncertain_jobs') or state.get('launch_intent')
            or any(j['job_id']!=(job or {}).get('job_id') for j in JobIndex.load(folder).active_jobs())):
        reject('exploratory_idle_required','Owning session must be idle and resolved')
    if state.get('worker') and alive(state['worker']) and EXPLORATORY_CAPABILITY not in state.get('worker_capabilities',[]):
        reject('worker_upgrade_required','Exploratory qualification requires a compatible worker')
    original=read(Path(folder)/'jobs'/(identifier(p['em_job_id'])+'.json'))
    if not original or original.get('status')!='failed' or original.get('operation')!='solve' or original.get('params',{}).get('project_id')!=p['project_id']:
        reject('exploratory_source_invalid','Original failed owning solve required')
    error=original.get('error') or {}; details=error.get('details') or {}; outcome=details.get('outcome') or {}
    result=original.get('result') or {}; completion=original.get('completion_evidence') or {}
    errors=outcome.get('errors') or []; messages=outcome.get('messages') or []
    if (error.get('code')!='session_solve_unverified' or outcome.get('status')!='unverified'
            or outcome.get('submitted') is not True or outcome.get('execution_returned') is not True
            or details.get('execution_returned') is not True or details.get('saved') is not True
            or details.get('saved_digest')!=p['expected_digest'] or result.get('saved_digest')!=p['expected_digest']
            or result.get('saved') is not True or result.get('execution_state')!='returned_saved'
            or result.get('review_required') is not True or completion.get('known_saved_solve') is not True
            or completion.get('monitor_failure_seen') is not False or completion.get('monitor_snapshot_available') is not True
            or (details.get('session_monitor') or {}).get('failure_latched') is not False
            or ((details.get('session_monitor') or {}).get('final_snapshot') or {}).get('state') != 'clear'
            or completion.get('launch_intent') is not False
            or completion.get('uncertain_job_count')!=0 or not errors
            or any(e.get('code')!='run_warnings' for e in errors)
            or not any(m.get('type')=='WARNING' for m in messages)
            or any(m.get('type') not in ('INFO','WARNING') for m in messages)):
        reject('exploratory_source_invalid','Returned/saved warning-only evidence is incomplete')
    warnings={m.get('text') for m in messages if m.get('type')=='WARNING'}
    if warnings != set(p['acknowledged_warnings']):
        reject('exploratory_warning_review_required','All warning texts must match the explicit review')
    guard=original.get('workflow_guard') or {}
    if guard.get('revision')!=workflow['revision'] or any(workflow[k]!=guard.get(k,-2)+1 for k in ('em_generation','hb_generation')):
        reject('exploratory_stale','Workflow inputs changed after source solve')
    if project.get('saved_digest')!=p['expected_digest'] or file_digest(project['path'])!=p['expected_digest']:
        reject('exploratory_changed','Saved project differs from source solve')
    return original


def execute(runtime, job):
    p=job['params']; state=runtime.state(); original=preflight(runtime.folder,state,p,job)
    project=state['projects'][p['project_id']]; workflow=project['workflow']
    paths=[Path(project['path']),*(Path(project['path']).with_suffix('')/'Result'/name for name in ('Model.log','output.txt','Storage.sdb'))]
    before={str(path):file_digest(path) for path in paths}
    try:
        log=exploratory_log_proof(paths[1].read_text(encoding='utf-8-sig'),original,p)
        matrix=saved_curves(project['path'],p,workflow['values'])
    except Exception as exc:
        reject('exploratory_evidence_invalid',str(exc))
    if before!={str(path):file_digest(path) for path in paths}:
        reject('exploratory_changed','Saved data changed during evidence collection')
    messages=original['error']['details']['outcome']['messages']
    return {'purpose':'exploratory_ads_handoff','source_job_id':original['job_id'],
            'source_job_identity':source_identity(original),'project_digest':p['expected_digest'],
            'workflow_revision':workflow['revision'],'em_generation':workflow['em_generation'],
            'native_files':before,'native_log':log,'saved_matrix':matrix,
            'warnings':[m for m in messages if m.get('type')=='WARNING'],
            'mesh_convergence':'unknown','solver_verified':False,'independent_dc_verified':False,
            'formal_hb_gate_satisfied':False}
