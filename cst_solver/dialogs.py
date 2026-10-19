# -*- coding: utf-8 -*-
"""CST 弹窗读取与独立监测；可离线导入，Windows 下读取正文与按钮。

监测不调用 CST SDK；调用仍阻塞时就输出诊断，不能强制取消执行线程。
旧 scripts/cst_dialog_guard.py 仅作为兼容入口。
"""
import ctypes
import ctypes.wintypes as wintypes
import threading
import copy
import json
import logging
import os
import sys
import time
from contextlib import contextmanager
from cst_solver.failures import structured_error

__all__ = ['list_windows', 'describe_windows', 'list_dialogs', 'describe_dialogs',
           'save_prompts', 'dismiss_dialogs', 'check_dialogs', 'guard',
           'CstDialogTimeout', 'DialogMonitor', 'DIALOG_ERROR_CODES']

DIALOG_ERROR_CODES = ('cst_dialog_monitor_failed',)

_user32 = ctypes.WinDLL('user32', use_last_error=True) if os.name == 'nt' else None
_kernel32 = ctypes.WinDLL('kernel32', use_last_error=True) if os.name == 'nt' else None
_logger = logging.getLogger(__name__)

_PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
_DIALOG_CLASS = '#32770'                  # 标准 Win32 对话框 / 消息框类名
# Qt 原生对话框类名（2026 版 CST 的 Save As / Open / 另存为 是 Qt 自己的窗口，
# 不是 #32770；只认 #32770 的巡检必然漏，2026-09-23 用户实测挂死 600s）
_QT_DIALOG_CLASS_PREFIX = 'Qt'
# 已知标题可识别无 owner 的 Qt 弹窗；未知标题由 owner 被禁用的模态关系识别。
# 普通 Qt 主窗口/无标题工具窗不能仅凭类名判为对话框。
_QT_DIALOG_TITLE_KEYWORDS = ('save as', 'open', '另存为', '保存为', '打开',
                             'warning', 'error', 'information', '警告', '错误', '提示')

# Win32 常量
_GW_OWNER = 4
_WM_COMMAND = 0x0111
_BM_CLICK = 0x00F5
_IDOK, _IDCANCEL, _IDABORT, _IDRETRY, _IDIGNORE, _IDYES, _IDNO = 1, 2, 3, 4, 5, 6, 7

# 英文按钮 → 对话框控件 ID（中文 CST 用的是同一个 ID，只是文字本地化了）
_BUTTON_LABEL_IDS = {
    'ok': _IDOK, '确定': _IDOK, '是': _IDYES, 'yes': _IDYES,
    '否': _IDNO, 'no': _IDNO, '取消': _IDCANCEL, 'cancel': _IDCANCEL,
    '中止': _IDABORT, 'abort': _IDABORT, '重试': _IDRETRY, 'retry': _IDRETRY,
    '忽略': _IDIGNORE, 'ignore': _IDIGNORE,
}

_pid_name_cache = {}

# 显式声明指针宽度，避免 64 位 HWND/HANDLE 被截断。离线导入不要求 Windows。
if _user32 is not None:
    _enum_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    _user32.EnumWindows.argtypes = [_enum_type, wintypes.LPARAM]
    _user32.EnumWindows.restype = wintypes.BOOL
    _user32.EnumChildWindows.argtypes = [wintypes.HWND, _enum_type, wintypes.LPARAM]
    _user32.EnumChildWindows.restype = wintypes.BOOL
    _kernel32.OpenProcess.restype = wintypes.HANDLE
    _kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    _kernel32.QueryFullProcessImageNameW.restype = wintypes.BOOL
    _kernel32.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, wintypes.DWORD,
        wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]
    _kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    for _name, _restype, _args in [
        ('GetWindow', wintypes.HWND, [wintypes.HWND, wintypes.UINT]),
        ('GetWindowTextLengthW', ctypes.c_int, [wintypes.HWND]),
        ('GetWindowTextW', ctypes.c_int, [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]),
        ('GetClassNameW', ctypes.c_int, [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]),
        ('GetWindowThreadProcessId', wintypes.DWORD,
         [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]),
        ('GetDlgCtrlID', ctypes.c_int, [wintypes.HWND]),
        ('IsWindowVisible', wintypes.BOOL, [wintypes.HWND]),
        ('IsWindowEnabled', wintypes.BOOL, [wintypes.HWND]),
        ('IsHungAppWindow', wintypes.BOOL, [wintypes.HWND]),
        ('SendMessageTimeoutW', ctypes.c_ssize_t,
         [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM,
          wintypes.UINT, wintypes.UINT, ctypes.POINTER(ctypes.c_size_t)]),
    ]:
        getattr(_user32, _name).restype = _restype
        getattr(_user32, _name).argtypes = _args


def _query_image_name(pid):
    """
    用 ``QueryFullProcessImageNameW`` 取进程名（快）。

    ⚠️ 对**高完整性级别**进程（实测 CST 的 ``cstd.exe``）OpenProcess 会被拒，
    此时返回 ``None``，由 :func:`_refresh_pid_names` 用 ``tasklist`` 兜底。

    :param pid: int
    :return: str|None
    """
    handle = _kernel32.OpenProcess(_PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not handle:
        return None
    try:
        size = wintypes.DWORD(260)
        buffer = ctypes.create_unicode_buffer(size.value)
        if _kernel32.QueryFullProcessImageNameW(handle, 0, buffer,
                                                ctypes.byref(size)):
            return buffer.value.rsplit('\\', 1)[-1]
    finally:
        _kernel32.CloseHandle(handle)
    return None


_pid_cache_time = 0.0
_pid_fallback_time = 0.0


def _refresh_pid_names():
    """一次 tasklist 兜底；失败向上游报告，不能把权限失败当成没有弹窗。"""
    import csv
    import subprocess
    global _pid_fallback_time
    _pid_fallback_time = time.monotonic()
    out = subprocess.run(['tasklist', '/FO', 'CSV', '/NH'], capture_output=True,
                         text=True, timeout=2, creationflags=0x08000000)
    if out.returncode:
        raise OSError(out.stderr.strip() or 'tasklist 查询失败')
    for row in csv.reader(out.stdout.splitlines()):
        if len(row) >= 2 and row[1].isdigit():
            _pid_name_cache[int(row[1])] = row[0]


def _pid_name(pid):
    """进程名缓存仅保留 3s；避免 PID 复用后操作过期会话。"""
    global _pid_cache_time
    now = time.monotonic()
    if now - _pid_cache_time > 3:
        _pid_name_cache.clear()
        _pid_cache_time = now
    if pid in _pid_name_cache:
        return _pid_name_cache[pid]
    name = _query_image_name(pid)
    if name is None and now - _pid_fallback_time > 2:
        _refresh_pid_names()
    name = name or _pid_name_cache.get(pid, f'pid{pid}')
    _pid_name_cache[pid] = name
    return name


def _window_text(hwnd):
    """窗口标题。"""
    length = _user32.GetWindowTextLengthW(hwnd)
    buffer = ctypes.create_unicode_buffer(length + 1)
    _user32.GetWindowTextW(hwnd, buffer, length + 1)
    return buffer.value


def _class_name(hwnd):
    """窗口类名（对话框为 ``#32770``）。"""
    buffer = ctypes.create_unicode_buffer(256)
    _user32.GetClassNameW(hwnd, buffer, 256)
    return buffer.value


def _pid_of(hwnd):
    """窗口所属进程 pid。"""
    pid = wintypes.DWORD()
    _user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return pid.value


def _is_cst_process(name):
    """进程名是否是 CST 系（cstd.exe / CSTDCMainController...）。"""
    return os.path.basename(name).lower().startswith('cst')


def _is_qt_dialog(klass, title, visible):
    """参数：类名/标题/可见性。返回值：已知 Qt 弹窗标题判据。

    说明：标题只作补充识别；list_windows 另查禁用 owner 的模态关系，正文通过 UIA 读取。
    """
    if not visible or not klass.startswith(_QT_DIALOG_CLASS_PREFIX):
        return False
    low = (title or '').strip().lower()
    return low in _QT_DIALOG_TITLE_KEYWORDS or low.startswith(('请输入', 'cst warning', 'cst error'))


def _child_buttons(hwnd):
    """
    枚举对话框上的按钮（类名 ``Button``）。

    :return: list[dict], ``{'text', 'ctrl_id'}``
    """
    buttons = []
    children = []
    EnumChildProc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    def _callback(child, _lparam):
        children.append(child)
        return True

    _user32.EnumChildWindows(hwnd, EnumChildProc(_callback), 0)
    if len(children) > 128:
        raise OSError('控件树超过 128 个，按钮读取不完整')
    deadline = time.monotonic() + 1
    for child in children[:128]:
        if time.monotonic() > deadline:
            raise OSError('按钮读取达到 1s 上限')
        if _class_name(child) == 'Button':
            buttons.append({
                'text': _control_text(child),
                'ctrl_id': _user32.GetDlgCtrlID(child),
                'hwnd': child,
                'enabled': bool(_user32.IsWindowEnabled(child)),
                'visible': bool(_user32.IsWindowVisible(child)),
            })
    return buttons


def _control_text(hwnd):
    """读取跨进程控件正文；WM_GETTEXT 本身最多等待 100ms。"""
    buffer = ctypes.create_unicode_buffer(8192)
    result = ctypes.c_size_t()
    if not _user32.SendMessageTimeoutW(hwnd, 0x000D, len(buffer), ctypes.addressof(buffer),
                                      0x2 | 0x20, 100, ctypes.byref(result)):
        raise OSError(f'控件文本读取超时/失败 hwnd={hwnd}')
    if result.value >= len(buffer) - 1:
        raise OSError(f'控件文本达到缓冲区上限，正文可能截断 hwnd={hwnd}')
    return buffer.value


def _dialog_content(hwnd, klass):
    import subprocess
    from cst_solver._dialog_uia import read_content
    texts, errors, children = [], [], []
    has_progress = False
    callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    callback = callback_type(lambda child, data: children.append(child) or True)
    _user32.EnumChildWindows(hwnd, callback, 0)
    if len(children) > 128:
        errors.append('控件树超过 128 个，正文读取不完整')
    deadline = time.monotonic() + 1
    for child in children[:128]:
        if time.monotonic() > deadline:
            errors.append('控件正文读取达到 1s 上限')
            break
        kind = _class_name(child)
        if not _user32.IsWindowVisible(child):
            continue
        has_progress |= kind.lower() == 'msctls_progress32'
        if kind in ('Static', 'Edit') or kind.startswith(('RichEdit', 'RICHEDIT')):
            try:
                text = _control_text(child)
                if text.strip():
                    texts.append(text)
            except OSError as exc:
                errors.append(str(exc))
    result = dict(body='\n'.join(dict.fromkeys(texts)), text_source='win32',
                  text_readable=bool(texts), read_errors=errors, has_progress=has_progress)
    if not texts:
        try:
            accessible = read_content(hwnd)
            result.update(accessible, text_source='uia',
                          text_readable=bool(accessible.get('body')))
            if accessible.get('truncated'):
                result['read_errors'].append('UIA 控件树超过上限，正文/按钮读取不完整')
        except (OSError, ValueError, subprocess.SubprocessError) as exc:
            result['read_errors'].append(f'UIA: {exc}')
    result['text_complete'] = bool(result['text_readable'] and not result['read_errors'])
    return result


def list_windows(only_cst=True, *, pid=None):
    """参数：only_cst 限定进程名，pid 限定会话。返回值：窗口与 owner/modal 信息。"""
    if _user32 is None:
        raise OSError('CST 弹窗读取需要 Windows 交互桌面')
    handles, windows = [], []
    callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    callback = callback_type(lambda hwnd, data: handles.append(hwnd) or True)
    if not _user32.EnumWindows(callback, 0):
        raise ctypes.WinError(ctypes.get_last_error())
    # 在 ctypes 回调外读取，确保异常不会被 ctypes 吞掉后误报“没有弹窗”。
    for hwnd in handles:
        window_pid = _pid_of(hwnd)
        if pid is not None and window_pid != pid:
            continue
        name = _pid_name(window_pid)
        if only_cst and not _is_cst_process(name):
            continue
        klass, title = _class_name(hwnd), _window_text(hwnd)
        visible = bool(_user32.IsWindowVisible(hwnd))
        owner = _user32.GetWindow(hwnd, _GW_OWNER) or 0
        modal = bool(owner and not _user32.IsWindowEnabled(owner))
        windows.append(dict(hwnd=hwnd, pid=window_pid, process=name, title=title,
                            **{'class': klass}, visible=visible, owner=owner,
                            responding=not bool(_user32.IsHungAppWindow(hwnd)), modal=modal,
                            is_dialog=klass == _DIALOG_CLASS or
                            _is_qt_dialog(klass, title, visible) or (visible and modal)))
    return windows


def describe_windows(only_cst=True):
    """
    人类可读的窗口快照（给日志/证据用）。

    :param only_cst: bool, 只看 CST 相关窗口
    :return: str
    """
    windows = list_windows(only_cst=only_cst)
    if not windows:
        return '（没有 CST 顶层窗口）'
    lines = []
    for window in windows:
        flag = '可见' if window['visible'] else '隐藏'
        state = '响应中' if window['responding'] else '无响应（需检查窗口与进度）'
        kind = ' 对话框' if window['is_dialog'] else ''
        title = window['title'] or '（无标题）'
        lines.append(f"  pid={window['pid']} {window['process']}{kind} "
                     f"[{flag}/{state}] {title!r}")
    return '\n'.join(lines)


def list_dialogs(only_cst=True, *, pid=None):
    """
    列出可见 Win32/Qt/有模态 owner 的窗口，附正文、按钮及读取完整性。

    :param only_cst: bool, 只看 CST 进程的对话框
    :return: list[dict], 新增 body/buttons/text_readable/text_complete/read_errors 等字段
    """
    dialogs = []
    deadline = time.monotonic() + 3
    for window in list_windows(only_cst=only_cst, **({'pid': pid} if pid is not None else {})):
        if not window['is_dialog'] or not window['visible']:
            continue
        dialog = dict(window)
        if time.monotonic() < deadline:
            content = _dialog_content(dialog['hwnd'], dialog['class'])
        else:
            content = dict(body='', text_source='unreadable', text_readable=False,
                           text_complete=False,
                           read_errors=['快照读取达到时限，请用 --pid 指定目标会话重读'],
                           has_progress=False)
        dialog.update(content)
        try:
            buttons = _child_buttons(dialog['hwnd'])
        except OSError as exc:
            buttons = []
            dialog['read_errors'].append(str(exc))
        dialog['buttons'] = buttons or content.get('buttons', [])
        dialog['text_complete'] = bool(dialog.get('text_complete', dialog['text_readable']) and
                                       not dialog['read_errors'])
        progress = (content.get('has_progress', False) and not dialog['read_errors'] and
                    all(_normalize_button(b['text']) in ('cancel', '取消', 'stop', '停止')
                        for b in dialog['buttons']))
        dialog['blocking'] = not progress and (
            dialog.get('modal', True) or not dialog.get('owner'))
        dialog['needs_visual_inspection'] = not dialog['text_complete']
        dialogs.append(dialog)
    return dialogs


_SAVE_KEYWORDS = ('保存', 'save', '另存', '未保存', 'unsaved', '更改', 'changes', 'overwrite', '覆盖')


def save_prompts(only_cst=True):
    """
    找出「是否保存更改 / 退出前保存」类弹窗（2026-09-17 实测出现过）。

    判定：对话框标题或按钮文字里出现 保存/save/更改/changes 等关键词。
    这类弹窗是**关闭项目或退出 CST 时**出现的，不点就会一直挂着。

    :param only_cst: bool, 只看 CST 进程
    :return: list[dict], 同 :func:`list_dialogs`
    """
    found = []
    for dialog in list_dialogs(only_cst=only_cst):
        haystack = dialog['title'].lower() + ' ' + dialog.get('body', '').lower() + ' ' + ' '.join(
            (b['text'] or '').lower() for b in dialog['buttons'])
        if any(word in haystack for word in _SAVE_KEYWORDS):
            found.append(dialog)
    return found


def describe_dialogs(only_cst=True):
    """
    对话框快照（含按钮文字），没有则返回「没有」。

    :param only_cst: bool, 只看 CST 进程
    :return: str
    """
    dialogs = list_dialogs(only_cst=only_cst)
    return _format_dialogs(dialogs)


def _format_dialogs(dialogs):
    if not dialogs:
        return '（没有可见的 CST 对话框）'
    lines = []
    for dialog in dialogs:
        state = '响应中' if dialog['responding'] else '无响应'
        lines.append(f"  pid={dialog['pid']} {dialog['process']} [{state}] "
                     f"标题={dialog['title']!r}")
        lines.append(f"      正文：{dialog.get('body') or '（正文不可读，需检查窗口）'}")
        if dialog.get('read_errors'):
            lines.append(f"      读取诊断：{dialog['read_errors']}")
        for button in dialog['buttons']:
            lines.append(f"      按钮: {button['text']!r} (id={button['ctrl_id']})")
        if not dialog['buttons']:
            if dialog['class'].startswith(_QT_DIALOG_CLASS_PREFIX):
                # Qt 原生对话框：能识别、但无法用白名单点按钮关闭
                lines.append('      （Qt 原生对话框：按钮不是标准 Button 控件，'
                             'dismiss_dialogs 对它无效，需人工或键盘处理）')
            else:
                lines.append('      （没有枚举到按钮 —— 可能是自绘/CST 私有对话框）')
    return '\n'.join(lines)


def _normalize_button(text):
    return (text or '').replace('&', '').strip().lower()


def _send_button(dialog, button):
    result = ctypes.c_size_t()
    return bool(_user32.SendMessageTimeoutW(button['hwnd'], _BM_CLICK, 0, 0,
                                            0x2 | 0x20, 500, ctypes.byref(result)))


def dismiss_dialogs(prefer=(), only_cst=True, require_title=None, *, pid=None, hwnd=None,
                    expected_message=None):
    """显式处理已读弹窗。参数必须包含 pid、hwnd、完整按钮文字；默认不点。

    返回值：action 为 clicked/no_match/scope_required/stale_or_foreign/send_failed。
    说明：不再默认选择“不保存”；不按按钮子串或坐标点击。
    """
    results = []
    for dialog in list_dialogs(only_cst=only_cst, **({'pid': pid} if pid is not None else {})):
        if require_title and require_title not in dialog['title']:
            continue
        if pid is not None and dialog['pid'] != pid:
            continue
        if hwnd is not None and dialog['hwnd'] != hwnd:
            continue
        entry = dict(title=dialog['title'], action='scope_required', button=None)
        if pid is None or hwnd is None:
            results.append(entry)
            continue
        if expected_message is not None and (
            (dialog['title'], dialog.get('body', '')) != tuple(expected_message) or
            not dialog.get('text_complete') or dialog.get('read_errors')):
            entry['action'] = 'message_changed'
            results.append(entry)
            continue
        choice = next((b for wanted in prefer for b in dialog['buttons']
                       if _normalize_button(wanted) == _normalize_button(b['text'])
                       and b.get('enabled', True) and b.get('visible', True)), None)
        if choice is None:
            entry.update(action='no_match', buttons=[b['text'] for b in dialog['buttons']])
        elif (not dialog['visible'] or dialog.get('class') != '#32770' or
              not _is_cst_process(dialog['process']) or _pid_of(hwnd) != pid or
              not _is_cst_process(_pid_name(pid)) or _pid_of(choice['hwnd']) != pid or
              _normalize_button(_control_text(choice['hwnd'])) != _normalize_button(choice['text'])):
            entry['action'] = 'stale_or_foreign'
        else:
            if expected_message is not None:
                current = _dialog_content(hwnd, dialog['class'])
                unchanged = (current.get('text_complete') and not current.get('read_errors') and
                             (_window_text(hwnd), current.get('body', '')) == tuple(expected_message))
            else:
                unchanged = True
            entry.update(action=('clicked' if _send_button(dialog, choice) else 'send_failed')
                         if unchanged else 'message_changed', button=choice['text'])
        results.append(entry)
    return results


class CstDialogTimeout(TimeoutError):
    """弹窗/步骤超时异常；details 保留阻塞期间读取的证据。"""
    def __init__(self, message, details=None):
        super().__init__(message)
        self.details = details or {}


def _blocking(dialogs, pid=None):
    return [d for d in dialogs if d.get('visible', True) and d.get('blocking', True)
            and (pid is None or d['pid'] == pid)]


def check_dialogs(label='', only_cst=True, *, pid=None):
    """前/后置检查。返回空列表；可见阻塞窗口抛异常，隐藏窗口/进度条不阻塞。"""
    dialogs = _blocking(list_dialogs(only_cst=only_cst, **({'pid': pid} if pid is not None else {})), pid)
    if dialogs:
        raise CstDialogTimeout(f'步骤「{label}」发现 CST 弹窗：\n{_format_dialogs(dialogs)}',
                               {'dialogs': dialogs})
    return []


class DialogMonitor:
    """独立巡检线程。参数：步骤名、timeout、poll、pid（整数或返回整数的函数）。

    on_event 接收变化诊断，默认写 stderr 并 flush；timeout=None 不限制长求解。
    返回值：snapshot() 提供最新状态；failure 保留已确认阻塞/超时，避免假成功。
    说明：不调用 CST SDK，不取消阻塞线程；pid 未知只报告归属未确认的弹窗。
    """
    def __init__(self, label='', timeout=300.0, poll=1.0, *, pid=None,
                 on_event=None, auto_acknowledge=False, acknowledge_messages=()):
        if poll <= 0 or (timeout is not None and timeout <= 0):
            raise ValueError('poll/timeout 必须大于零（timeout 可为 None）')
        self.label, self.timeout, self.poll, self.pid = label, timeout, poll, pid
        self.on_event, self.auto_acknowledge = on_event, auto_acknowledge
        self.acknowledge_messages = frozenset(tuple(pair) for pair in acknowledge_messages)
        self._done, self._lock = threading.Event(), threading.RLock()
        self._thread = None
        self._state = dict(state='clear', attention_required=False, dialogs=[])
        self.failure = None
        self._finished = None

    def snapshot(self):
        """返回独立的 JSON 友好诊断副本。"""
        with self._lock:
            return copy.deepcopy(self._state)

    def _publish(self, state):
        with self._lock:
            if state['state'] == 'timeout' or (self.failure and self.failure['state'] == 'timeout'):
                state = dict(state, timeout_reached=True)
            if state == self._state:
                return
            self._state = copy.deepcopy(state)
            if state['state'] in ('blocked_by_dialog', 'timeout') and self.failure is None:
                self.failure = copy.deepcopy(state)
        if self.on_event:
            try:
                self.on_event(copy.deepcopy(state))
            except Exception:
                _logger.exception('CST 弹窗诊断回调失败')
                print('[CST_DIALOG] ' + json.dumps(state, ensure_ascii=False), file=sys.stderr, flush=True)
        elif state['state'] != 'clear':
            print('[CST_DIALOG] ' + json.dumps(state, ensure_ascii=False), file=sys.stderr, flush=True)

    def _scan(self):
        pid = self.pid() if callable(self.pid) else self.pid
        dialogs = _blocking(list_dialogs(**({'pid': pid} if pid is not None else {})), pid)
        state = dict(state='clear', attention_required=False, dialogs=dialogs,
                     label=self.label, target_pid=pid)
        if dialogs:
            state.update(state='blocked_by_dialog' if pid is not None else 'dialog_detected',
                         attention_required=True, scope_confirmed=pid is not None)
        elif self.timeout is not None and (
                (self._finished if self._finished is not None else time.monotonic()) -
                self._started >= self.timeout):
            state.update(state='timeout', attention_required=True,
                         message='步骤超时，未发现可见阻塞弹窗；调用尚未被取消')
        if dialogs and self.auto_acknowledge and pid is not None:
            actions = []
            for dialog in dialogs:
                body = dialog.get('body', '').lower()
                buttons = dialog.get('buttons', [])
                if ((dialog['title'], dialog.get('body', '')) in self.acknowledge_messages and
                    dialog.get('text_complete') and not dialog.get('read_errors') and
                    dialog['title'].strip().lower() in ('information', '信息') and body and
                    not any(word in body for word in _SAVE_KEYWORDS +
                            ('error', 'warning', 'failed', '错误', '失败', '警告', 'parameter', '参数')) and
                    len(buttons) == 1 and _normalize_button(buttons[0]['text']) in ('ok', '确定')):
                    actions.extend(dismiss_dialogs(prefer=(buttons[0]['text'],), pid=pid,
                                                   hwnd=dialog['hwnd'],
                                                   expected_message=(dialog['title'], dialog['body'])))
            if actions:
                state['actions'] = actions
        self._publish(state)

    def _loop(self):
        while not self._done.is_set():
            try:
                self._scan()
            except Exception as exc:
                self._publish(dict(state='monitor_error', attention_required=True, dialogs=[],
                                   label=self.label, error=structured_error(
                                       'cst_dialog_monitor_failed', f'{type(exc).__name__}: {exc}')))
            self._enforce_deadline()
            delay = self.poll
            if self.timeout is not None:
                remaining = self.timeout - (time.monotonic() - self._started)
                if remaining > 0:
                    delay = min(delay, remaining)
            self._done.wait(delay)

    def _enforce_deadline(self):
        """窗口读取失败也不能关闭步骤时限；收尾等待不计入步骤耗时。"""
        end = self._finished if self._finished is not None else time.monotonic()
        if self.timeout is None or end - self._started < self.timeout or self.failure is not None:
            return
        state = self.snapshot()
        failure = dict(state='timeout', attention_required=True, dialogs=state.get('dialogs', []),
                       label=self.label, monitor_diagnostics=state,
                       message='步骤达到时限；调用没有被强制取消')
        with self._lock:
            if self.failure is None:
                self.failure = failure
        if state['state'] == 'monitor_error':
            self._publish(dict(state, timeout_reached=True))
        else:
            self._publish(failure)

    def start(self):
        """启动并返回本对象；不访问 CST SDK。"""
        self._started = time.monotonic()
        self._thread = threading.Thread(target=self._loop, name='cst-dialog-monitor', daemon=True)
        self._thread.start()
        return self

    def stop(self):
        """停止巡检，等待有界窗口读取完成。"""
        self._finished = time.monotonic()
        self._done.set()
        if self._thread is not None:
            self._thread.join(timeout=10)
            if self._thread.is_alive():
                raise RuntimeError('CST 弹窗读取线程未能在 10s 内结束')
        self._enforce_deadline()

    def __enter__(self):
        return self.start()

    def __exit__(self, *args):
        self.stop()


@contextmanager
def guard(label, timeout=300.0, poll=1.0, *, pid=None, on_event=None,
          auto_acknowledge=False, acknowledge_messages=()):
    """兼容 with guard(...)；阻塞期间即报告，恢复后抛出记录的失败。

    返回值：yield DialogMonitor；原调用抛出的异常优先保留。线程无法强制取消 SDK。
    """
    with DialogMonitor(label, timeout, poll, pid=pid, on_event=on_event,
                       auto_acknowledge=auto_acknowledge,
                       acknowledge_messages=acknowledge_messages) as monitor:
        yield monitor
    if monitor.failure:
        raise CstDialogTimeout(f'步骤「{label}」{monitor.failure["state"]}：\n'
                               f'{_format_dialogs(monitor.failure["dialogs"])}', monitor.failure)


def main(argv=None):
    """兼容 CLI；--json 为结构化快照，--watch 可在建模进程外独立巡检。"""
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--json', action='store_true')
    parser.add_argument('--dialogs', action='store_true')
    parser.add_argument('--all', action='store_true')
    parser.add_argument('--watch', action='store_true')
    parser.add_argument('--pid', type=int)
    parser.add_argument('--interval', type=float, default=1)
    parser.add_argument('--duration', type=float, default=None)
    parser.add_argument('--dismiss', action='store_true')
    parser.add_argument('--hwnd', type=lambda value: int(value, 0))
    parser.add_argument('--button')
    args = parser.parse_args(argv)
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    if args.dismiss:
        if args.pid is None or args.hwnd is None or not args.button:
            parser.error('--dismiss 必须同时提供 --pid、--hwnd 和 --button')
        print(json.dumps(dismiss_dialogs(prefer=(args.button,), pid=args.pid, hwnd=args.hwnd),
                         ensure_ascii=False), flush=True)
    elif args.watch:
        with DialogMonitor('CLI', timeout=None, poll=args.interval, pid=args.pid,
                           on_event=lambda event: print(json.dumps(event, ensure_ascii=False), flush=True)):
            try:
                threading.Event().wait(args.duration)
            except KeyboardInterrupt:
                return 130
    else:
        dialogs = list_dialogs(only_cst=not args.all, **({'pid': args.pid} if args.pid is not None else {}))
        if args.pid is not None:
            dialogs = [d for d in dialogs if d['pid'] == args.pid]
        if args.json:
            print(json.dumps({'dialogs': dialogs, 'target_pid': args.pid}, ensure_ascii=False))
        else:
            print(_format_dialogs(dialogs))
            if not args.dialogs:
                print(describe_windows(only_cst=not args.all))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
