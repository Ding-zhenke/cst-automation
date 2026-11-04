"""Typed queue evidence and pre-submit boundaries, with synthetic messages only."""
from unittest.mock import Mock

import pytest

from cst_solver.run_contract import RunContract


class Sink:
    def __init__(self): self.records = []
    def write(self, record):
        self.records.append(dict(record))
        return 'offline.jsonl'


def contract(sink=None):
    values = iter([{'items': [['x', 1, 1]]}, {'items': [['x', 2, 2]]}])
    return RunContract('synthetic.cst', probe=lambda p: next(values), sink=sink or Sink())


def test_information_is_preserved_without_becoming_a_solver_error():
    messages = [{'type': 'INFO', 'text': 'Completed bookkeeping', 'native_id': 7}]
    result = contract().run_and_record(lambda: None, read_messages=lambda: messages)
    assert result['status'] == 'succeeded'
    assert result['messages'] == messages
    assert result['message_summary'] == {'info': 1, 'warning': 0, 'error': 0, 'unknown': 0}
    assert result['messages_clean'] is True and result['queue_empty'] is False
    assert result['native_solver_status'] == 'unknown'
    assert result['validation_passed'] is False


@pytest.mark.parametrize('message,status,key', [
    ({'type': 'WARNING', 'text': 'Needs review'}, 'unverified', 'warning'),
    ({'type': 'ERROR', 'text': 'Native error'}, 'failed', 'error'),
    ({'type': 'OTHER', 'text': 'Unknown'}, 'failed', 'unknown'),
    ("{'type': 'INFO', 'text': 'legacy repr'}", 'failed', 'unknown'),
])
def test_warning_error_and_unknown_are_not_silently_discarded(message, status, key):
    result = contract().run_and_record(lambda: None, read_messages=lambda: [message])
    assert result['status'] == status
    assert result['messages'] == [message]
    assert result['message_summary'][key] == 1
    assert result['messages_clean'] is False
    assert result['validation_passed'] is False


def test_prior_queue_is_persisted_before_submission_and_not_subtracted_by_text():
    sink = Sink(); c = contract(sink)
    warning = {'type': 'WARNING', 'text': 'Repeated native warning'}
    def submit():
        assert sink.records[-1]['phase'] == 'before_submit'
        assert sink.records[-1]['prior_messages'] == [warning]
    result = c.run_and_record(submit, read_prior_messages=lambda: [warning], read_messages=lambda: [warning])
    assert result['status'] == 'unverified'
    assert result['messages'] == result['prior_messages'] == [warning]
    assert result['message_scope'] == 'post_boundary_queue'
    assert result['prior_messages_review_required'] is True
    assert result['native_run_message_binding_verified'] is False


def test_prior_warning_remains_visible_when_current_queue_is_info_only():
    result = contract().run_and_record(lambda: None,
        read_prior_messages=lambda: [{'type': 'WARNING', 'text': 'Earlier operation'}],
        read_messages=lambda: [{'type': 'INFO', 'text': 'This call returned'}])
    assert result['status'] == 'succeeded'
    assert result['prior_messages_review_required'] is True
    assert result['prior_message_summary']['warning'] == 1
    assert result['message_summary']['warning'] == 0


@pytest.mark.parametrize('failure', ['read', 'persist'])
def test_boundary_failure_prevents_submission(failure):
    sink = Sink()
    if failure == 'persist': sink.write = Mock(side_effect=OSError('audit unavailable'))
    c = contract(sink); submit = Mock()
    def prior():
        if failure == 'read': raise OSError('queue unavailable')
        return [{'type': 'INFO', 'text': 'Preserve before solving'}]
    reader = Mock(side_effect=prior)
    result = c.run_and_record(submit, read_prior_messages=reader, read_messages=lambda: [])
    submit.assert_not_called()
    if failure == 'persist': reader.assert_not_called()
    assert result['execution_returned'] is False
    assert result['status'] != 'succeeded'


def test_without_prior_boundary_old_queue_origin_is_unknown():
    result = contract().run_and_record(lambda: None, read_messages=lambda: [])
    assert result['message_scope'] == 'pending_queue_unbounded'
    assert result['prior_messages_state'] == 'not_read'


def test_setup_run_checked_reads_prior_queue_and_post_queue_separately(tmp_path):
    from cst_solver.tests.test_run_contract import _Host
    host = _Host(str(tmp_path/'synthetic.cst'))
    host.get_messages = Mock(side_effect=[
        [{'type': 'WARNING', 'text': 'Previous operation'}],
        [{'type': 'INFO', 'text': 'This operation'}]])
    values = iter([{'items': [['x', 1, 1]]}, {'items': [['x', 2, 2]]}])
    outcome = host.run_checked(sink=Sink(), probe=lambda p: next(values))
    assert host.get_messages.call_count == 2
    assert outcome['prior_message_summary']['warning'] == 1
    assert outcome['message_summary']['info'] == 1
    assert outcome['status'] == 'succeeded'


def test_partial_info_reader_is_unverified_and_preserves_raw_messages():
    def reader():
        yield {'type': 'INFO', 'text': 'Partial'}
        raise OSError('queue disconnected')
    outcome = contract().run_and_record(lambda: None, read_messages=reader)
    assert outcome['messages'] == [{'type': 'INFO', 'text': 'Partial'}]
    assert outcome['status'] == 'unverified'
    assert outcome['messages_clean'] is None
