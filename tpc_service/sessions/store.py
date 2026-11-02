"""Atomic records, process identities and cross-process file locks."""
import contextlib
import ctypes
import hashlib
import json
import os
from pathlib import Path
import re
import time
from uuid import uuid4

from tpc_service.errors import ServiceError


def identifier(value):
    if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,100}', value):
        raise ServiceError('invalid_session_argument', 'Invalid identifier')
    return value


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     allow_nan=False, separators=(',', ':')).encode()).hexdigest()


def read(path, default=None):
    try:
        return json.loads(Path(path).read_text(encoding='utf-8'))
    except FileNotFoundError:
        return default


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + '.' + uuid4().hex + '.tmp')
    try:
        with temp.open('x', encoding='utf-8') as stream:
            json.dump(value, stream, ensure_ascii=False, allow_nan=False, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(str(temp), str(path))
    finally:
        temp.unlink(missing_ok=True)


@contextlib.contextmanager
def lock(path, *, blocking=True):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    stream = path.open('a+b')
    if path.stat().st_size == 0:
        stream.write(b'0')
        stream.flush()
    acquired = False
    try:
        if os.name == 'nt':
            import msvcrt
            deadline = time.monotonic() + (30 if blocking else 0)
            while True:
                try:
                    stream.seek(0)
                    msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
                    acquired = True
                    break
                except OSError:
                    if time.monotonic() >= deadline:
                        raise ServiceError('session_locked', 'Session is locked by another process')
                    time.sleep(.02)
        else:
            import fcntl
            fcntl.flock(stream.fileno(), fcntl.LOCK_EX | (0 if blocking else fcntl.LOCK_NB))
            acquired = True
        yield
    finally:
        if acquired:
            if os.name == 'nt':
                import msvcrt
                stream.seek(0)
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)
        stream.close()


def process_identity(pid):
    """None means confirmed absent; access denial is never treated as death."""
    pid = int(pid)
    if os.name == 'nt':
        from ctypes import wintypes
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        kernel.OpenProcess.restype = wintypes.HANDLE
        kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel.GetProcessTimes.argtypes = [wintypes.HANDLE] + [ctypes.POINTER(wintypes.FILETIME)] * 4
        kernel.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, wintypes.DWORD,
                                                    wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]
        handle = kernel.OpenProcess(0x1000, False, pid)
        if not handle:
            error = ctypes.get_last_error()
            if error == 87:
                return None
            raise ServiceError('process_identity_unavailable', 'Cannot inspect process identity', pid=pid, winerror=error)
        try:
            times = [wintypes.FILETIME() for _ in range(4)]
            if not kernel.GetProcessTimes(handle, *[ctypes.byref(t) for t in times]):
                raise ctypes.WinError(ctypes.get_last_error())
            if times[1].dwHighDateTime or times[1].dwLowDateTime:
                return None
            size = wintypes.DWORD(32768)
            image = ctypes.create_unicode_buffer(size.value)
            if not kernel.QueryFullProcessImageNameW(handle, 0, image, ctypes.byref(size)):
                raise ctypes.WinError(ctypes.get_last_error())
            return {'pid': pid, 'started': (times[0].dwHighDateTime << 32) | times[0].dwLowDateTime,
                    'image': os.path.normcase(image.value)}
        finally:
            kernel.CloseHandle(handle)
    try:
        stat = Path('/proc') / str(pid) / 'stat'
        values = stat.read_text().rsplit(')', 1)[1].split()
        if values[0] == 'Z':
            return None
        return {'pid': pid, 'started': values[19], 'image': os.readlink('/proc/%d/exe' % pid)}
    except FileNotFoundError:
        return None


def alive(identity):
    return bool(identity) and process_identity(identity['pid']) == identity


def contained(root, path):
    root, path = Path(root).resolve(), Path(path).resolve()
    if path == root or root not in path.parents:
        raise ServiceError('workdir_escape', 'Path must remain inside session directory')
    return path


def assert_environment_unclaimed(root, session_id, identity):
    """Caller holds registry.lock, which serializes every environment assignment."""
    for path in Path(root).glob('ses-*/session.json'):
        state = read(path)
        if state['session_id'] != session_id and state.get('environment') == identity and state['status'] != 'closed':
            raise ServiceError('session_environment_claimed', 'Environment belongs to another session')
