"""Message evidence must be observed, not inferred from an empty container."""
import json
from unittest.mock import Mock

import pytest

from cst_solver.run_contract import JsonlSink, RunContract
from cst_solver.tests.test_run_contract import _Host, _Sink


def contract(sink=None):
    values = iter([{'items': [['Result/x', 1, 1]]}, {'items': [['Result/x', 2, 2]]}])
    return RunContract('offline.cst', probe=lambda path: next(values), sink=sink or _Sink())


def test_not_read_is_unknown_even_when_results_changed():
    result = contract().run_and_record(lambda: None)
    assert result['status'] == 'unverified'
    assert result['messages_state'] == 'not_read'
    assert result['messages_read_attempted'] is False and result['messages_read'] is False
    assert result['messages_clean'] is None and result['messages'] == []
    assert 'messages_not_read' in [e['code'] for e in result['errors']]
    assert result['warnings_scope'] == 'audit'
    assert result['native_warnings_state'] == 'unknown' and result['native_warnings'] is None
    assert result['native_solver_status'] == result['mesh_convergence'] == 'unknown'
    assert result['validation_passed'] is False
    assert result['warnings']


@pytest.mark.parametrize('messages,clean,status', [([], True, 'succeeded'),
                                                  (['Warning: quality'], False, 'failed')])
def test_completed_reader_sets_explicit_observation(messages, clean, status):
    reader = Mock(return_value=messages)
    result = contract().run_and_record(lambda: None, read_messages=reader)
    assert result['messages_state'] == 'read' and result['messages_read'] is True
    assert result['messages_read_attempted'] is True and result['messages_clean'] is clean
    assert result['message_source'] == 'callback' and result['status'] == status
    assert result['native_warnings'] is None  # a queue is not the native log
    reader.assert_called_once_with()


@pytest.mark.parametrize('partial', [False, True])
def test_reader_failure_is_unknown_and_keeps_partial_messages(partial):
    def reader():
        if partial:
            yield 'Warning: maximum passes reached'
        raise OSError('queue disconnected')
    result = contract().run_and_record(lambda: None, read_messages=reader)
    assert result['messages_state'] == 'read_failed' and result['messages_read'] is False
    assert result['messages_read_attempted'] is True and result['messages_clean'] is None
    assert 'queue disconnected' in result['messages_read_error']
    assert result['messages'] == (['Warning: maximum passes reached'] if partial else [])
    assert result['status'] == ('failed' if partial else 'unverified')


def test_call_failure_is_reported_without_claiming_clean_messages():
    result = contract().run_and_record(lambda: None, read_messages=Mock(side_effect=RuntimeError('read failed')))
    assert result['messages_clean'] is None and result['messages_state'] == 'read_failed'


def test_none_reader_result_is_not_an_empty_success():
    result = contract().run_and_record(lambda: None, read_messages=lambda: None)
    assert result['messages_state'] == 'read_failed' and result['status'] == 'unverified'


@pytest.mark.parametrize('messages', [None, []])
def test_direct_after_submit_defaults_to_not_read(messages):
    c = contract()
    result = c.after_submit(c.before_submit(), messages=messages)
    assert result['messages_clean'] is None and result['status'] == 'unverified'
    assert result['message_source'] == 'caller'


def test_direct_caller_must_explicitly_declare_read_evidence():
    c = contract()
    result = c.after_submit(c.before_submit(), messages=[], messages_state='read')
    assert result['messages_clean'] is True and result['status'] == 'succeeded'
    assert result['message_source'] == 'caller'


def test_read_state_requires_data_and_valid_state():
    for state, messages in [('read', None), ('clean', [])]:
        c = contract()
        with pytest.raises(ValueError):
            c.after_submit(c.before_submit(), messages=messages, messages_state=state)


def test_solver_failure_is_not_downgraded_by_missing_messages():
    def fail():
        raise RuntimeError('native failure')
    result = contract().run_and_record(fail)
    assert result['status'] == 'failed' and result['messages_clean'] is None
    assert {'run_exception', 'messages_not_read'} <= {e['code'] for e in result['errors']}


def test_jsonl_preserves_unknown_instead_of_serializing_it_as_clean(tmp_path):
    path = tmp_path / 'observations.jsonl'
    result = contract(sink=JsonlSink(str(path))).run_and_record(lambda: None)
    persisted = json.loads(path.read_text(encoding='utf-8'))
    assert persisted['messages_clean'] is None
    assert persisted['messages_state'] == result['messages_state'] == 'not_read'
    assert persisted['message_source'] == result['message_source']


def test_run_checked_disabled_reader_is_never_called(tmp_path):
    host = _Host(str(tmp_path / 'fake.cst'))
    host.get_messages = Mock(side_effect=AssertionError('must not read'))
    fingerprints = iter([{'items': [['x', 1, 1]]}, {'items': [['x', 2, 2]]}])
    result = host.run_checked(read_messages=False, sink=_Sink(), probe=lambda path: next(fingerprints))
    assert result['messages_state'] == 'not_read' and result['messages_clean'] is None
    assert result['status'] == 'unverified' and result['message_source'] == 'sdk_pending_queue'
    host.get_messages.assert_not_called()


def test_run_checked_enabled_reader_records_queue_scope(tmp_path):
    host = _Host(str(tmp_path / 'fake.cst'))
    host.get_messages = Mock(return_value=[])
    fingerprints = iter([{'items': [['x', 1, 1]]}, {'items': [['x', 2, 2]]}])
    result = host.run_checked(sink=_Sink(), probe=lambda path: next(fingerprints))
    assert result['status'] == 'succeeded' and result['messages_clean'] is True
    assert result['message_source'] == 'sdk_pending_queue' and result['native_warnings'] is None


def test_observation_state_does_not_leak_between_runs():
    counter = iter(range(10))
    c = RunContract('offline.cst', probe=lambda path: {'items': [['x', next(counter), 1]]}, sink=_Sink())
    first = c.run_and_record(lambda: None, read_messages=lambda: [])
    second = c.run_and_record(lambda: None)
    third = c.run_and_record(lambda: None, read_messages=lambda: [])
    assert first['messages_clean'] is third['messages_clean'] is True
    assert second['messages_clean'] is None and second['messages_state'] == 'not_read'


def test_invalid_source_cannot_trigger_submission():
    submit = Mock()
    with pytest.raises(ValueError):
        contract().run_and_record(submit, message_source='')
    submit.assert_not_called()


def test_synthetic_native_warnings_are_not_claimed_absent(tmp_path):
    (tmp_path / 'Model.log').write_text(
        'Native solver SUCCESS\n*** Warning ***\n'
        'Mesh adaptation terminated because the maximum number of passes is reached\n'
        'Low quality tetrahedra\n', encoding='utf-8')
    c = contract()
    c.project_path = str(tmp_path / 'project.cst')
    result = c.run_and_record(lambda: None)
    assert result['native_warnings_state'] == 'unknown' and result['native_warnings'] is None
    assert result['native_solver_status'] == 'unknown'  # no log reader was requested
    assert result['mesh_convergence'] == 'unknown' and result['validation_passed'] is False


def test_legacy_read_error_overrides_explicit_clean_claim():
    c = contract()
    record = c.before_submit()
    record['messages_read_error'] = 'legacy reader failed'
    result = c.after_submit(record, messages=[], messages_state='read')
    assert result['messages_clean'] is None and result['messages_state'] == 'read_failed'
