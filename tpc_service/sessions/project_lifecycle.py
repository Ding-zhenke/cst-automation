"""Pure project-intent checks, performed before queue acceptance."""
import os
from pathlib import Path

from tpc_service.errors import ServiceError


def path_key(path):
    return os.path.normcase(str(Path(path).resolve()))


def check_project_intent(state, jobs, operation, params):
    if operation not in ('create_project', 'import_project', 'adopt_project'):
        return
    records = list(state['projects'].values())
    records.extend(j['params'] for j in jobs if j['operation'] in ('create_project', 'import_project', 'adopt_project')
                   and j['status'] in ('queued', 'running'))
    for record in records:
        if record['project_id'] == params['project_id']:
            raise ServiceError('project_exists', 'Project already registered or queued; reuse its original ID and receipt')
    if params['project_id'] in state.get('retired_projects', {}):
        raise ServiceError('project_exists', 'Temporary project ID is retired; use its original receipt')
    if operation == 'import_project' and not params.get('copy_reason'):
        source = path_key(params['source_path'])
        for record in records:
            if any(record.get(key) and path_key(record[key]) == source for key in ('path', 'source_path')):
                raise ServiceError('duplicate_project_source',
                                   'Reuse the registered project; an independent copy requires copy_reason',
                                   project_id=record['project_id'])
