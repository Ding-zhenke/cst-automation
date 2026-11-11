"""Source checks for experimental linear SP; no permission to run HB or SP."""
from pathlib import Path

from .em_qualification import saved_curves, source_identity
from .native import file_digest
from .store import identifier, read

NETWORK_CAPABILITY = 'exploratory-sp-network-v1'
SP_CAPABILITY = 'exploratory-linear-sp-v1'


def validate_setup(p):
    import math
    if not isinstance(p, dict) or set(p) != {'project_id', 'network_job_id', 'task', 'ports'}:
        raise ValueError('Exact project, network, task and ports required')
    identifier(p['project_id']); identifier(p['network_job_id'])
    task = p['task']
    if not isinstance(task, dict) or set(task) != {'task_name', 'frequency_unit', 'fmin', 'fmax', 'samples', 'port_impedances'}:
        raise ValueError('Exact SP task settings required')
    name = task['task_name']
    if (not isinstance(name, str) or not name.strip() or any(c in name for c in '\r\n\x00\\')
            or task['frequency_unit'] not in ('Hz', 'kHz', 'MHz', 'GHz')
            or any(type(task[k]) not in (int, float) or not math.isfinite(task[k]) for k in ('fmin', 'fmax'))
            or not 0 <= task['fmin'] < task['fmax'] or type(task['samples']) is not int
            or not 2 <= task['samples'] <= 100000):
        raise ValueError('Invalid task or frequency settings')
    ports = p['ports']; impedances = task['port_impedances']
    if not isinstance(ports, list) or not 1 <= len(ports) <= 128 or not isinstance(impedances, dict):
        raise ValueError('Explicit external ports and impedances required')
    names, nets = set(), set()
    for row in ports:
        if not isinstance(row, dict) or set(row) != {'name', 'position', 'net_name', 'expected_members'}:
            raise ValueError('Exact port fields required')
        name, net, pos, members = row['name'], row['net_name'], row['position'], row['expected_members']
        if (not isinstance(name, str) or not name.strip() or name in names or any(c in name for c in '\r\n\x00')
                or not isinstance(net, str) or not net.strip() or net in nets or any(c in net for c in '\r\n\x00')
                or not isinstance(pos, list) or len(pos) != 2
                or any(type(v) not in (int, float) or not math.isfinite(v) for v in pos)
                or not isinstance(members, list) or not members):
            raise ValueError('Invalid port, position, net or expected membership')
        for member in members:
            if (not isinstance(member, list) or len(member) != 3
                    or not isinstance(member[0], str) or not isinstance(member[1], str)
                    or type(member[2]) is not int or member[2] < 0):
                raise ValueError('Invalid native net member')
        names.add(name); nets.add(net)
    if set(impedances) != names or any(type(v) not in (int, float) or not math.isfinite(v) or v <= 0 for v in impedances.values()):
        raise ValueError('Each new port needs a finite positive reference impedance')


def validate_solve(p):
    from cst_solver.circuit.results import task_result_path
    if not isinstance(p, dict) or set(p) != {'project_id', 'network_job_id', 'setup_job_id', 'task_name', 'expected_results'}:
        raise ValueError('Exact solve request required')
    for k in ('project_id', 'network_job_id', 'setup_job_id'): identifier(p[k])
    name = p['task_name']; results = p['expected_results']
    if (not isinstance(name, str) or not name.strip() or not isinstance(results, list) or not results
            or any(not isinstance(item, dict) or set(item) != {'tree_path', 'run_id'}
                   or not isinstance(item['tree_path'], str) or not task_result_path(item['tree_path'], name)
                   or '\\s-parameters\\' not in item['tree_path'].casefold()
                   or type(item['run_id']) is not int or item['run_id'] < 0 for item in results)):
        raise ValueError('Task-scoped result paths and nonnegative Run IDs required')


def network_options(params):
    from cst_automation.embedded_network import validate
    if not isinstance(params, dict) or 'qualification_job_id' not in params:
        raise ValueError('Exploratory qualification job required')
    identifier(params['qualification_job_id'])
    p = {key: value for key, value in params.items() if key != 'qualification_job_id'}
    validate(p)
    return p


def network_preflight(folder, state, params, job=None):
    from cst_automation import embedded_network as data
    from .store import alive
    from .workflow import reject
    from .job_index import JobIndex
    if (state.get('status') != 'ready' or state.get('uncertain_jobs') or state.get('launch_intent')
            or any(j['job_id'] != (job or {}).get('job_id') for j in JobIndex.load(folder).active_jobs())):
        reject('exploratory_sp_network_idle_required', 'Owning session must be idle and unfenced')
    if state.get('worker') and alive(state['worker']) and NETWORK_CAPABILITY not in state.get('worker_capabilities', []):
        reject('worker_upgrade_required', 'Exploratory SP network needs a compatible worker')
    try:
        p = network_options(params)
        data.load_matrix(p)
        output = Path(p['output_path'])
        if (output.parent.resolve() != Path(p['matrix_path']).parent.resolve()
                or output.exists() or output.with_stem(output.stem + '_lf').exists()):
            raise ValueError('Output must be new and beside the source matrix')
        verify_exploratory_matrix(folder, state['projects'][p['project_id']], params['qualification_job_id'], p)
    except (ValueError, OSError, KeyError, RuntimeError) as exc:
        reject('exploratory_sp_network_invalid', str(exc))


def execute_network(runtime, job, app):
    from cst_solver.circuit.embedded_network import prepare
    from tpc_service.errors import ServiceError
    from .workflow import live_checks
    params = job['params']
    p = network_options(params)
    state = runtime.state(); project = state['projects'][p['project_id']]
    source = verify_exploratory_matrix(runtime.folder, project, params['qualification_job_id'], p)
    live_checks(app, project['workflow'], 'em')
    w = project['workflow']
    w.update(network_required=True, network_fit=None, network_update=None, evidence=None, sp_network=None, sp_setup=None)
    w['hb_generation'] += 1
    runtime.update(projects=state['projects'])
    try:
        receipt = prepare(app, p, project['path'], job['job_id'], lambda: runtime.save(app, p['project_id']))
        if verify_exploratory_matrix(runtime.folder, runtime.state()['projects'][p['project_id']],
                                     params['qualification_job_id'], p) != source:
            raise ValueError('Exploratory source changed during network replacement')
    except Exception as exc:
        raise ServiceError('session_exploratory_sp_network_partial', str(exc),
                           mutation_may_have_occurred=True, requested=params) from exc
    state = runtime.state(); w = state['projects'][p['project_id']]['workflow']
    receipt['source'] = source
    w['sp_network'] = {'job_id': job['job_id'], 'em_generation': w['em_generation'],
                       'params': params, 'receipt': receipt}
    runtime.update(projects=state['projects'])
    return dict(receipt, saved=True, em_generation=w['em_generation'],
                formal_hb_gate_satisfied=False, solver_verified=False)


def check_prepared_network(folder, project, network_job_id, app=None):
    from cst_automation import embedded_network as data
    from .workflow import reject, _hash_artifacts
    w = project['workflow']; update = w.get('sp_network') or {}
    if (update.get('job_id') != network_job_id or update.get('em_generation') != w['em_generation']):
        reject('exploratory_sp_network_stale', 'Current exploratory network receipt required')
    job = read(Path(folder) / 'jobs' / (identifier(network_job_id) + '.json'))
    if (not job or job.get('status') != 'succeeded' or job.get('operation') != 'prepare_exploratory_sp_network'
            or job.get('params') != update.get('params')):
        reject('exploratory_sp_network_stale', 'Network job is not the matching completed operation')
    try:
        params = update['params']; p = network_options(params); receipt = update['receipt']
        if verify_exploratory_matrix(folder, project, params['qualification_job_id'], p) != receipt['source']:
            raise ValueError('Exploratory source changed')
        _hash_artifacts(receipt['artifacts'])
        if data.digest(receipt['after']['path']) != receipt['after']['sha256']:
            raise ValueError('Embedded payload changed')
        if app is not None:
            from cst_solver.circuit.embedded_network import observe, snapshot
            if observe(app, p, project['path']) != receipt['after'] or snapshot(app, p['block_name']) != receipt['topology']:
                raise ValueError('Native payload or circuit topology changed')
    except (ValueError, OSError, KeyError, RuntimeError) as exc:
        reject('exploratory_sp_network_invalid', str(exc))
    return update


def sp_solve_preflight(folder, state, p, job=None):
    from .workflow import reject
    from .job_index import JobIndex
    from .store import alive
    if (state.get('status') != 'ready' or state.get('uncertain_jobs') or state.get('launch_intent')
            or any(j['job_id'] != (job or {}).get('job_id') for j in JobIndex.load(folder).active_jobs())):
        reject('exploratory_sp_idle_required', 'Owning session must be idle and unfenced')
    if state.get('worker') and alive(state['worker']) and SP_CAPABILITY not in state.get('worker_capabilities', []):
        reject('worker_upgrade_required', 'Exploratory SP solve requires a compatible worker')
    project = state['projects'][p['project_id']]; w = project['workflow']; setup = w.get('sp_setup') or {}
    if (setup.get('job_id') != p['setup_job_id'] or setup.get('network_job_id') != p['network_job_id']
            or setup.get('em_generation') != w['em_generation'] or setup.get('task_name') != p['task_name']
            or setup.get('saved_digest') != project.get('saved_digest')):
        reject('exploratory_sp_setup_required', 'Current saved SP configuration receipt required')
    source_job = read(Path(folder)/'jobs'/(identifier(p['setup_job_id'])+'.json'))
    if (not source_job or source_job.get('status') != 'succeeded'
            or source_job.get('operation') != 'configure_exploratory_linear_sp'
            or source_job.get('params', {}).get('project_id') != p['project_id']
            or source_job.get('params', {}).get('network_job_id') != p['network_job_id']
            or source_job.get('params', {}).get('task') != setup.get('task')
            or source_job.get('result', {}).get('saved_digest') != setup.get('saved_digest')):
        reject('exploratory_sp_setup_required', 'Matching successful SP configuration job required')
    report = setup.get('task_report') or {}
    if (report.get('frequency_unit_readback') != setup['task'].get('frequency_unit')
            or report.get('sample_count_readback') != setup['task'].get('samples')
            or report.get('port_impedances_readback') != setup['task'].get('port_impedances')):
        reject('exploratory_sp_setup_unverified', 'Frequency unit, sampling and port impedances need native readback')
    check_prepared_network(folder, project, p['network_job_id'])
    return setup


def setup_preflight(folder, state, p, job=None):
    from .workflow import reject
    from .job_index import JobIndex
    from .store import alive
    validate_setup(p)
    if (state.get('status') != 'ready' or state.get('uncertain_jobs') or state.get('launch_intent')
            or any(j['job_id'] != (job or {}).get('job_id') for j in JobIndex.load(folder).active_jobs())):
        reject('exploratory_sp_idle_required', 'Owning session must be idle and unfenced')
    if state.get('worker') and alive(state['worker']) and SP_CAPABILITY not in state.get('worker_capabilities', []):
        reject('worker_upgrade_required', 'Exploratory SP setup requires a compatible worker')
    project = state['projects'][p['project_id']]
    update = check_prepared_network(folder, project, p['network_job_id'])
    from cst_automation import embedded_network as data
    f, _, _ = data.load_matrix(network_options(update['params']))
    scale = {'Hz': 1, 'kHz': 1e3, 'MHz': 1e6, 'GHz': 1e9}[p['task']['frequency_unit']]
    if p['task']['fmax'] * scale > float(f[-1]):
        reject('exploratory_sp_coverage_invalid', 'SP upper frequency exceeds the saved network')
    reject('exploratory_sp_setup_readback_unsupported',
           'Native readback of task sample count and constant impedance is not yet supported')


def execute_setup(runtime, job, app):
    from cst_solver.circuit.adapter import attach_external_port_to_net, iterate
    from cst_solver.circuit.embedded_network import snapshot, observe
    from cst_solver.circuit.linear_sp import configure_linear_sp_task
    from tpc_service.errors import ServiceError
    from .workflow import live_checks
    p = job['params']; validate_setup(p)
    state = runtime.state(); project = state['projects'][p['project_id']]
    update = check_prepared_network(runtime.folder, project, p['network_job_id'], app)
    live_checks(app, project['workflow'], 'em')
    adapter = app.circuit.adapter; schematic = adapter.schematic
    before = snapshot(app, update['params']['block_name'])
    existing = list(iterate(schematic.ExternalPort, 'StartPortNameIteration', 'GetNextPortName'))
    if existing:
        raise ServiceError('exploratory_sp_setup_conflict', 'Existing external ports require an explicitly supported full port mapping')
    task = schematic.SimulationTask; task.Reset(); task.Name(p['task']['task_name'])
    if task.DoesExist():
        raise ServiceError('exploratory_sp_setup_conflict', 'SP task already exists')
    w = project['workflow']; w.update(sp_setup=None, network_required=True, network_update=None, evidence=None)
    w['hb_generation'] += 1
    runtime.update(projects=state['projects'])
    try:
        for row in p['ports']:
            port = schematic.ExternalPort; port.Reset(); port.Name(row['name'])
            port.Position(*row['position']); port.Create()
            port.Reset(); port.Name(row['name'])
            if int(port.GetNumberOfPorts()) != 1:
                raise ValueError('New external port does not expose one endpoint')
            attach_external_port_to_net(schematic.Net, row['net_name'],
                                        ['Externalport', row['name'], 0], row['expected_members'])
        spec = p['task']
        task_report = configure_linear_sp_task(schematic, spec['task_name'],
            frequency_unit=spec['frequency_unit'], fmin=spec['fmin'], fmax=spec['fmax'],
            samples=spec['samples'], port_impedances=spec['port_impedances'])
        after = snapshot(app, update['params']['block_name'])
        for key in ('blocks', 'probes', 'units', 'parameters', 'unknown'):
            if before[key] != after[key]: raise ValueError('Existing circuit changed: ' + key)
        if ([v for v in after['external_ports'] if v['name'] not in {r['name'] for r in p['ports']}]
                != before['external_ports']): raise ValueError('Existing external ports changed')
        if ([v for v in after['tasks'] if v['name'] != spec['task_name']] != before['tasks']):
            raise ValueError('Existing tasks changed')
        if observe(app, network_options(update['params']), project['path']) != update['receipt']['after']:
            raise ValueError('Embedded network payload changed')
        saved = runtime.save(app, p['project_id'])
        project = runtime.state()['projects'][p['project_id']]
        if snapshot(app, update['params']['block_name']) != after:
            raise ValueError('Circuit topology changed during save')
        check_prepared_network(runtime.folder, project, p['network_job_id'])
    except Exception as exc:
        raise ServiceError('session_exploratory_sp_setup_partial', str(exc),
                           mutation_may_have_occurred=True, requested=p) from exc
    state = runtime.state(); project = state['projects'][p['project_id']]; w = project['workflow']
    w['sp_setup'] = {'job_id': job['job_id'], 'network_job_id': p['network_job_id'],
                     'em_generation': w['em_generation'], 'task_name': spec['task_name'],
                     'saved_digest': saved['saved_digest'], 'task': spec, 'topology': after,
                     'task_report': task_report}
    runtime.update(projects=state['projects'])
    return {'saved': True, 'saved_digest': saved['saved_digest'], 'task_report': task_report,
            'solver_verified': False, 'formal_hb_gate_satisfied': False}


def execute_sp_solve(runtime, job, app):
    from cst_solver.circuit.embedded_network import snapshot, observe
    from .workflow import live_checks
    from tpc_service.errors import ServiceError
    from .operations import circuit
    p = job['params']; validate_solve(p)
    state = runtime.state(); project = state['projects'][p['project_id']]
    setup = sp_solve_preflight(runtime.folder, state, p, job=job)
    update = check_prepared_network(runtime.folder, project, p['network_job_id'])
    live_checks(app, project['workflow'], 'em')
    if (snapshot(app, update['params']['block_name']) != setup['topology']
            or observe(app, network_options(update['params']), project['path']) != update['receipt']['after']):
        raise ServiceError('exploratory_sp_native_mismatch', 'Native circuit or payload changed after SP setup')
    task = app.circuit.adapter.select('SimulationTask', p['task_name'])
    props = setup['task_report']['properties_readback']
    if (not task.DoesExist() or str(task.GetTypeForTask(p['task_name'])).casefold() != 's-parameters'
            or str(task.GetUnit('Frequency')) != setup['task']['frequency_unit']
            or str(task.GetUnit('Resistance')) != 'Ohm'
            or any(str(task.GetPortImpedanceType(name)) != mode['impedance_type']
                   or str(task.GetPortSourceType(name)) != mode['source_type']
                   for name, mode in setup['task_report']['port_modes'].items())
            or any(str(task.GetProperty(k)) != v for k, v in props.items())):
        raise ServiceError('exploratory_sp_native_mismatch', 'Native SP task differs from setup receipt')
    requested = {'project_id': p['project_id'], 'kind': 'solve', 'settings': {
        'operation': 'run_task', 'task_name': p['task_name'], 'mode': 'network',
        'expected_results': p['expected_results'], 'reuse': 'never'}}
    result = circuit(runtime, app, project, requested)
    return {'circuit_result': result, 'source_network_job_id': p['network_job_id'],
            'setup_job_id': p['setup_job_id'], 'purpose': 'exploratory_linear_sp',
            'formal_hb_gate_satisfied': False,
            'reference_impedance_readback': 'unsupported'}


def check_exploratory_source(folder, project, qualification_job_id):
    """Recheck the original receipt and fixed native run after circuit-only saves."""
    job = read(Path(folder) / 'jobs' / (identifier(qualification_job_id) + '.json'))
    if (not job or job.get('status') != 'succeeded' or job.get('operation') != 'qualify_exploratory_em'
            or job.get('params', {}).get('project_id') != project['project_id']):
        raise ValueError('Matching successful exploratory qualification required')
    proof = job.get('result') or {}
    workflow = project['workflow']
    if (proof.get('purpose') != 'exploratory_ads_handoff'
            or proof.get('workflow_revision') != workflow['revision']
            or proof.get('em_generation') != workflow['em_generation']):
        raise ValueError('Exploratory qualification is stale or has the wrong purpose')
    original = read(Path(folder) / 'jobs' / (identifier(proof.get('source_job_id')) + '.json'))
    if (not original or original.get('status') != 'failed' or original.get('operation') != 'solve'
            or original.get('params', {}).get('project_id') != project['project_id']
            or source_identity(original) != proof.get('source_job_identity')):
        raise ValueError('Original failed solver receipt changed')
    result_dir = Path(project['path']).with_suffix('') / 'Result'
    log = result_dir / 'Model.log'
    storage = result_dir / 'Storage.sdb'
    try:
        if file_digest(log) != proof['native_files'][str(log)]:
            raise ValueError('Original native EM log changed')
        before = file_digest(storage)
        expected = proof['saved_matrix']
        values = {name: value for name, value in workflow['values'].items()
                  if workflow['spec']['parameters'][name]['affects'] == 'em'}
        actual = saved_curves(project['path'], job['params'], values)
        if actual != expected or file_digest(storage) != before or file_digest(log) != proof['native_files'][str(log)]:
            raise ValueError('Native EM result changed during source validation')
    except (OSError, KeyError, RuntimeError) as exc:
        raise ValueError('Exploratory source is unavailable or incomplete') from exc
    return proof


def verify_exploratory_matrix(folder, project, qualification_job_id, p):
    """Compare an explicit exported full matrix against the qualified native run."""
    import numpy as np
    from cst_automation import embedded_network as data
    proof = check_exploratory_source(folder, project, qualification_job_id)
    job = read(Path(folder) / 'jobs' / (identifier(qualification_job_id) + '.json'))
    options = job['params']
    if (p['project_id'] != project['project_id'] or p['em_job_id'] != proof['source_job_id']
            or p['run_id'] != options['run_id'] or p['physical_port_ids'] != options['port_ids']
            or options['max_residual'] > p['limits']['native_sample_residual']
            or any(not any(abs(v - required) <= options['frequency_atol_hz']
                           for v in options['required_frequencies_hz'])
                   for required in p['low_frequencies_hz'])):
        raise ValueError('Matrix identity or direct low-frequency evidence differs')
    f, s, _ = data.load_matrix(p)
    ports = p['physical_port_ids']
    indexes = {port: i for i, port in enumerate(ports)}
    native = np.empty_like(s)
    seen = set()
    def consume(row, col, xs, ys):
        if ((row, col) in seen or row not in indexes or col not in indexes
                or len(xs) != len(f) or len(ys) != len(f)
                or np.max(np.abs(np.asarray(xs) - f)) > p['frequency_atol_hz']):
            raise ValueError('Native curve grid or identity differs')
        native[:, indexes[row], indexes[col]] = ys
        seen.add((row, col))
    workflow = project['workflow']
    values = {name: value for name, value in workflow['values'].items()
              if workflow['spec']['parameters'][name]['affects'] == 'em'}
    actual = saved_curves(project['path'], options, values, consume=consume)
    if actual != proof['saved_matrix'] or seen != {(r, c) for r in ports for c in ports}:
        raise ValueError('Native matrix coverage or qualification changed')
    error = float(np.max(np.abs(data.renormalize(native, p['native_reference_ohms'], p['reference_ohm']) - s)))
    if not np.isfinite(error) or error > p['limits']['native_matrix_error']:
        raise ValueError('Exported matrix differs from native source')
    if data.digest(p['matrix_path']) != p['matrix_sha256']:
        raise ValueError('Matrix changed during comparison')
    check_exploratory_source(folder, project, qualification_job_id)
    return {'source_job_id': proof['source_job_id'], 'qualification_job_id': qualification_job_id,
            'max_matrix_error': error, 'matrix_sha256': p['matrix_sha256'],
            'formal_hb_gate_satisfied': False, 'solver_verified': False}
