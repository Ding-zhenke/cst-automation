"""The queue may index history but execution evidence stays in the journals."""

import pytest

from tpc_service.errors import ServiceError
from tpc_service.sessions import SessionManager, job_index, store


@pytest.fixture
def session(tmp_path):
    manager = SessionManager(str(tmp_path), backend='fake')
    ref = manager.ensure('queue', 'ensure')
    manager._launch = lambda *_: None
    return manager, ref, tmp_path / ref['session_id']


def submit(session, request, operation_id=None):
    manager, ref, _ = session
    return manager.submit(ref['session_id'], ref['credential'], request, 'inspect',
                          {'project_id': 'model'}, operation_id=operation_id)


def write_job(folder, job):
    store.write(folder / 'jobs' / (job['job_id'] + '.json'), job)


def test_warm_submit_and_worker_selection_do_not_decode_history(session, monkeypatch):
    _, ref, folder = session
    for i in range(1, 81):
        write_job(folder, dict(job_id=f'job-old-{i}', session_id=ref['session_id'],
            sequence=i, request_id=f'request-{i}', operation_id=f'operation-{i}',
            status='succeeded', fingerprint='old', operation='inspect', result={'data': 'x' * 4096}))
    job_index.JobIndex.load(folder)  # migrate the pre-existing journals
    original_read = store.read

    def guarded_read(path, *args, **kwargs):
        assert not path.name.startswith('job-old-'), 'historical receipt was decoded again'
        return original_read(path, *args, **kwargs)

    monkeypatch.setattr(job_index, 'read', guarded_read)
    first = submit(session, 'new-request', 'new-stage')
    second = submit(session, 'another-request')
    assert (first['sequence'], second['sequence']) == (81, 82)
    assert submit(session, 'alias-request', 'new-stage')['job_id'] == first['job_id']
    assert job_index.JobIndex.load(folder).next_queued() == first
    write_job(folder, dict(first, status='succeeded'))  # index still lists it as active
    assert job_index.JobIndex.load(folder).next_queued() == second


def test_journal_published_before_index_is_recovered_without_duplicate(session, monkeypatch):
    _, _, folder = session
    submit(session, 'first')
    save = job_index.JobIndex.save

    def interrupted(_):
        raise OSError('lost index write after queued journal')

    monkeypatch.setattr(job_index.JobIndex, 'save', interrupted)
    with pytest.raises(OSError):
        submit(session, 'original', 'second-stage')
    monkeypatch.setattr(job_index.JobIndex, 'save', save)
    recovered = submit(session, 'retry-via-stage', 'second-stage')
    assert recovered['request_id'] == 'original' and recovered['sequence'] == 2
    assert submit(session, 'third')['sequence'] == 3
    assert len(list((folder / 'jobs').glob('*.json'))) == 3


def test_corrupt_index_rebuilds_but_missing_indexed_receipt_blocks_submission(session):
    _, _, folder = session
    first = submit(session, 'first')
    index = job_index.JobIndex.load(folder)
    index.path.write_text('{broken', encoding='utf-8')
    assert job_index.JobIndex.load(folder).next_queued() == first
    (folder / 'jobs' / (first['job_id'] + '.json')).unlink()
    with pytest.raises(ServiceError) as exc:
        submit(session, 'new')
    assert exc.value.code == 'session_job_journal_missing'


def test_unfinished_and_uncertain_receipts_survive_index_rebuild(session):
    _, _, folder = session
    first = submit(session, 'one')
    second = submit(session, 'two')
    write_job(folder, dict(first, status='running'))
    write_job(folder, dict(second, status='needs_reconcile'))
    index = job_index.JobIndex.load(folder)
    assert [job['status'] for job in index.active_jobs()] == ['running', 'needs_reconcile']
    assert index.next_queued() is None
    index.path.unlink()
    assert [job['status'] for job in job_index.JobIndex.load(folder).active_jobs()] == ['running', 'needs_reconcile']
