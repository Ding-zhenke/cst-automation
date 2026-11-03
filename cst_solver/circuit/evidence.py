"""CST 2026 task-log evidence. Timestamps or existing curves alone are insufficient."""
import hashlib
import re


def log_completion(before, after, task_name):
    appended = bool(before and after.startswith(before))
    segment = after[len(before):] if appended else after
    tasks = re.findall(r'\bTask:\s*([^\r\n]+)', segment)
    bad = bool(re.search(r'\b(?:ERROR|FATAL|FAILED|ABORTED)\s*:|\b(?:task|solver|simulation)\s+(?:failed|aborted)\b', after, re.I))
    markers = ('Task:', 'Task time:', 'Total time:')
    old_lines = set(before.splitlines())
    fresh_markers = all(any(marker in line and (appended or line not in old_lines)
                            for line in segment.splitlines()) for marker in markers)
    warnings = bool(re.search(r'\bWARNING\s*:', segment, re.I))
    complete = (after != before and tasks == [task_name] and fresh_markers and not bad and not warnings)
    return {'completed': complete, 'log_changed': after != before,
            'log_tasks': tasks, 'log_errors': bad, 'log_warnings': warnings,
            'log_sha256_before': hashlib.sha256(before.encode()).hexdigest(),
            'log_sha256_after': hashlib.sha256(after.encode()).hexdigest()}


def configuration_complete(snapshot):
    return all(u == {'field': 'parameter_dimensions', 'status': 'unknown'}
               for u in snapshot.get('unknown', []))


def information_only(messages):
    return all(isinstance(m, dict) and m.get('type', '').upper() == 'INFO' for m in messages)


def em_log_completion(before, after, output, task_name, state, *, output_before=''):
    old_lines = set(before.splitlines())
    segment = after[len(before):] if before and after.startswith(before) else after
    fresh = all(any(marker in line and line not in old_lines for line in segment.splitlines())
                for marker in ('Solver started at:', 'Solver finished at:'))
    pattern = r'Network co-simulation:\s*Task\s+' + re.escape(task_name) + r'\s*(?:\r?\n|$)'
    binding = bool(re.search(pattern, output) and not re.search(pattern, output_before))
    errors = bool(re.search(r'\b(?:ERROR|FATAL|WARNING)\s*:|\b(?:task|solver|simulation)\s+(?:failed|aborted)\b', after + '\n' + output, re.I))
    return {'em_completed': bool(fresh and binding and 'Network co-simulation' in segment and state == 'SUCCESS' and not errors),
            'em_native_state': state, 'em_fresh_start_finish': fresh, 'em_task_binding': bool(binding),
            'em_log_sha256': hashlib.sha256(after.encode()).hexdigest(), 'em_log_errors': errors}


def time_coverage(x, duration):
    import math
    if len(x) < 2 or not math.isfinite(duration) or duration <= 0 or not all(math.isfinite(t) for t in x):
        return False
    steps = [b-a for a, b in zip(x, x[1:])]
    max_step = max(steps)
    return (all(step > 0 for step in steps) and max_step <= min(duration / 1000, 1e-11) and
            x[0] <= 0 and x[-1] >= duration - min(2 * max_step, duration / 4000, 1e-11))


def cosim_evidence(app, snapshot, task_name, last):
    """Calibrated self MWS discrete-port case; reject unsupported mappings."""
    import math
    from pathlib import Path
    from cst_solver.environment import _load_cst_module
    root = Path(last['path']).with_suffix('')
    read = lambda p: p.read_text(encoding='utf-8-sig', errors='replace') if p.is_file() else ''
    state = app.cst_file.model3d.get_solver_run_info()
    proof = em_log_completion(last.get('em_log_before', ''), read(root / 'Result/Model.log'),
                              read(root / 'Result/output.txt'), task_name, state.get('state'),
                              output_before=last.get('em_output_before', ''))
    proof.update(em_runs=[], reason='Matching fresh EM task execution and complete port time curves required')
    if not proof['em_completed']:
        return proof
    candidates = [b for b in snapshot['blocks'] if b['type'].lower() == 'cst microwave studio schematic block'
                  and b['files'] and len(b['files']) == 1 and Path(b['files'][0]).resolve() == Path(last['path'])]
    if len(candidates) != 1:
        proof.update(em_completed=False, reason='Only one associated self MWS block is calibrated')
        return proof
    ports = [p['pin_name'] for p in candidates[0]['pins']]
    if not ports or not all(p.isdecimal() and int(p) > 0 for p in ports):
        proof.update(em_completed=False, reason='Only discrete ports with numeric pin names are calibrated')
        return proof
    task = app.cst_file.schematic.SimulationTask
    task.Reset(); task.Name(task_name)
    scales = {'s': 1., 'ms': 1e-3, 'us': 1e-6, 'ns': 1e-9, 'ps': 1e-12, 'fs': 1e-15}
    duration = float(task.GetProperty('tmax')) * scales[str(app.cst_file.schematic.Units.GetUnit('Time'))]
    module = _load_cst_module('cst.results').ProjectFile(last['path'], allow_interactive=True).get_3d()
    items = module.get_tree_items()
    for port in ports:
        for quantity in ('Voltages', 'Currents'):
            path = f'1D Results\\Discrete Ports\\{quantity}\\Signals\\Port {port} [cosim {task_name}]'
            if path not in items or 0 not in module.get_run_ids(path):
                proof.update(em_completed=False, reason='Missing target cosim EM voltage/current time curve')
                return proof
            item = module.get_result_item(path, run_id=0)
            label = item.xlabel
            if not label.startswith('Time / ') or label[7:] not in scales:
                proof.update(em_completed=False, reason='EM time unit is unavailable')
                return proof
            x = [float(v) * scales[label[7:]] for v in item.get_xdata()]
            y = [complex(v) for v in item.get_ydata()]
            if (not time_coverage(x, duration) or len(x) != len(y) or
                    not all(math.isfinite(v.real) and math.isfinite(v.imag) for v in y) or
                    not y):
                proof.update(em_completed=False, reason='EM signals do not cover the requested duration or contain invalid data')
                return proof
            proof['em_runs'].append({'domain': '3d', 'tree_path': path, 'run_id': 0,
                                     'samples': len(x), 'end_time_s': x[-1],
                                     'sample_digest': hashlib.sha256(repr((x, y)).encode()).hexdigest()})
    proof['reason'] = 'Fresh target EM execution, SUCCESS state and both time signals for every associated discrete port'
    return proof
