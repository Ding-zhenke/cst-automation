"""One long-lived process, one SDK thread, one environment. No client-owned handles."""
import sys
import time
from pathlib import Path

from tpc_service.errors import ServiceError
from .store import lock, process_identity, read, write
from .diagnostics import mark_stage, exception_diagnostics, exception_repr


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
            or monitor_failure or state.get('uncertain_jobs') or state.get('launch_intent')
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
            or error.get('code') != 'session_geometry_unverified' or monitor_failure
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


def _finish_failed_job(job, error, state, *, monitor_failure=None):
    known = _known_saved_solve(job, error, state, monitor_failure)
    geometry = _known_saved_geometry(job, error, state, monitor_failure)
    job.update(status='failed', error=error, finished_at=time.time())
    if (job.get('operation') == 'inspect' and job.get('params', {}).get('read_only_review') is True
            and not monitor_failure):
        state['last_read_review_error'] = error
        return  # A bounded getter failure neither lifts nor adds a write fence.
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
    state['last_error'] = error


def run(folder):
    from .native import Runtime
    import os
    folder = Path(folder).resolve()
    with lock(folder / 'worker.lock', blocking=False):
        with lock(folder / 'state.lock'):
            state = read(folder / 'session.json')
            state['worker'] = process_identity(os.getpid())
            # A running journal means an uncertain SDK side effect. Never requeue it.
            uncertain = []
            for path in (folder / 'jobs').glob('*.json'):
                job = read(path)
                if job['status'] == 'running':
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
                    uncertain.append(job['job_id'])
            if uncertain or state.get('launch_intent'):
                state['status'] = 'needs_reconcile'
                state['uncertain_jobs'] = uncertain
            elif state['status'] not in ('closing', 'close_failed', 'needs_reconcile'):
                state['status'] = 'ready'
            write(folder / 'session.json', state)
        runtime = Runtime(folder, state['backend'])
        while True:
            with lock(folder / 'state.lock'):
                state = read(folder / 'session.json')
                queue = sorted((read(p) for p in (folder / 'jobs').glob('*.json')),
                               key=lambda j: j['sequence'])
                job = next((j for j in queue if j['status'] == 'queued'), None)
                if state['status'] == 'closed':
                    return
                if job and state['status'] == 'needs_reconcile' and job['operation'] not in ('inspect', 'close'):
                    # Fence all accepted but not started writes after an uncertain predecessor.
                    job['status'] = 'blocked'
                    job['error'] = {'code': 'session_needs_reconcile', 'message': 'Predecessor outcome is uncertain'}
                    write(folder / 'jobs' / (job['job_id'] + '.json'), job)
                    job = None
                if job:
                    job['status'] = 'running'
                    job['started_at'] = time.time()
                    write(folder / 'jobs' / (job['job_id'] + '.json'), job)
            if job is None:
                time.sleep(.1)
                continue
            monitor = None
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
                if monitor is not None and monitor.failure:
                    raise ServiceError('cst_dialog_blocked', 'Operation returned after a detected CST dialog; inspect evidence',
                                       diagnostics=monitor.failure)
                job.update(status='succeeded', result=result, finished_at=time.time())
            except Exception as exc:
                error = _error_for_exception(exc, runtime, job)
                with lock(folder / 'state.lock'):
                    state = read(folder / 'session.json')
                    _finish_failed_job(job, error, state, monitor_failure=monitor.failure if monitor else None)
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
