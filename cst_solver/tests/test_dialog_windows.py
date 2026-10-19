# -*- coding: utf-8 -*-
"""真实 Win32 消息框验证；只创建并关闭本测试子进程，不启动 CST。"""
import os
import subprocess
import sys
import threading
import time

import pytest

from cst_solver import dialogs


@pytest.mark.skipif(os.name != 'nt', reason='需要 Windows 桌面')
@pytest.mark.gui
def test_native_body_is_reported_while_message_box_is_open(monkeypatch):
    child = subprocess.Popen([sys.executable, '-c',
        "import ctypes; ctypes.windll.user32.MessageBoxW(None, "
        "'Undefined variable: Ls', 'TPC guard native test', 0x10)"],
        creationflags=0x08000000)
    reported = threading.Event()
    snapshots = []
    reader = dialogs.list_dialogs
    monkeypatch.setattr(dialogs, 'list_dialogs',
                        lambda **kw: reader(only_cst=False, pid=child.pid))
    def on_event(event):
        if event['state'] == 'blocked_by_dialog':
            snapshots.append(event)
            reported.set()
    try:
        with dialogs.DialogMonitor('native-test', timeout=None, poll=0.02,
                                    pid=child.pid, on_event=on_event):
            assert reported.wait(5), 'native message box was not reported'
            assert child.poll() is None, 'the diagnostic must arrive before the call returns'
            dialog = snapshots[0]['dialogs'][0]
            assert dialog['title'] == 'TPC guard native test'
            assert dialog['body'] == 'Undefined variable: Ls'
            assert dialog['text_readable'] is True
            assert dialog['buttons']
            # 同时验证 Qt/自绘备用通道所用的真实 UIA 进程桥，不只替换返回值。
            from cst_solver._dialog_uia import read_content
            accessible = read_content(dialog['hwnd'])
            assert 'Undefined variable: Ls' in accessible['body']
            assert accessible['buttons'] and not accessible['truncated'], accessible
            # 发给本测试的真实 Button；验证有界发送后窗口确实关闭。
            assert dialogs._send_button(dialog, dialog['buttons'][0])
            assert child.wait(timeout=3) == 0
    finally:
        if child.poll() is None:
            child.terminate()
            child.wait(timeout=3)
