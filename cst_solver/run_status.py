"""Joint read-only diagnostics on an already owned handle; never open or attach."""
import hashlib
import os
from pathlib import Path
import time

from .dialogs import list_dialogs
from .host import process_identity


def _path(value):
    return os.path.normcase(os.path.realpath(value))


def _observe(reader):
    started = time.time()
    try:
        value = reader()
        return dict(started_at=started, finished_at=time.time(), status='read', value=value)
    except Exception as exc:
        return dict(started_at=started, finished_at=time.time(), status='error',
                    value=None, error=f'{type(exc).__name__}: {exc}')


def _log_tail(project):
    path = Path(project).with_suffix('') / 'Result' / 'Model.log'
    before = path.stat()
    with path.open('rb') as stream:
        stream.seek(max(0, before.st_size - 65536))
        raw = stream.read(65536)
    after = path.stat()
    return dict(path=str(path), size=before.st_size, mtime_ns=before.st_mtime_ns,
                stable_during_read=(before.st_size, before.st_mtime_ns) ==
                                   (after.st_size, after.st_mtime_ns),
                complete_file=before.st_size <= 65536,
                tail_sha256=hashlib.sha256(raw).hexdigest(),
                text=raw.decode('utf-8', errors='replace'),
                source_job_binding='not_verified', qualification_evidence=False)


def inspect_owned_run(app, *, job_reader, expected_pid, expected_creation_time, expected_project):
    """No screenshots, SDK writes, attach, launch, stop, or session-state mutation.

    The caller supplies the original session-owned handle on its legal SDK thread
    and a fresh original-job reader. This helper does not bypass thread ownership.
    Log text and running=True never certify computational progress or convergence.
    """
    if (type(expected_pid) is not int or expected_pid <= 0 or
            not isinstance(expected_creation_time, str) or not expected_creation_time.isdecimal() or
            int(expected_creation_time) <= 0 or not callable(job_reader) or
            not isinstance(expected_project, (str, Path)) or not Path(expected_project).is_absolute()):
        raise ValueError('Explicit process identity, absolute project and original-job reader required')

    def identity():
        found = process_identity(expected_pid)
        if (found.get('status') != 'known' or found.get('creation_time') != expected_creation_time or
                app.project.pid != expected_pid):
            raise ValueError('Owned process identity changed or unknown')
        if _path(app.cst_file.filename()) != _path(expected_project):
            raise ValueError('Owned project identity changed')
        return dict(pid=expected_pid, creation_time=expected_creation_time, project=_path(expected_project))

    before = identity()
    job_before = _observe(job_reader)
    native = _observe(lambda: app.cst_file.model3d.is_solver_running(timeout=5))
    if native['status'] == 'read' and type(native['value']) is not bool:
        native.update(status='error', error='Native getter did not return a boolean', value=None)
    dialogs = _observe(lambda: list_dialogs(pid=expected_pid))
    log = _observe(lambda: _log_tail(expected_project))
    job_after = _observe(job_reader)
    after = _observe(identity)
    original = job_before.get('value') or {}
    latest = job_after.get('value') or {}
    consistent = (after['status'] == 'read' and after['value'] == before and
                  bool(original.get('job_id')) and original.get('job_id') == latest.get('job_id'))
    waiting = (any(d.get('blocking', True) for d in dialogs['value'])
               if dialogs['status'] == 'read' else 'unknown')
    # A terminal journal alone does not prove a blocked native SDK call returned.
    completion = latest.get('completion_evidence') or {}
    returned = True if consistent and completion.get('known_saved_solve') is True else 'unknown'
    return dict(read_only=True, observed_at=time.time(), identity_before=before,
                identity_after=after, identity_consistent=consistent,
                job_before=job_before, job_after=job_after, native_3d=native,
                dialogs=dialogs, log=log, waiting_for_prompt=waiting,
                original_call_returned=returned, whole_sequence_idle='unknown',
                computational_progress='unknown', resource_samples='not_collected',
                solver_verified=False, stop_requested='not_assessed')
