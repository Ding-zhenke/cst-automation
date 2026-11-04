"""Explicit retirement of closed session process copies, without native calls."""
from pathlib import Path
import time

from tpc_service.errors import ServiceError
from .diagnostics import mark_stage
from .store import lock, read


def retire_closed_project(runtime, job):
    from .validation import validate
    from .native import file_digest
    from .formal_paths import same_path
    params = job['params']
    validate('close_project', params)
    project_id = params['project_id']
    folder = Path(runtime.folder).resolve()
    # Share the acceptance lock so a new queued operation cannot slip between
    # the empty-queue check and moving the registration into retired_projects.
    with lock(folder.parent / 'registry.lock'):
        mark_stage(runtime, 'project.retire_preflight')
        state = runtime.state()
        record = state['projects'].get(project_id) or state.get('retired_projects', {}).get(project_id)
        if not record or record.get('project_id') != project_id:
            raise ServiceError('project_not_registered', 'Retirement requires the same registered owner')
        process_root = folder / 'projects' / project_id
        raw_path = Path(record['path'])
        path = raw_path.resolve()
        if not raw_path.is_absolute() or path.suffix.lower() != '.cst' or process_root not in path.parents:
            raise ServiceError('session_retirement_scope', 'Only this session project process directory may be retired')
        if (state.get('status') != 'ready' or state.get('uncertain_jobs') or state.get('launch_intent')
                or state.get('close_requested') or
                (state.get('runtime_diagnostics') or {}).get('state', 'clear') != 'clear'):
            raise ServiceError('session_busy', 'Retirement requires a ready session without unknown or dialog state')
        if project_id in runtime.handles or record.get('tab_closed') is not True or record.get('saved') is not True:
            raise ServiceError('session_retirement_requires_closed', 'Close and save the process project before explicit retirement')
        for job_path in (folder / 'jobs').glob('*.json'):
            other = read(job_path)
            if other.get('job_id') != job['job_id'] and other.get('status') in ('queued', 'running', 'needs_reconcile'):
                raise ServiceError('session_busy', 'Other accepted or uncertain work prevents retirement')
        expected = params['expected_digest']
        if record.get('saved_digest') != expected:
            raise ServiceError('session_digest_mismatch', 'Retirement expected digest differs from registered save')
        already_retired = project_id in state.get('retired_projects', {})
        if not already_retired:
            # Other registrations must not share this file (including aliases).
            for state_path in folder.parent.glob('ses-*/session.json'):
                owner = read(state_path)
                for key in ('projects', 'retired_projects'):
                    for other_id, other in owner.get(key, {}).items():
                        if state_path.parent.resolve() == folder and other_id == project_id:
                            continue
                        if same_path(other['path'], path):
                            raise ServiceError('session_retirement_scope', 'Another project registration shares this file')
            mark_stage(runtime, 'project.retire_digest_check')
            if not path.is_file() or file_digest(path) != expected:
                raise ServiceError('session_digest_mismatch', 'Process file differs from the reviewed saved baseline')
            retired = dict(record, retirement_review={
                'expected_digest': expected, 'review_note': params['review_note'],
                'idle_asserted_by_caller': True, 'idle_verified': False,
                'closed_evidence': 'registered_tab_closed', 'job_id': job['job_id'],
                'retired_at': time.time(), 'files_deleted': False})
            state['projects'].pop(project_id)
            state.setdefault('retired_projects', {})[project_id] = retired
            mark_stage(runtime, 'project.persist_retirement')
            runtime.update(projects=state['projects'], retired_projects=state['retired_projects'])
        return dict(project_id=project_id, saved=True, saved_digest=expected, tab_closed=True,
                    already_closed=True, retired=True, already_retired=already_retired,
                    environment_closed=False, files_deleted=False,
                    idle_asserted_by_caller=True, idle_verified=False, backend=runtime.backend)
