"""Native-window fixtures only: no UIA, desktop enumeration or CST calls."""
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from cst_solver import dialogs


def glow(hwnd=9, **changes):
    window = dict(hwnd=hwnd, pid=70, process='cstd.exe', title='',
                  **{'class': 'QtitanTitleBarGlowWindow'}, visible=True,
                  owner=8, owner_pid=70, owner_class='Qt683QWindowIcon',
                  process_creation_time='100', owner_creation_time='100',
                  modal=True, is_dialog=True, responding=True)
    window.update(changes)
    return window


def snapshot(monkeypatch, windows, *, child=0):
    monkeypatch.setattr(dialogs, 'list_windows', lambda **kw: windows)
    monkeypatch.setattr(dialogs, '_user32', SimpleNamespace(
        IsWindowVisible=lambda hwnd: True, GetWindow=lambda hwnd, flag: child))
    content = Mock(return_value=dict(body='', text_readable=False, text_complete=False,
                                    read_errors=['UIA failed'], buttons=[], has_progress=False))
    monkeypatch.setattr(dialogs, '_dialog_content', content)
    monkeypatch.setattr(dialogs, '_child_buttons', lambda hwnd: [])
    ticks = iter([0., 10., 10., 10., 10., 10.])
    monkeypatch.setattr(dialogs.time, 'monotonic', lambda: next(ticks, 10.))
    return content


def test_verified_glows_do_not_consume_or_depend_on_uia_budget(monkeypatch):
    content = snapshot(monkeypatch, [glow(i) for i in (9, 10, 11)])
    result = dialogs.list_dialogs(pid=70)
    assert len(result) == 3
    assert all(row['classification'] == 'decoration' and not row['blocking'] for row in result)
    assert all(row['text_source'] == 'win32_glow_structure' for row in result)
    assert all(row['text_readable'] is False and row['text_complete'] is False for row in result)
    assert all(not row['needs_visual_inspection'] for row in result)
    assert dialogs._blocking(result, 70) == []
    content.assert_not_called()


@pytest.mark.parametrize('change', [
    {'title': 'Warning'}, {'owner': 0}, {'owner_pid': 71},
    {'owner_class': '#32770'}, {'process_creation_time': None},
    {'owner_creation_time': '200'}, {'responding': False},
    {'class': 'Qt683QWindowIcon'},
])
def test_incomplete_or_contradictory_structure_still_blocks(monkeypatch, change):
    snapshot(monkeypatch, [glow(**change)])
    result = dialogs.list_dialogs(pid=70)
    assert result[0]['blocking'] is True
    assert result[0]['classification'] != 'decoration'
    assert result[0]['read_errors']


def test_glow_with_native_child_is_not_suppressed_on_budget_failure(monkeypatch):
    snapshot(monkeypatch, [glow()], child=99)
    result = dialogs.list_dialogs(pid=70)
    assert result[0]['blocking'] is True
    assert result[0]['needs_visual_inspection'] is True


def test_actual_modal_after_glows_is_not_hidden(monkeypatch):
    snapshot(monkeypatch, [glow(), glow(10), glow(11, **{'class': '#32770', 'title': 'Connection Check'})])
    result = dialogs.list_dialogs(pid=70)
    blockers = dialogs._blocking(result, 70)
    assert len(blockers) == 1
    assert blockers[0]['title'] == 'Connection Check'
    assert blockers[0]['error_code'] == 'cst_dialog_unknown'
