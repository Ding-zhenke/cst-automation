"""One long-lived process, one SDK thread, one environment. No client-owned handles."""
import sys
import time
import copy
import hashlib
import marshal
import os
from pathlib import Path

from tpc_service.errors import ServiceError
from .store import lock, process_identity, read, write
from .diagnostics import mark_stage, exception_diagnostics, exception_repr
from .manager import FENCED_OPERATIONS
from .job_index import JobIndex
from .schematic_recovery import OPERATION as SCHEMATIC_RECOVERY, ROLLBACK_ERROR, returned_vba_error


def _code_fingerprint(function):
    try:
        code = getattr(function, '__code__', None)
        return hashlib.sha256(marshal.dumps(code)).hexdigest() if code is not None else None
    except Exception:
        return None


def _worker_runtime_info():
    operations = sys.modules.get('tpc_service.sessions.operations')
    functions = {'run': run, 'finish_failed_job': _finish_failed_job,
                 'known_saved_geometry': _known_saved_geometry, 'known_saved_solve': _known_saved_solve,
                 'monitor_completion': _monitor_completion, 'recorded_monitor_failure': _recorded_monitor_failure,
                 'operations_execute': getattr(operations, 'execute', None)}
    return dict(pid=os.getpid(), executable=sys.executable, python_version=sys.version,
                implementation_revision='workflow-enforcement-v1', marshal_version=marshal.version,
                code_fingerprints={name: _code_fingerprint(function) for name, function in functions.items()})


def _monitor_completion(monitor, *, prior_failure=None):
    if monitor is None:
        return prior_failure, None
    try:
        snapshot = monitor.snapshot()
    except Exception as exc:
        snapshot = dict(state='monitor_error', evidence_source='worker_snapshot_error', snapshot_error=exception_repr(exc))
        return prior_failure or monitor.failure or snapshot, snapshot
    return prior_failure or monitor.failure, snapshot


def _recorded_monitor_failure(error):
    return (error.get('details', {}).get('session_monitor') or {}).get('first_failure')


def _error_for_exception(exc, runtime, job):
    if isinstance(exc, ServiceError):
        return exc.to_dict()
    try:
        details = exception_diagnostics(exc, runtime, job)
    except Exception as diagnostic_error:
        # Diagnostics must never bypass failure fencing for the original error.
        details = {'exception_type': type(exc).__name__, 'stage': 'worker.execute',
                   'diagnostic_error_type': type(diagnostic_error).__name__,
                   'diagnostics_incomplete': True}
    return {'code': 'session_operation_failed', 'message': exception_repr(exc),
            'details': {'diagnostics': details}}


def _known_saved_solve(job, error, state, monitor_failure):
    """Only a returned operation + its verified saved receipt avoids uncertainty."""
    params = job.get('params', {})
    circuit = (job.get('operation') == 'circuit' and params.get('kind', 'build') == 'solve'
               and params.get('settings', {}).get('operation') == 'run_task'
               and error.get('code') == 'session_circuit_failed')
    solve = job.get('operation') == 'solve' and error.get('code') == 'session_solve_unverified'
    if (not (solve or circuit)
            or monitor_failure or _recorded_monitor_failure(error)
            or state.get('uncertain_jobs') or state.get('launch_intent')
            or state.get('status') != 'ready'):
        return False
    details = error.get('details', {})
    project_id = job.get('params', {}).get('project_id')
    project = state.get('projects', {}).get(project_id, {})
    outcome = details.get('execution_receipt', {}) if circuit else details.get('outcome', {})
    digest = details.get('saved_digest')
    if (details.get('project_id') != project_id or details.get('saved') is not True
            or details.get('execution_returned') is not True or outcome.get('execution_returned') is not True
            or outcome.get('submitted') is not True or not outcome.get('run_token')
            or project.get('saved') is not True or not digest or project.get('saved_digest') != digest):
        return False
    if circuit and (outcome.get('saved') is not True or outcome.get('saved_digest') != digest):
        return False
    if circuit:
        settings = params['settings']
        identity = details.get('outcome', {}).get('run_identity', {})
        if (outcome.get('task_name') != settings.get('task_name')
                or outcome.get('mode') != settings.get('mode')
                or any(identity.get(key) != outcome.get(key) for key in ('run_token', 'task_name', 'mode'))):
            return False
    try:
        from .native import file_digest
        return (Path(outcome['project']).resolve() == Path(project['path']).resolve()
                and file_digest(project['path']) == digest)
    except (KeyError, TypeError, ValueError, OSError):
        return False


def _known_saved_geometry(job, error, state, monitor_failure):
    if (job.get('operation') not in ('set_parameters', 'model_api', 'configure_sweep', 'history')
            or error.get('code') != 'session_geometry_unverified' or monitor_failure or _recorded_monitor_failure(error)
            or state.get('status') != 'ready' or state.get('launch_intent') or state.get('uncertain_jobs')):
        return False
    details = error.get('details', {})
    proof = details.get('geometry_outcome', {})
    validation = proof.get('validation', {})
    project_id = job.get('params', {}).get('project_id')
    record = state.get('projects', {}).get(project_id, {})
    digest = details.get('saved_digest')
    if (details.get('project_id') != project_id or details.get('saved') is not True
            or details.get('execution_returned') is not True or proof.get('execution_returned') is not True
            or proof.get('validation_returned') is not True or proof.get('saved') is not True
            or validation.get('rebuild_performed') is not True or validation.get('rebuild_returned') is not True
            or proof.get('operation') != job.get('operation') or not job.get('job_id') or not job.get('operation_id')
            or proof.get('job_id') != job['job_id'] or proof.get('operation_id') != job['operation_id']
            or proof.get('validation_passed') is not False or proof.get('geometry_verified') is not False
            or record.get('saved') is not True or not digest or proof.get('saved_digest') != digest
            or record.get('saved_digest') != digest or details.get('validation') != validation):
        return False
    try:
        from .native import file_digest
        return Path(proof['project']).resolve() == Path(record['path']).resolve() and file_digest(record['path']) == digest
    except (KeyError, OSError, TypeError, ValueError):
        return False


def _finish_failed_job(job, error, state, *, monitor_failure=None, monitor_snapshot=None):
    monitor_failure = monitor_failure or _recorded_monitor_failure(error)
    prior = state.get('status')
    if monitor_failure is not None or monitor_snapshot is not None:
        error = dict(error, details=dict(error.get('details', {}), session_monitor=dict(
            first_failure=copy.deepcopy(monitor_failure), final_snapshot=copy.deepcopy(monitor_snapshot),
            failure_latched=bool(monitor_failure))))
    known = _known_saved_solve(job, error, state, monitor_failure)
    geometry = _known_saved_geometry(job, error, state, monitor_failure)
    schematic_error_returned = returned_vba_error(job, error)
    job.update(status='failed', error=error, finished_at=time.time())
    job['worker_runtime'] = _worker_runtime_info()
    evidence = dict(prior_status=prior, monitor_failure_seen=bool(monitor_failure),
                    monitor_snapshot_available=monitor_snapshot is not None,
                    launch_intent=bool(state.get('launch_intent')),
                    uncertain_job_count=len(state.get('uncertain_jobs') or []),
                    known_saved_solve=known, known_saved_geometry=geometry)
    if schematic_error_returned:
        evidence['schematic_call_state'] = 'returned_native_vba_error'
    job['completion_evidence'] = evidence
    if (job.get('workflow_preflight_rejected') is True and error.get('code', '').startswith('workflow_')
            and not monitor_failure):
        evidence.update(decision=prior, reason='workflow_rejected_before_native_access')
        return
    if (job.get('operation') == 'accept_saved_baseline'
            and job.get('baseline_acceptance_read_only') is True and not monitor_failure):
        evidence.update(decision=prior, reason='read_only_baseline_refusal_preserved_state')
        return
    if job.get('operation') in ('qualify_saved_em', 'qualify_exploratory_em') and not monitor_failure:
        evidence.update(decision=prior, reason='read_only_qualification_preserved_state')
        return
    if (job.get('operation') == 'inspect' and job.get('params', {}).get('read_only_review') is True
            and not monitor_failure):
        state['last_read_review_error'] = error
        evidence.update(decision=prior, reason='read_only_review_preserved_state')
        return  # A bounded getter failure neither lifts nor adds a write fence.
    if (job.get('operation') in ('capture_failed_static','complete_failed_static_task','inspect_failed_static_task','exclude_unconnected_self_em','read_fenced_static_impedances')
            and error.get('code') == 'session_static_recovery_refused' and not monitor_failure):
        state['last_static_recovery_error'] = error
        evidence.update(decision=prior, reason='static_recovery_refused_before_mutation')
        return
    if (job.get('operation') == 'initialize_parameters' and error.get('code') == 'session_initial_parameters_refused'
            and not monitor_failure):
        evidence.update(decision=prior, reason='initial_parameters_refused_before_mutation')
        return
    if job.get('operation') == 'review_native_static_sp' and not monitor_failure:
        evidence.update(decision=prior, reason='read_only_static_review_preserved_state')
        return
    if (job.get('operation') == 'prepare_native_static_sp' and error.get('code') == 'session_native_static_refused'
            and not monitor_failure):
        evidence.update(decision=prior, reason='native_static_prepare_refused_before_write')
        return
    if (job.get('operation') == 'run_native_static_sp' and error.get('code') == 'session_native_static_refused'
            and not monitor_failure):
        evidence.update(decision=prior, reason='native_static_run_refused_before_update')
        return
    if (job.get('operation') == 'read_native_static_sp' and error.get('code') == 'session_native_static_read_refused'
            and not monitor_failure):
        evidence.update(decision=prior, reason='native_static_read_refused_without_mutation')
        return
    if (job.get('operation') == 'run_fenced_static_sp'
            and error.get('code') in ('session_static_recovery_refused','session_static_run_refused') and not monitor_failure):
        state['last_static_run_error'] = error
        evidence.update(decision=prior, reason='static_run_refused_before_update')
        return
    if (job.get('operation') == 'read_fenced_static_sp'
            and error.get('code') == 'session_static_read_refused' and not monitor_failure):
        state['last_static_read_error'] = error
        evidence.update(decision=prior, reason='static_read_refused_without_mutation')
        return
    if job['operation'] == SCHEMATIC_RECOVERY and error.get('code') != ROLLBACK_ERROR and not monitor_failure:
        state['last_schematic_recovery_error'] = error
        evidence.update(decision=prior, reason='schematic_recovery_refused_before_mutation')
        return
    if geometry:
        details = error['details']
        job['result'] = dict(saved=True, saved_digest=details['saved_digest'],
                             geometry_outcome=details['geometry_outcome'], execution_state='returned_saved',
                             review_required=True, geometry_verified=False)
        state['status'] = 'ready'
    elif known:
        details = error['details']
        outcome = details.get('execution_receipt', details['outcome'])
        job['result'] = dict(saved=True, saved_digest=details['saved_digest'],
                             solver_outcome=outcome, execution_state='returned_saved',
                             review_required=True)
        if job['operation'] == 'circuit':
            job['result']['circuit_outcome'] = details['outcome']
        state['status'] = 'ready'
    else:
        state['status'] = 'close_failed' if job['operation'] == 'close' else 'needs_reconcile'
    reason = ('monitor_failure_latched' if monitor_failure else 'prior_state_not_ready' if prior != 'ready'
              else 'unknown_predecessor' if state.get('uncertain_jobs') else 'launch_intent_unresolved' if state.get('launch_intent')
              else 'verified_returned_saved' if known or geometry
              else 'schematic_vba_error_partial_write_possible' if schematic_error_returned else 'saved_receipt_not_verified')
    evidence.update(decision=state['status'], reason=reason)
    state['last_error'] = error


def run(folder):
    from .native import Runtime
    folder = Path(folder).resolve()
    with lock(folder / 'worker.lock', blocking=False):
        with lock(folder / 'state.lock'):
            state = read(folder / 'session.json')
            native_upgrade = state.get('worker_upgrade') or {}
            if native_upgrade.get('mode') == 'preserve_native_de_v1':
                from .native_handoff import admit_worker, STARTUP_ENV, error_record
                try:
                    admit_worker(state, os.environ.pop(STARTUP_ENV, None))
                except Exception as exc:
                    native_upgrade['startup_error'] = error_record(exc)
                    write(folder/'session.json',state)
                    return  # No native handle acquired; keep the original identity and freeze.
            if state.get('worker_upgrade', {}).get('phase') in ('reviewing', 'stop_requested'):
                return  # A concurrent legacy resume must not replace the frozen worker.
            state['worker'] = process_identity(os.getpid())
            from .manager import UPGRADE_CAPABILITY
            from .workflow import CAPABILITY
            from .model_api import SETTINGS_ONLY_CAPABILITY, MESH_SETTINGS_CAPABILITY, MODEL_BAND_CAPABILITY, HF_TET_ADAPTATION_CAPABILITY
            from .read_review import CAPABILITY as READ_REVIEW_CAPABILITY
            from cst_automation.port_replacement import CAPABILITY as PORT_CAPABILITY
            from cst_automation.em_network import CAPABILITY as NETWORK_CAPABILITY
            from cst_automation.em_qualification import CAPABILITY as QUALIFICATION_CAPABILITY
            from cst_automation.embedded_network import CAPABILITY as EMBEDDED_CAPABILITY
            from .saved_baseline import CAPABILITY as BASELINE_CAPABILITY
            from cst_automation.em_qualification import EXPLORATORY_CAPABILITY
            from .native_handoff import CAPABILITY as HANDOFF_CAPABILITY
            from .linear_sp import NETWORK_CAPABILITY as EXPLORATORY_SP_NETWORK_CAPABILITY, SP_CAPABILITY
            from .model_api import HF_TET_ORDER_CAPABILITY
            state['worker_capabilities'] = [EXPLORATORY_CAPABILITY, BASELINE_CAPABILITY, EMBEDDED_CAPABILITY, QUALIFICATION_CAPABILITY, NETWORK_CAPABILITY, CAPABILITY, SETTINGS_ONLY_CAPABILITY, MESH_SETTINGS_CAPABILITY, MODEL_BAND_CAPABILITY, HF_TET_ADAPTATION_CAPABILITY, PORT_CAPABILITY, UPGRADE_CAPABILITY, READ_REVIEW_CAPABILITY]
            from .model_api import PORT_IDENTITY_CAPABILITY
            state['worker_capabilities'].append(PORT_IDENTITY_CAPABILITY)
            state['worker_capabilities'].append(HANDOFF_CAPABILITY)
            state['worker_capabilities'].append(EXPLORATORY_SP_NETWORK_CAPABILITY)
            state['worker_capabilities'].append(SP_CAPABILITY)
            state['worker_capabilities'].append(HF_TET_ORDER_CAPABILITY)
            from cst_automation.fd_linear import LF_CAPABILITY
            state['worker_capabilities'].append(LF_CAPABILITY)
            from cst_automation.settings_history import CAPABILITY as HISTORY_CAPABILITY
            state['worker_capabilities'].append(HISTORY_CAPABILITY)
            from .model_api import HF_TET_CURVATURE_CAPABILITY
            state['worker_capabilities'].append(HF_TET_CURVATURE_CAPABILITY)
            from .model_api import HF_TET_CURVATURE_POLICY_CAPABILITY
            state['worker_capabilities'].append(HF_TET_CURVATURE_POLICY_CAPABILITY)
            from cst_automation.discrete_face_port import CAPABILITY as FACE_CAPABILITY
            state['worker_capabilities'].append(FACE_CAPABILITY)
            from cst_automation.task_disable import CAPABILITY as DISABLE_CAPABILITY
            state['worker_capabilities'].append(DISABLE_CAPABILITY)
            state['worker_capabilities'].append('circuit-position-v1')
            state['worker_capabilities'].append('circuit-task-execution-v1')
            state['worker_capabilities'].append('sp-impedance-read-v1')
            state['worker_capabilities'].append('circuit-source-property-readback-v1')
            state['worker_capabilities'].append('static-sp-prepare-v1')
            state['worker_capabilities'].append('static-sp-fenced-recovery-v1')
            state['worker_capabilities'].append('static-sp-self-em-exclusion-v1')
            state['worker_capabilities'].append('static-sp-guarded-run-v1')
            state['worker_capabilities'].append('point-lumped-element-v1')
            state['worker_capabilities'].append('initial-parameters-v1')
            state['worker_capabilities'].append('native-solver-status-v1')
            state['worker_capabilities'].append('native-static-sp-v3')
            from cst_automation.discrete_ports import CAPABILITY as DISCRETE_READ_CAPABILITY
            state['worker_capabilities'].append(DISCRETE_READ_CAPABILITY)
            # A running journal means an uncertain SDK side effect. Never requeue it.
            uncertain = list(state.get('uncertain_jobs') or [])
            # Audit the original receipts once at process start. This also
            # covers restored journals whose filenames already exist in the index.
            for job in JobIndex.load(folder, rebuild=True).active_jobs():
                if job['status'] == 'needs_reconcile' and job['job_id'] not in uncertain:
                    uncertain.append(job['job_id'])
                if job['status'] == 'running':
                    path = folder / 'jobs' / (job['job_id'] + '.json')
                    from .native import file_digest
                    checkpoint = read(folder / 'checkpoints' / (job['job_id'] + '.json'))
                    project = state['projects'].get(job['params'].get('project_id'))
                    if (checkpoint and project and checkpoint.get('fingerprint') == job['fingerprint']
                            and Path(project['path']).is_file()
                            and file_digest(project['path']) == checkpoint.get('saved_digest')):
                        job.update(status='succeeded', result=checkpoint, recovered_from_checkpoint=True)
                        write(path, job)
                        continue
                    job['status'] = 'needs_reconcile'
                    job['error'] = {'code': 'execution_receipt_missing', 'message': 'Inspect before replay'}
                    write(path, job)
                    if job['job_id'] not in uncertain:
                        uncertain.append(job['job_id'])
            if uncertain or state.get('launch_intent'):
                state['status'] = 'needs_reconcile'
                state['uncertain_jobs'] = uncertain
            elif state['status'] not in ('closing', 'close_failed', 'needs_reconcile'):
                state['status'] = 'ready'
            upgrade = state.get('worker_upgrade')
            if (upgrade and upgrade.get('mode') != 'preserve_native_de_v1'
                    and upgrade.get('phase') == 'starting' and state['status'] == 'closing'
                    and not uncertain and not state.get('launch_intent') and not JobIndex.load(folder).active_jobs()):
                upgrade['new_worker_ready'] = state['worker']
            write(folder / 'session.json', state)
        runtime = Runtime(folder, state['backend'])
        if (state.get('worker_upgrade') or {}).get('mode') == 'preserve_native_de_v1':
            from .native_handoff import prepare_new_worker
            if not prepare_new_worker(runtime):
                return
        while True:
            with lock(folder / 'state.lock'):
                state = read(folder / 'session.json')
                if state['status'] == 'closed':
                    return
                upgrade = state.get('worker_upgrade')
                if (upgrade and upgrade.get('phase') == 'stop_requested'
                        and upgrade.get('old_worker') == process_identity(os.getpid())):
                    upgrade['stop_ack'] = True
                    write(folder / 'session.json', state)
                    return
                job = (None if upgrade and upgrade.get('mode') == 'preserve_native_de_v1'
                       else JobIndex.load(folder).next_queued())
                if job and state['status'] == 'needs_reconcile' and job['operation'] not in FENCED_OPERATIONS:
                    # Fence all accepted but not started writes after an uncertain predecessor.
                    job['status'] = 'blocked'
                    job['error'] = {'code': 'session_needs_reconcile', 'message': 'Predecessor outcome is uncertain'}
                    write(folder / 'jobs' / (job['job_id'] + '.json'), job)
                    job = None
                if job:
                    job['status'] = 'running'
                    job['started_at'] = time.time()
                    job['worker_runtime'] = _worker_runtime_info()
                    write(folder / 'jobs' / (job['job_id'] + '.json'), job)
            if job is None:
                if (upgrade and upgrade.get('mode') == 'preserve_native_de_v1'
                        and upgrade.get('phase') == 'release_requested'):
                    from .native_handoff import verify_release
                    if not verify_release(runtime):
                        return
                time.sleep(.1)
                continue
            monitor = None
            monitor_failure = None
            try:
                mark_stage(runtime, 'worker.monitor_setup')
                from contextlib import nullcontext
                if runtime.backend == 'cst':
                    from cst_solver.dialogs import DialogMonitor
                    def diagnostic(event):
                        with lock(folder / 'state.lock'):
                            current = read(folder / 'session.json')
                            current['runtime_diagnostics'] = event
                            write(folder / 'session.json', current)
                    monitor = DialogMonitor(job['job_id'], timeout=None,
                                            pid=lambda: (runtime.state()['environment'] or {}).get('pid'),
                                            on_event=diagnostic)
                with monitor if monitor is not None else nullcontext():
                    mark_stage(runtime, 'worker.execute')
                    result = runtime.execute(job)
                    mark_stage(runtime, 'worker.monitor_finalize')
                monitor_failure, monitor_snapshot = _monitor_completion(monitor)
                if monitor_failure:
                    raise ServiceError('cst_dialog_blocked', 'Operation returned after a detected CST dialog; inspect evidence',
                                       diagnostics=monitor_failure)
                from .workflow import record_success
                record_success(runtime, job)
                job.update(status='succeeded', result=result, finished_at=time.time())
                job['worker_runtime'] = _worker_runtime_info()
                job['completion_evidence'] = dict(decision='succeeded', reason='operation_returned_without_monitor_failure',
                                                 monitor_failure_seen=False, final_monitor_snapshot=monitor_snapshot)
            except Exception as exc:
                error = _error_for_exception(exc, runtime, job)
                monitor_failure, monitor_snapshot = _monitor_completion(monitor, prior_failure=monitor_failure)
                with lock(folder / 'state.lock'):
                    state = read(folder / 'session.json')
                    _finish_failed_job(job, error, state, monitor_failure=monitor_failure, monitor_snapshot=monitor_snapshot)
                    write(folder / 'session.json', state)
            with lock(folder / 'state.lock'):
                write(folder / 'jobs' / (job['job_id'] + '.json'), job)
                state = read(folder / 'session.json')
                if job['operation'] == 'close' and job['status'] == 'succeeded':
                    state['status'] = 'closed'
                    write(folder / 'session.json', state)
                    return


if __name__ == '__main__':
    run(sys.argv[1])
