"""Enforced source identity and durable embedded-network receipts."""
from pathlib import Path
from datetime import datetime
import re

import numpy as np

from cst_automation import embedded_network as data
from .store import read, identifier, alive
from .workflow import reject, live_checks, check_evidence, _hash_artifacts
from .em_network import current_em


def verify_source(folder, project, p):
    from .em_qualification import saved_curves
    current_em(folder, project, p['em_job_id'])
    f, s, indices = data.load_matrix(p)
    w = project['workflow']
    job = read(Path(folder)/'jobs'/(identifier(p['em_job_id'])+'.json'))
    result_dir = Path(project['path']).with_suffix('')/'Result'
    files = [result_dir/'Model.log', result_dir/'Storage.sdb']
    before = {str(v): data.digest(v) for v in files}
    log = files[0].read_text(encoding='utf-8-sig')
    samples = data.actual_lf_samples(log, p)
    qid = w['em_receipt'].get('qualification_job_id')
    if qid:
        qualification = read(Path(folder)/'jobs'/(identifier(qid)+'.json'))
        if qualification['params']['run_id'] != p['run_id']:
            raise ValueError('Requested run differs from qualified EM')
    else:
        starts = re.findall(r'Solver started at: ([0-9-]{10} [0-9:]{8} [+-][0-9]{4})', log)
        if len(starts) != 1 or re.findall(r'Creating parametric 1D results for Run ID (\d+)', log) != [str(p['run_id'])]:
            raise ValueError('Saved Run ID is not uniquely bound to the successful solve')
        start = datetime.strptime(starts[0], '%Y-%m-%d %H:%M:%S %z').timestamp()
        if not job['started_at']-1 <= start <= job['finished_at']:
            raise ValueError('Saved native run lies outside the source job window')
    ports = p['physical_port_ids']; native = np.empty_like(s)
    lookup = {port: i for i, port in enumerate(ports)}
    def consume(row, col, xs, ys):
        if len(xs) != len(f) or np.max(np.abs(np.asarray(xs)-f)) > p['frequency_atol_hz']:
            raise ValueError('Source frequency grid differs from the complete saved matrix')
        native[:, lookup[row], lookup[col]] = ys
    source = saved_curves(project['path'], dict(run_id=p['run_id'], port_ids=ports,
        fmin_hz=float(f[0]), fmax_hz=float(f[-1]), frequency_atol_hz=p['frequency_atol_hz'],
        required_frequencies_hz=p['low_frequencies_hz']),
        {k: v for k, v in w['values'].items() if w['spec']['parameters'][k]['affects'] == 'em'}, consume=consume)
    error = float(np.max(np.abs(data.renormalize(native, p['native_reference_ohms'], p['reference_ohm'])-s)))
    if not np.isfinite(error) or error > p['limits']['native_matrix_error']:
        raise ValueError('Normalized source differs from actual full saved EM matrix')
    if before != {str(v): data.digest(v) for v in files}:
        raise ValueError('Saved native source changed during validation')
    return {'saved_matrix': source, 'native_log_sha256': before[str(files[0])],
            'native_matrix_error': error, 'actual_lf_samples': samples,
            'native_reference_getter_verified': False}


def preflight(folder, state, p):
    if state.get('worker') and alive(state['worker']) and data.CAPABILITY not in state.get('worker_capabilities', []):
        reject('worker_upgrade_required', 'Embedded handoff requires an upgraded idle worker')
    project = state['projects'][p['project_id']]
    try:
        data.load_matrix(p)
        output = Path(p['output_path'])
        if output.parent.resolve() != Path(p['matrix_path']).parent.resolve():
            raise ValueError('New output must be beside the supplied matrix')
        if output.exists() or output.with_stem(output.stem+'_lf').exists():
            raise ValueError('Existing output cannot be overwritten')
        verify_source(folder, project, p)
    except (ValueError, OSError, KeyError, RuntimeError) as exc:
        reject('embedded_input_invalid', str(exc))


def execute(runtime, job, app):
    from cst_solver.circuit.embedded_network import prepare
    from tpc_service.errors import ServiceError
    p = job['params']; state = runtime.state(); project = state['projects'][p['project_id']]
    w = project['workflow']
    source = verify_source(runtime.folder, project, p)
    live_checks(app, w, 'em')
    w['network_required'] = True
    w['network_fit'] = w['network_update'] = w['evidence'] = None
    w['hb_generation'] += 1
    runtime.update(projects=state['projects'])
    try:
        receipt = prepare(app, p, project['path'], job['job_id'], lambda: runtime.save(app, p['project_id']))
        # Preserve the certified EM source through the DS-only save.
        if verify_source(runtime.folder, runtime.state()['projects'][p['project_id']], p) != source:
            raise ValueError('EM source changed during embedded handoff')
    except Exception as exc:
        raise ServiceError('session_embedded_network_partial', str(exc), requested=p,
                           mutation_may_have_occurred=True) from exc
    receipt['source'] = source
    state = runtime.state(); w = state['projects'][p['project_id']]['workflow']
    w['network_update'] = {'kind': 'embedded', 'job_id': job['job_id'], 'em_generation': w['em_generation'],
                           'params': p, 'receipt': receipt}
    runtime.update(projects=state['projects'])
    return dict(receipt, saved=True, em_generation=w['em_generation'])


def check_hb(folder, project, update, app=None):
    p, receipt = update['params'], update['receipt']
    try:
        if verify_source(folder, project, p) != receipt['source']:
            raise ValueError('Saved EM matrix changed since embedded handoff')
        _hash_artifacts(receipt['artifacts'])
        if data.digest(receipt['after']['path']) != receipt['after']['sha256']:
            raise ValueError('Effective embedded payload changed')
        check_evidence(folder, project)
        report = project['workflow']['evidence']['report']
        accepted = {(str(Path(v['path']).resolve()).casefold(), v['sha256']) for v in report['artifacts']}
        if any((str(Path(v['path']).resolve()).casefold(), v['sha256']) not in accepted for v in receipt['artifacts']):
            raise ValueError('Accepted report must include all embedded fitting artifacts')
        if app is not None:
            from cst_solver.circuit.embedded_network import observe, snapshot
            if observe(app, p, project['path']) != receipt['after'] or snapshot(app, p['block_name']) != receipt['topology']:
                raise ValueError('Native payload, ports or topology changed')
    except (ValueError, OSError, KeyError, RuntimeError) as exc:
        reject('embedded_hb_invalid', str(exc))
