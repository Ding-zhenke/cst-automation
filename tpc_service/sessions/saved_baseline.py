"""Explicit adoption of a reviewed external save, without native writes."""
import copy
import json
from pathlib import Path
import time

from cst_automation.em_network import sha, text, finite
from cst_automation.workflow import digest
from .store import alive, assert_environment_unclaimed, identifier, lock, read, write
from .native import file_digest
from .workflow import reject, marker, live_checks

OPERATION = 'accept_saved_baseline'
CAPABILITY = 'reviewed-saved-baseline-v1'


def validate(p):
    fields = {'project_id', 'old_digest', 'new_digest', 'environment_identity',
        'expected_parameters', 'expected_blocks', 'expected_block_properties',
        'review_path', 'review_sha256', 'review_note', 'authorization_note',
        'confirm_idle', 'confirm_saved_tab', 'accept_external_save'}
    if not isinstance(p, dict) or set(p) != fields: raise ValueError('Exact baseline review fields required')
    identifier(p['project_id'])
    for key in ('old_digest', 'new_digest', 'review_sha256'): sha(p[key])
    if p['old_digest'] == p['new_digest']: raise ValueError('External save must differ from registration')
    for key in ('confirm_idle', 'confirm_saved_tab', 'accept_external_save'):
        if p[key] is not True: raise ValueError('Explicit review and acceptance confirmations required')
    for key in ('review_note', 'authorization_note'): text(p[key])
    env = p['environment_identity']
    if (not isinstance(env, dict) or set(env) != {'pid', 'started', 'image'}
            or type(env['pid']) is not int or env['pid'] <= 0
            or type(env['started']) not in (int, str) or not env['started']):
        raise ValueError('Complete explicit environment identity required')
    text(env['image'])
    if not isinstance(p['review_path'], str) or not Path(p['review_path']).is_absolute():
        raise ValueError('Absolute review JSON path required')
    for key in ('expected_parameters', 'expected_blocks', 'expected_block_properties'):
        if not isinstance(p[key], dict) or len(p[key]) > 10000: raise ValueError('Bounded review maps required')
        for name in p[key]: text(name)
    if not p['expected_parameters']: raise ValueError('Complete nonempty parameter review required')
    for item in p['expected_parameters'].values():
        if not isinstance(item, dict) or set(item) != {'value', 'expression'}:
            raise ValueError('Each parameter requires exact value and expression')
        finite(item['value']); text(item['expression'])
    for value in p['expected_blocks'].values(): text(value)
    for name, properties in p['expected_block_properties'].items():
        if name not in p['expected_blocks'] or not isinstance(properties, dict) or not 1 <= len(properties) <= 1000:
            raise ValueError('Property review must refer to a declared block')
        for name, value in properties.items():
            text(name)
            if isinstance(value, str): text(value)
            else: finite(value)


def review_file(p):
    path = Path(p['review_path'])
    if path.stat().st_size > 4_000_000 or file_digest(path) != p['review_sha256']:
        raise ValueError('Review document changed or exceeds limit')
    if not isinstance(json.loads(path.read_text(encoding='utf-8-sig')), dict):
        raise ValueError('Review document must be a JSON object')


def preflight(folder, state, p, job=None):
    from .job_index import JobIndex
    try:
        validate(p)
        if (state.get('backend') != 'cst' or state.get('status') != 'ready'
                or state.get('uncertain_jobs') or state.get('launch_intent') or state.get('close_requested')
                or (state.get('runtime_diagnostics') or {}).get('state', 'clear') != 'clear'):
            raise ValueError('Only a ready, resolved CST session can accept an external save')
        if any(j['job_id'] != (job or {}).get('job_id') for j in JobIndex.load(folder).active_jobs()):
            raise ValueError('Other active or unknown tasks prevent baseline acceptance')
        if not alive(state.get('worker')) or CAPABILITY not in state.get('worker_capabilities', []):
            raise ValueError('An already-running compatible owning worker is required; no restart performed')
        if state.get('environment') != p['environment_identity'] or not alive(state['environment']):
            raise ValueError('The exact reviewed environment is no longer live')
        record = state['projects'].get(p['project_id'])
        if (not record or record.get('project_id') != p['project_id'] or record.get('tab_closed')
                or record.get('saved') is not True or record.get('saved_digest') != p['old_digest']
                or file_digest(record['path']) != p['new_digest']):
            raise ValueError('Old registration or current saved-file digest differs from review')
        if record.get('workflow') or marker(record['path']).exists():
            if not record.get('workflow') or read(marker(record['path'])) != {
                    'session_folder': str(Path(folder).resolve()), 'project_id': p['project_id']}:
                raise ValueError('Workflow ownership differs')
            for name, value in record['workflow']['values'].items():
                if p['expected_parameters'].get(name, {}).get('value') != value:
                    raise ValueError('Reviewed parameters must preserve the current workflow targets')
        review_file(p)
        guard = {'baseline_revision': digest({'environment': state['environment'],
            'environment_generation': state.get('environment_generation'), 'path': record['path'],
            'saved_digest': record['saved_digest'], 'workflow': record.get('workflow')})}
        if job is not None and job.get('workflow_guard') != guard:
            raise ValueError('Registration or workflow changed after review submission')
        return guard
    except (ValueError, TypeError, KeyError, OSError) as exc:
        reject('baseline_refused', str(exc))


def native_review(app, handle, p):
    from cst_solver.circuit.adapter import iterate
    from .inspection import inspect_native
    if handle.model3d.is_solver_running(timeout=5) is not False:
        raise ValueError('Native EM solver is not confirmed idle')
    actual = inspect_native(app, {'solid_names': []})
    for value in actual['parameters'].values(): finite(value['value'])
    if (actual['errors'] or actual['parameters'] != p['expected_parameters']
            or int(handle.model3d.GetNumberOfParameters()) != len(p['expected_parameters'])):
        raise ValueError('Complete native parameter names, values or expressions differ from review')
    block = handle.schematic.Block
    blocks = {}
    for name in list(iterate(block, 'StartBlockNameIteration', 'GetNextBlockName')):
        if name in blocks: raise ValueError('Duplicate native block name')
        obj = app.circuit.adapter.select('Block', name)
        blocks[name] = str(obj.GetTypeName())
    if blocks != p['expected_blocks']: raise ValueError('Complete native block types differ from review')
    properties = {}
    for name, checks in p['expected_block_properties'].items():
        obj = app.circuit.adapter.select('Block', name)
        properties[name] = {}
        for key, expected in checks.items():
            value = obj.GetProperty(key)
            value = str(value) if isinstance(expected, str) else finite(float(value))
            if value != expected: raise ValueError('Native block property differs: '+name+'.'+key)
            properties[name][key] = value
    return {'parameters': actual['parameters'], 'blocks': blocks, 'block_properties': properties}


def execute(runtime, job):
    from cst_solver.dialogs import check_dialogs
    from .read_review import borrow_open_project
    from .project_lifecycle import path_key
    p = job['params']
    job['baseline_acceptance_read_only'] = True
    state = runtime.state()
    preflight(runtime.folder, state, p, job)
    record = state['projects'][p['project_id']]; identity = state['environment']
    with lock(runtime.folder.parent/'registry.lock'):
        assert_environment_unclaimed(runtime.folder.parent, state['session_id'], identity)
    # Dialog inspection failures are not ordinary read-only review refusals.
    job['baseline_acceptance_read_only'] = False
    check_dialogs('review external saved baseline', pid=identity['pid'])
    job['baseline_acceptance_read_only'] = True
    app, handle, opened = borrow_open_project(runtime, identity, record['path'])
    app.cst_file = handle
    actual = native_review(app, handle, p)
    if record.get('workflow'): live_checks(app, record['workflow'], 'em')
    job['baseline_acceptance_read_only'] = False
    check_dialogs('finish external saved baseline review', pid=identity['pid'])
    job['baseline_acceptance_read_only'] = True
    if native_review(app, handle, p) != actual:
        reject('baseline_refused', 'Native review changed before baseline commit')
    if (not alive(identity) or path_key(handle.filename()) != path_key(record['path'])
            or {path_key(v) for v in app.project.list_open_projects()} != set(opened)
            or handle.model3d.is_solver_running(timeout=5) is not False):
        reject('baseline_refused', 'Native tab, environment or idle state changed during review')
    # One atomic state write publishes audit, baseline and invalidation together.
    # No old job or error receipt is rewritten and no native save is performed.
    with lock(runtime.folder.parent/'registry.lock'), lock(runtime.folder/'state.lock'):
        state = read(runtime.folder/'session.json')
        preflight(runtime.folder, state, p, job)
        assert_environment_unclaimed(runtime.folder.parent, state['session_id'], identity)
        record = state['projects'][p['project_id']]
        old_workflow = copy.deepcopy(record.get('workflow'))
        if old_workflow:
            w = record['workflow']
            w['em_generation'] += 1; w['hb_generation'] += 1
            for key in ('em_receipt', 'evidence', 'network_fit', 'network_update'): w[key] = None
        audit = {'job_id': job['job_id'], 'project_id': p['project_id'], 'path': record['path'],
            'old_digest': p['old_digest'], 'new_digest': p['new_digest'],
            'environment_identity': identity, 'review_path': p['review_path'], 'review_sha256': p['review_sha256'],
            'review_note': p['review_note'], 'authorization_note': p['authorization_note'],
            'review_authorized_by_caller': True, 'saved_tab_confirmed_by_caller': True,
            'native_review_sha256': digest(actual), 'previous_workflow_sha256': digest(old_workflow),
            'em_idle_verified': True, 'circuit_idle_verified': False,
            'whole_model_disk_equivalence_verified': False, 'solver_verified': False, 'at': time.time()}
        record.update(saved_digest=p['new_digest'], saved=True)
        state.setdefault('baseline_acceptances', []).append(audit)
        job['baseline_acceptance_read_only'] = False  # persistence failure must not be treated as a getter refusal
        write(runtime.folder/'session.json', state)
    runtime.app = app; runtime.handles[p['project_id']] = handle
    facade = getattr(app, '_circuit_facade', None)
    if facade is not None: facade._spec = None
    return {'accepted': True, 'audit': audit, 'native_review': actual,
            'invalidated_workflow': old_workflow, 'saved': False, 'solver_verified': False}
