import json
import subprocess
from types import SimpleNamespace

import pytest

from cst_solver import _dialog_uia as uia


def install_reader(monkeypatch, replies):
    calls = []
    def run(args, **kwargs):
        calls.append(kwargs)
        reply = replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return SimpleNamespace(returncode=0, stdout=json.dumps(reply), stderr='')
    monkeypatch.setattr(uia.subprocess, 'run', run)
    return calls


def content(body='', **extra):
    return dict(body=body, buttons=[{'text': 'Yes'}, {'text': 'No'}],
                truncated=False, has_progress=False, read_errors=[], **extra)


def test_empty_control_view_uses_raw_text_without_losing_attempt(monkeypatch):
    calls = install_reader(monkeypatch, [content(), content('Fixture question')])
    result = uia.read_content(100)
    assert result['body'] == 'Fixture question'
    assert [a['view'] for a in result['read_attempts']] == ['control', 'raw']
    assert result['read_attempts'][0]['body'] == ''
    assert [c['env']['CST_DIALOG_VIEW'] for c in calls] == ['control', 'raw']
    assert sum(c['timeout'] for c in calls) <= 4


def test_complete_control_view_does_not_repeat_read(monkeypatch):
    calls = install_reader(monkeypatch, [content('Question')])
    assert uia.read_content(100)['body'] == 'Question'
    assert len(calls) == 1


def test_raw_failure_keeps_buttons_and_reports_unknown(monkeypatch):
    install_reader(monkeypatch, [content(), subprocess.TimeoutExpired('uia', 2)])
    result = uia.read_content(100)
    assert result['body'] == ''
    assert [b['text'] for b in result['buttons']] == ['Yes', 'No']
    assert result['read_errors']
    assert result['read_attempts'][-1]['status'] == 'failed'


def test_truncated_raw_result_never_promoted_to_complete(monkeypatch):
    raw = content('Partial question')
    raw['truncated'] = True
    install_reader(monkeypatch, [content(), raw])
    assert uia.read_content(100)['truncated'] is True


def test_failed_control_preserves_raw_buttons_even_without_body(monkeypatch):
    raw = content(); raw['has_progress'] = True
    install_reader(monkeypatch, [subprocess.TimeoutExpired('uia', 2), raw])
    result = uia.read_content(100)
    assert result['buttons'] == [{'text': 'Yes'}, {'text': 'No'}]
    assert result['has_progress'] is True
    assert result['body'] == '' and result['read_errors']


@pytest.mark.parametrize('hwnd', [True, 0, -1, '100', None])
def test_invalid_window_never_launches_reader(monkeypatch, hwnd):
    calls = install_reader(monkeypatch, [])
    with pytest.raises(ValueError):
        uia.read_content(hwnd)
    assert not calls
