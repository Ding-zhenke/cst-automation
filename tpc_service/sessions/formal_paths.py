"""Request-scoped project paths; never a global external-directory allowlist."""
from pathlib import Path

from tpc_service.errors import ServiceError
from .project_lifecycle import path_key
from .store import contained, read

PROJECT_OPERATIONS = ('create_project', 'import_project', 'adopt_project')


def same_path(left, right):
    if path_key(left) == path_key(right):
        return True
    if Path(left).exists() and Path(right).exists():
        return Path(left).samefile(right)
    return False


def working_path(folder, params):
    if 'working_path' in params:
        value = params['working_path']
        if (not isinstance(value, str) or '\x00' in value or not Path(value).is_absolute()
                or Path(value).suffix.lower() != '.cst'):
            raise ServiceError('invalid_session_argument', 'Absolute .cst working_path required')
        if params.get('authorize_working_path') is not True:
            raise ServiceError('session_path_authorization_required', 'Explicit authorize_working_path=true required')
        try:
            return Path(value).resolve()
        except (OSError, ValueError) as exc:
            raise ServiceError('invalid_session_argument', 'Invalid absolute .cst working_path') from exc
    if 'authorize_working_path' in params:
        raise ServiceError('invalid_session_argument', 'Path authorization requires an exact working_path')
    return contained(folder, Path(folder) / 'projects' / params['project_id'] / 'model.cst')


def check_destination(folder, operation, params):
    path = working_path(folder, params)
    if operation == 'adopt_project':
        from .native import file_digest
        if not path.is_file() or file_digest(path) != params['expected_digest']:
            raise ServiceError('session_digest_mismatch', 'Adoption saved baseline digest does not match')
    elif path.exists() or path.with_suffix('').exists():
        raise ServiceError('project_exists', 'Destination file or paired results already exists; never overwrite')
    if operation == 'import_project':
        source = Path(params['source_path']).resolve()
        if path_key(source) == path_key(path):
            raise ServiceError('project_exists', 'Import cannot overwrite its source; use adopt_project')
        if source.with_suffix('') == path.parent or source.with_suffix('') in path.parents:
            raise ServiceError('workdir_escape', 'Import destination cannot be inside source results directory')
    return path


def assert_path_unclaimed(root, folder, operation, params):
    """Caller holds registry.lock, serializing queued claims across this root."""
    path = working_path(folder, params)
    for state_path in Path(root).glob('ses-*/session.json'):
        state = read(state_path)
        records = list(state.get('projects', {}).values())
        records += list(state.get('retired_projects', {}).values())
        for record in records:
            if same_path(record['path'], path):
                raise ServiceError('session_project_path_claimed', 'Project path already registered in a session')
        for job_path in (state_path.parent / 'jobs').glob('*.json'):
            job = read(job_path)
            # A failed native open can already own a tab even when it failed
            # before project registration. Only explicit reconciliation changes
            # that journal to resolved; a state-only transition cannot release it.
            if job['operation'] in PROJECT_OPERATIONS and job['status'] in ('queued', 'running', 'needs_reconcile', 'failed'):
                claimed = working_path(state_path.parent, job['params'])
                if same_path(claimed, path):
                    raise ServiceError('session_project_path_claimed', 'Project path already claimed by an accepted operation')
    return check_destination(folder, operation, params)
