from pathlib import Path
import os

import pytest

from tpc_service.sessions import model3d_archive_recovery as mod
from tpc_service.sessions.store import read
from tpc_service.errors import ServiceError


def scene(tmp_path):
    target = tmp_path / 'model.cst'; target.write_bytes(b'failed archive')
    pair = target.with_suffix(''); pair.mkdir()
    (pair / 'Model.lok').write_bytes(b'lock bytes are not archive data')
    (pair / 'history.json').write_bytes(b'full history')
    return target, pair, tmp_path / 'audit'


def test_exact_root_lock_excluded_with_metadata_not_claimed_as_copied(tmp_path, monkeypatch):
    target, pair, evidence = scene(tmp_path)
    real_digest = mod.file_digest
    def digest(path):
        if Path(path) == pair / 'Model.lok': raise PermissionError('native exclusive lock')
        return real_digest(path)
    monkeypatch.setattr(mod, 'file_digest', digest)
    mod._backup(target, evidence)
    manifest = read(evidence / 'before_manifest.json')
    assert manifest['companion'] == {'history.json': real_digest(pair / 'history.json')}
    exclusion = manifest['excluded_companion']['Model.lok']
    assert exclusion['content_backed_up'] is False
    assert exclusion['stat']['size'] == (pair / 'Model.lok').stat().st_size
    assert exclusion['reason'] == 'owned_cst_companion_root_temporary_lock'
    assert not (evidence / 'before/companion/Model.lok').exists()
    assert (evidence / 'before/companion/history.json').read_bytes() == b'full history'


@pytest.mark.parametrize('name', ['other.lok', 'nested/Model.lok', 'locked_result.bin'])
def test_other_read_failures_are_not_ignored(tmp_path, monkeypatch, name):
    target, pair, evidence = scene(tmp_path)
    blocked = pair / name; blocked.parent.mkdir(exist_ok=True); blocked.write_bytes(b'essential')
    real_digest = mod.file_digest
    def digest(path):
        if Path(path) == blocked: raise PermissionError('locked essential file')
        return real_digest(path)
    monkeypatch.setattr(mod, 'file_digest', digest)
    with pytest.raises(PermissionError): mod._backup(target, evidence)
    assert not (evidence / 'before_manifest.json').exists()


@pytest.mark.parametrize('state', ['empty', 'partial', 'manifest', 'not_reviewing'])
def test_only_empty_uncommitted_reviewing_snapshot_can_continue(tmp_path, state):
    target, pair, evidence = scene(tmp_path)
    before = evidence / 'before'; before.mkdir(parents=True)
    if state == 'partial': (before / 'unknown').write_bytes(b'do not delete')
    if state == 'manifest': (evidence / 'before_manifest.json').write_text('{}')
    if state == 'empty':
        mod._backup(target, evidence, allow_empty_resume=True)
        assert read(evidence / 'before_manifest.json')['project'] == mod.file_digest(target)
    else:
        with pytest.raises(ServiceError): mod._backup(target, evidence, allow_empty_resume=state != 'not_reviewing')
        if state == 'partial': assert (before / 'unknown').read_bytes() == b'do not delete'


@pytest.mark.skipif(os.name != 'nt', reason='Windows file sharing semantics')
def test_real_windows_exclusive_lock_can_be_statted_but_not_read(tmp_path):
    import ctypes
    from ctypes import wintypes
    target, pair, evidence = scene(tmp_path)
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
        wintypes.LPVOID, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
    kernel.CreateFileW.restype = wintypes.HANDLE
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    handle = kernel.CreateFileW(str(pair / 'Model.lok'), 0x80000000, 0, None, 3, 0x80, None)
    assert handle != wintypes.HANDLE(-1).value
    try:
        with pytest.raises(PermissionError): (pair / 'Model.lok').read_bytes()
        mod._backup(target, evidence)
        assert read(evidence / 'before_manifest.json')['excluded_companion']['Model.lok']['content_backed_up'] is False
    finally:
        kernel.CloseHandle(handle)
