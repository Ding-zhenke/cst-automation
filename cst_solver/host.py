"""Read-only Windows host diagnostics and an opt-in checked CST session entry.

No process enumeration is used as proof of machine idleness. No SDK is imported
until open_host_session has passed its desktop/identity checks.
"""
import ctypes
from ctypes import wintypes
import os

__all__ = ['HostSessionError', 'diagnose_host_session', 'process_identity', 'open_host_session']


class HostSessionError(RuntimeError):
    def __init__(self, code, details):
        super().__init__(f'{code}: use an accessible interactive host session; do not retry launching CST')
        self.code, self.details = code, details


def process_identity(pid):
    """Return creation FILETIME as an exact decimal string, or explicit unknown."""
    result = dict(pid=pid, creation_time=None, status='unknown')
    if os.name != 'nt':
        return dict(result, error='Windows required')
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel.GetProcessTimes.argtypes = [wintypes.HANDLE] + [ctypes.POINTER(wintypes.FILETIME)] * 4
    kernel.GetProcessTimes.restype = wintypes.BOOL
    handle = kernel.OpenProcess(0x1000, False, pid)
    if not handle:
        return dict(result, error=f'OpenProcess: {ctypes.get_last_error()}')
    try:
        times = [wintypes.FILETIME() for _ in range(4)]
        if not kernel.GetProcessTimes(handle, *(ctypes.byref(t) for t in times)):
            return dict(result, error=f'GetProcessTimes: {ctypes.get_last_error()}')
        ticks = (times[0].dwHighDateTime << 32) | times[0].dwLowDateTime
        return dict(result, status='known', creation_time=str(ticks))
    finally:
        kernel.CloseHandle(handle)


def _classify_desktop(station_visible, current_name, input_name):
    if not station_visible:
        return 'restricted'
    if not current_name or not input_name:
        return 'unknown'
    return 'interactive' if current_name == input_name else 'restricted'


def _desktop_access():
    user = ctypes.WinDLL('user32', use_last_error=True)
    user.GetProcessWindowStation.restype = wintypes.HANDLE
    user.GetUserObjectInformationW.argtypes = [wintypes.HANDLE, ctypes.c_int,
                                              ctypes.c_void_p, wintypes.DWORD,
                                              ctypes.POINTER(wintypes.DWORD)]
    user.GetUserObjectInformationW.restype = wintypes.BOOL
    user.OpenInputDesktop.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    user.OpenInputDesktop.restype = wintypes.HANDLE
    user.CloseDesktop.argtypes = [wintypes.HANDLE]
    user.GetThreadDesktop.argtypes = [wintypes.DWORD]
    user.GetThreadDesktop.restype = wintypes.HANDLE
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.GetCurrentThreadId.restype = wintypes.DWORD

    class Flags(ctypes.Structure):
        _fields_ = [('inherit', wintypes.BOOL), ('reserved', wintypes.BOOL), ('flags', wintypes.DWORD)]

    station = user.GetProcessWindowStation()  # borrowed handle: never close
    flags, needed = Flags(), wintypes.DWORD()
    if not station or not user.GetUserObjectInformationW(station, 1, ctypes.byref(flags),
                                                         ctypes.sizeof(flags), ctypes.byref(needed)):
        return dict(desktop='unknown', error=f'window station: {ctypes.get_last_error()}')
    if not flags.flags & 1:  # WSF_VISIBLE
        return dict(desktop='restricted', error='process window station is not visible')
    desktop = user.OpenInputDesktop(0, False, 1)  # DESKTOP_READOBJECTS, no mutation
    if not desktop:
        return dict(desktop='restricted', error=f'input desktop inaccessible: {ctypes.get_last_error()}')
    def name(handle):
        buffer = ctypes.create_unicode_buffer(1024)
        if not handle or not user.GetUserObjectInformationW(handle, 2, buffer,
                                                             ctypes.sizeof(buffer), ctypes.byref(needed)):
            return None
        return buffer.value
    try:
        current_name = name(user.GetThreadDesktop(kernel.GetCurrentThreadId()))
        input_name = name(desktop)
        return dict(desktop=_classify_desktop(True, current_name, input_name),
                    current_desktop=current_name, input_desktop=input_name)
    finally:
        user.CloseDesktop(desktop)


def diagnose_host_session():
    """Describe desktop access, not license, IPC reachability or whole-host idleness."""
    report = dict(platform=os.name, desktop='unknown', ipc='not_probed',
                  process_visibility='unknown', machine_idle='unknown',
                  guidance='Use an accessible interactive host; serialize CST work with a whole-host lock.')
    if os.name != 'nt':
        return dict(report, error='Windows required')
    try:
        report.update(_desktop_access())
    except OSError as exc:
        report['error'] = str(exc)
    return report


def open_host_session(filename=None, *, pid=None, expected_creation_time=None):
    """Check desktop, then launch once or attach once to an identified process.

    Caller must already hold a whole-host serial lock and verify other CST work
    is finished. This function cannot certify idleness from a restricted view.
    """
    report = diagnose_host_session()
    if report['desktop'] != 'interactive':
        raise HostSessionError('cst_host_unavailable', report)
    if pid is not None:
        identity = process_identity(pid)
        if not expected_creation_time or identity['creation_time'] != expected_creation_time:
            raise HostSessionError('cst_process_identity_unknown_or_changed', dict(report, process=identity))
    from cst_solver import setup
    try:
        return setup(filename) if pid is None else setup.attach(pid=pid, filename=filename)
    except Exception as exc:
        raise HostSessionError('cst_session_open_failed',
                               dict(report, ipc='unknown', operation='attach' if pid is not None else 'launch',
                                    error=f'{type(exc).__name__}: {exc}')) from exc
