"""Mandatory engineering gates for the owning persistent session."""
import copy
import json
from pathlib import Path

from cst_automation.workflow import digest, normalize, number, parameter_changes, within
from tpc_service.errors import ServiceError
from .native import file_digest
from .store import alive, read, write, identifier

CAPABILITY = 'parameter-em-hb-v1'
READ_CIRCUIT = frozenset(('inspect', 'read_results', 'read_run_parameters', 'package', 'stage_postprocessing_template'))
PARAMETER_SWEEPS = frozenset(('configure_sweep', 'configure_discrete_sweep',
    'add_sweep_parameter_arbitrary_points', 'add_parameter_sweep_sequence', 'add_sweep_parameter_samples'))


def reject(code, message, **details):
    raise ServiceError('workflow_' + code, message, **details)


def marker(path):
    return Path(str(Path(path).resolve()) + '.workflow.json')


def reject_unowned_route(path):
    if marker(path).exists():
        reject('owning_session_required', 'Protected project must use its owning session')


def protected(operation, params):
    return operation in ('set_parameters', 'solve', 'accept_workflow_evidence', 'fit_em_network', 'update_hb_network', 'qualify_saved_em', 'qualify_exploratory_em', 'prepare_hb_embedded_network', 'prepare_exploratory_sp_network', 'configure_exploratory_linear_sp', 'run_exploratory_linear_sp') or (
        operation == 'circuit' and params.get('kind', 'build') in ('solve', 'study'))


def mutates(operation, params):
    if operation in ('set_parameters', 'model_api', 'history', 'configure_sweep'):
        return True
    return operation == 'circuit' and params.get('kind', 'build') == 'build' and params.get('settings', {}).get('operation') not in READ_CIRCUIT


def check_worker(state):
    if state.get('worker') and alive(state['worker']):
        if CAPABILITY not in state.get('worker_capabilities', []):
            reject('worker_upgrade_required', 'Existing worker lacks workflow enforcement; wait for safe upgrade')


def bind(folder, state, project_id, spec, expected_revision):
    from .job_index import JobIndex
    project = state['projects'].get(project_id)
    if not project or project.get('tab_closed'):
        reject('project_required', 'An open registered project is required')
    if state['status'] != 'ready' or state.get('uncertain_jobs') or state.get('launch_intent') or JobIndex.load(folder).active_jobs():
        reject('busy', 'Bind or revise a specification only with an idle, resolved session')
    check_worker(state)
    try:
        spec = normalize(spec)
    except (ValueError, TypeError, KeyError) as exc:
        reject('spec_invalid', str(exc))
    old = project.get('workflow')
    revision = digest(spec)
    if old and old['revision'] == revision:
        return {'revision': revision, 'project_id': project_id, 'unchanged': True}
    if (old and expected_revision != old['revision']) or (not old and expected_revision is not None):
        reject('revision_conflict', 'Updating the specification requires its current revision')
    target = marker(project['path'])
    ownership = {'session_folder': str(Path(folder).resolve()), 'project_id': project_id}
    existing = read(target)
    if existing and existing != ownership:
        reject('owner_mismatch', 'Project already has a different workflow owner')
    if file_digest(project['path']) != project.get('saved_digest'):
        reject('project_changed', 'Saved project changed before binding')
    project['workflow'] = {'revision': revision, 'spec': spec, 'values': copy.deepcopy(spec['initial_values']),
                           'em_generation': 0, 'hb_generation': 0, 'em_receipt': None, 'evidence': None}
    # Fail closed if interrupted between marker and durable state publication.
    write(target, ownership)
    write(Path(folder) / 'session.json', state)
    return {'revision': revision, 'project_id': project_id, 'started_cst': False}


def _hash_artifacts(artifacts):
    if not isinstance(artifacts, list) or not artifacts:
        reject('evidence_invalid', 'Numerical report requires nonempty source artifacts')
    seen = set()
    for item in artifacts:
        if not isinstance(item, dict) or set(item) != {'path', 'sha256'}:
            reject('evidence_invalid', 'Artifact requires path and sha256 only')
        path = Path(item['path'])
        if not path.is_absolute() or str(path.resolve()) in seen:
            reject('evidence_invalid', 'Unique absolute artifact paths required')
        seen.add(str(path.resolve()))
        try:
            if file_digest(path) != item['sha256']:
                reject('artifact_changed', 'Evidence artifact changed', path=str(path))
        except OSError as exc:
            reject('artifact_unavailable', str(exc), path=str(path))


def evidence_report(folder, project, params):
    workflow = project['workflow']
    receipt = workflow.get('em_receipt')
    if not receipt or receipt['job_id'] != params.get('em_job_id') or receipt['em_generation'] != workflow['em_generation']:
        reject('evidence_required', 'Current successful EM receipt required')
    job = read(Path(folder) / 'jobs' / (identifier(params['em_job_id']) + '.json'))
    from .em_qualification import qualified_source
    if not job or (job['status'] != 'succeeded' and not qualified_source(folder, project, job)) or job['operation'] != 'solve' or job['params']['project_id'] != project['project_id']:
        reject('evidence_invalid', 'EM source job is not a successful solve of this project')
    path = Path(params.get('report_path', ''))
    if not path.is_absolute():
        reject('evidence_invalid', 'Absolute analysis report path required')
    try:
        raw = path.read_bytes()
        if len(raw) > 4_000_000:
            raise ValueError('Analysis report too large')
        report = json.loads(raw.decode('utf-8-sig'))
        if set(report) != {'em_job_id', 'em_saved_digest', 'metrics', 'artifacts'}:
            raise ValueError('Analysis report fields differ from schema')
        if report['em_job_id'] != receipt['job_id'] or report['em_saved_digest'] != receipt['saved_digest']:
            raise ValueError('Analysis report belongs to another EM execution')
        for name, rule in workflow['spec']['evidence_rules'].items():
            within(report['metrics'][name], rule)
        _hash_artifacts(report['artifacts'])
    except (OSError, ValueError, TypeError, KeyError) as exc:
        reject('evidence_invalid', str(exc))
    return {'report': report, 'report_path': str(path), 'report_sha256': __import__('hashlib').sha256(raw).hexdigest(),
            'revision': workflow['revision'], 'em_generation': workflow['em_generation'], 'em_job_id': receipt['job_id']}


def check_evidence(folder, project):
    workflow = project['workflow']
    evidence = workflow.get('evidence')
    if not evidence or evidence['revision'] != workflow['revision'] or evidence['em_generation'] != workflow['em_generation']:
        reject('evidence_required', 'Current accepted EM analysis evidence required before HB')
    actual = evidence_report(folder, project, {'em_job_id': evidence['em_job_id'], 'report_path': evidence['report_path']})
    if actual != evidence:
        reject('artifact_changed', 'Accepted analysis report changed; collect evidence again')


def preflight(folder, state, operation, params, *, job=None):
    from cst_automation.task_disable import is_request, normalize, CAPABILITY as DISABLE_CAPABILITY
    if is_request(operation, params):
        try:
            normalize(params['settings'])
            if params.get('kind') != 'build':
                raise ValueError('Task disable requires explicit build kind')
        except (ValueError, TypeError) as exc:
            reject('request_invalid', str(exc))
        if (job is not None or state.get('worker')) and DISABLE_CAPABILITY not in state.get('worker_capabilities', []):
            reject('worker_upgrade_required', 'Task disable requires a compatible idle worker')
    if operation == 'accept_saved_baseline':
        from .saved_baseline import preflight as baseline_preflight
        return baseline_preflight(folder, state, params, job)
    project = state['projects'].get(params.get('project_id'))
    workflow = project.get('workflow') if project else None
    standalone_transient = (operation == 'circuit' and params.get('kind') == 'solve'
        and params.get('settings', {}).get('operation') == 'run_network_transient')
    if standalone_transient:
        settings = params['settings']
        from cst_solver.circuit.results import task_result_path
        if (set(settings) - {'operation', 'task_name', 'expected_results', 'note'}
                or not isinstance(settings.get('task_name'), str) or not settings['task_name']
                or not isinstance(settings.get('note', ''), str)
                or not isinstance(settings.get('expected_results'), list) or not settings['expected_results']
                or any(not isinstance(row, dict) or not isinstance(row.get('tree_path'), str)
                       or not task_result_path(row['tree_path'], settings['task_name'])
                       or type(row.get('run_id')) is not int or row['run_id'] < 0
                       for row in settings['expected_results'])):
            reject('transient_request_invalid', 'Explicit task/results required; MOR reuse and cancellation are unsupported')
    if standalone_transient and workflow:
        reject('route_unsupported', 'Standalone transient cannot bypass an existing protected workflow')
    if not workflow:
        if project and marker(project['path']).exists():
            reject('owner_mismatch', 'Protected project has no matching session contract')
        if protected(operation, params) and not standalone_transient and state['backend'] == 'cst':
            reject('required', 'Bind an engineering specification before parameter/EM/HB execution')
        return None
    relevant = protected(operation, params) or mutates(operation, params)
    if not relevant:
        return None
    if read(marker(project['path'])) != {'session_folder': str(Path(folder).resolve()), 'project_id': params['project_id']}:
        reject('owner_mismatch', 'Workflow ownership marker is missing or changed')
    if job is None:
        check_worker(state)
    expected = {'revision': workflow['revision'], 'em_generation': workflow['em_generation'],
                'hb_generation': workflow['hb_generation']}
    if job is not None and job.get('workflow_guard') != expected:
        reject('stale_request', 'Contract or inputs changed after submission')
    try:
        if file_digest(project['path']) != project.get('saved_digest'):
            reject('project_changed', 'Project changed outside its owning session')
    except OSError as exc:
        reject('project_changed', str(exc))
    if operation in ('history', 'configure_sweep') or (operation == 'circuit' and params.get('kind') == 'study'):
        reject('route_unsupported', 'Raw history and unmanaged studies cannot bypass the guarded chain')
    if operation == 'model_api':
        if any(call['method'] in PARAMETER_SWEEPS for call in params['calls']):
            reject('route_unsupported', 'Native geometry sweep requires a guarded per-case implementation')
    if operation == 'set_parameters':
        try:
            parameter_changes(workflow['spec'], params['values'])
            descriptions = params.get('expressions', {})
            if (not isinstance(descriptions, dict) or any(name not in params['values']
                    or not isinstance(value, str) for name, value in descriptions.items())):
                raise ValueError('expressions must map value keys to description strings')
        except (ValueError, TypeError) as exc:
            reject('parameter_invalid', str(exc))
    if operation == 'prepare_hb_embedded_network':
        from .embedded_network import preflight as embedded_preflight
        embedded_preflight(folder, state, params)
    if operation == 'prepare_exploratory_sp_network':
        from .linear_sp import network_preflight
        network_preflight(folder, state, params, job=job)
    if operation == 'configure_exploratory_linear_sp':
        from .linear_sp import setup_preflight
        setup_preflight(folder, state, params, job=job)
    if operation == 'run_exploratory_linear_sp':
        from .linear_sp import sp_solve_preflight
        sp_solve_preflight(folder, state, params, job=job)
    if operation == 'qualify_saved_em':
        from .em_qualification import preflight as qualify_preflight
        qualify_preflight(folder, state, params, job)
    if operation == 'qualify_exploratory_em':
        from .exploratory_em import preflight as exploratory_preflight
        exploratory_preflight(folder, state, params, job)
    if operation in ('fit_em_network', 'update_hb_network'):
        from .em_network import preflight as network_preflight
        network_preflight(folder, state, operation, params)
    if operation == 'accept_workflow_evidence':
        evidence_report(folder, project, params)
    if operation == 'circuit' and params.get('kind') == 'solve':
        settings, spec = params['settings'], workflow['spec']
        if (settings.get('operation') != 'run_task' or settings.get('task_name') != spec['hb_task']
                or settings.get('reuse', 'never') != 'never'
                or any(settings.get(k) != v for k, v in spec['hb_request'].items())):
            reject('hb_request_mismatch', 'HB request differs from the bound task/specification')
        results = settings.get('expected_results')
        from cst_solver.circuit.results import task_result_path
        if (not isinstance(results, list) or not results or any(
                not isinstance(item, dict) or not isinstance(item.get('tree_path'), str)
                or not task_result_path(item['tree_path'], spec['hb_task']) or type(item.get('run_id')) is not int
                or item['run_id'] < 0 for item in results)):
            reject('hb_request_mismatch', 'Explicit result tree paths and nonnegative integer run IDs required')
        check_evidence(folder, project)
        from .em_network import check_hb
        check_hb(folder, project)
    return expected


def live_checks(app, workflow, stage):
    """Use bounded native getters, never a caller's passed/readback flag."""
    try:
        for name, expected in workflow['values'].items():
            actual = float(app.get_parameter(name))
            number(actual)
            expression = str(app.cst_file.model3d.RestoreParameterExpression(name))
            number(float(expression))  # independent numeric parameters cannot alias another one
            if actual != expected:
                reject('native_mismatch', 'Native parameter differs from the current target', parameter=name)
        for check in workflow['spec'][stage + '_checks']:
            if check['source'] == 'parameter':
                actual = app.get_parameter(check['name'])
            else:
                kind = 'Block' if check['source'] == 'block_property' else 'SimulationTask'
                obj = app.circuit.adapter.select(kind, check['name'])
                if not obj.DoesExist():
                    reject('native_mismatch', 'Required native object is missing', name=check['name'])
                actual = obj.GetProperty(check['property'])
            expected = check['expected']
            if type(expected) in (int, float):
                actual = number(float(actual))
                matches = abs(actual - expected) <= check.get('atol', 0)
            else:
                matches = str(actual) == expected
            if not matches:
                reject('native_mismatch', 'Native setting differs from specification', check=check, actual=actual)
    except ServiceError:
        raise
    except Exception as exc:
        reject('native_unavailable', 'Required native readback unavailable: ' + str(exc))


def invalidate(runtime, job):
    state = runtime.state()
    project = state['projects'][job['params']['project_id']]
    workflow = project.get('workflow')
    if not workflow or not (mutates(job['operation'], job['params']) or job['operation'] == 'solve'):
        return
    operation, params = job['operation'], job['params']
    affects_em = operation != 'circuit' or params.get('settings', {}).get('operation') == 'configure_em_time_settings'
    if operation == 'set_parameters':
        affects_em = any(workflow['spec']['parameters'][n]['affects'] == 'em' for n in params['values'])
        workflow['values'].update(params['values'])
    if operation == 'circuit' or affects_em:
        workflow['network_update'] = None
        workflow['sp_network'] = None
        workflow['sp_setup'] = None
    if affects_em:
        workflow['network_fit'] = None
    workflow['hb_generation'] += 1
    if affects_em:
        workflow['em_generation'] += 1
        workflow['em_receipt'] = workflow['evidence'] = None
    runtime.update(projects=state['projects'])


def record_success(runtime, job):
    if job['operation'] != 'solve' or runtime.backend != 'cst':
        return
    state = runtime.state()
    project = state['projects'][job['params']['project_id']]
    workflow = project.get('workflow')
    if workflow:
        workflow['em_receipt'] = {'job_id': job['job_id'], 'saved_digest': project['saved_digest'],
                                  'em_generation': workflow['em_generation']}
        workflow['evidence'] = None
        runtime.update(projects=state['projects'])
