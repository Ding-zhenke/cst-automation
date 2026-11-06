"""Compact queue metadata. Full journals remain authoritative for execution.

Callers hold the session state lock. Publish a journal before indexing it;
filename enumeration repairs that gap without decoding existing history.
"""

from json import JSONDecodeError
from pathlib import Path

from tpc_service.errors import ServiceError
from .store import read, write


_ACTIVE = frozenset(('queued', 'running', 'needs_reconcile'))


class JobIndex:
    def __init__(self, folder, entries, active):
        self.folder = Path(folder)
        self.path = self.folder / 'job-index.json'
        self.entries = entries
        self.active = set(active)

    @classmethod
    def load(cls, folder, *, rebuild=False):
        folder = Path(folder)
        try:
            data = read(folder / 'job-index.json')
        except (JSONDecodeError, UnicodeDecodeError):
            data = None
        if not cls._valid(data):
            data = {'entries': {}, 'active': []}
        index = cls(folder, data['entries'], data['active'])
        names = {path.stem for path in (folder / 'jobs').glob('*.json')}
        missing = index.entries.keys() - names
        if missing:
            raise ServiceError('session_job_journal_missing', 'An indexed job journal is missing', job_ids=sorted(missing))
        if rebuild:
            index = cls(folder, {}, [])
        unindexed = names - index.entries.keys()
        for job_id in sorted(unindexed):
            index.add(index.journal(job_id))
        if unindexed or rebuild:
            index.save()
        return index

    @staticmethod
    def _valid(data):
        if not isinstance(data, dict) or data.get('version') != 1:
            return False
        entries, active = data.get('entries'), data.get('active')
        return (isinstance(entries, dict) and isinstance(active, list)
                and all(isinstance(job_id, str) and job_id in entries for job_id in active)
                and all(isinstance(row, list) and len(row) == 3 and type(row[0]) is int
                        and isinstance(row[1], str) and isinstance(row[2], str) for row in entries.values()))

    def add(self, job):
        self.entries[job['job_id']] = [job['sequence'], job['request_id'], job['operation_id']]
        if job['status'] in _ACTIVE:
            self.active.add(job['job_id'])

    def save(self):
        write(self.path, {'version': 1, 'entries': self.entries, 'active': sorted(self.active)})

    def journal(self, job_id):
        job = read(self.folder / 'jobs' / (job_id + '.json'))
        if job is None or job.get('job_id') != job_id:
            raise ServiceError('session_job_journal_missing', 'Job journal unavailable or mismatched', job_id=job_id)
        return job

    @property
    def maximum_sequence(self):
        return max((row[0] for row in self.entries.values()), default=0)

    def match(self, request_id=None, operation_id=None):
        candidates = [job_id for job_id, (_, request, operation) in self.entries.items()
                      if request == request_id or operation == operation_id]
        if len(candidates) > 1:
            raise ServiceError('request_id_conflict', 'Request and operation IDs refer to different journals')
        return self.journal(candidates[0]) if candidates else None

    def _active_journals(self):
        for job_id in sorted(self.active, key=lambda jid: (self.entries[jid][0], jid)):
            job = self.journal(job_id)
            if job['status'] in _ACTIVE:
                yield job
            else:
                # The receipt may have reached disk before an old worker exited
                # or before the compact index could be updated.
                self.active.remove(job_id)

    def active_jobs(self):
        size = len(self.active)
        jobs = list(self._active_journals())
        if len(self.active) != size:
            self.save()
        return jobs

    def next_queued(self):
        size = len(self.active)
        job = next((job for job in self._active_journals() if job['status'] == 'queued'), None)
        if len(self.active) != size:
            self.save()
        return job
