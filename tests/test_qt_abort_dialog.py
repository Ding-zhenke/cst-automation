import copy
import json
import os
import subprocess
import time

import pytest
from cst_solver import qt_abort_dialog as mod


def snapshot():
    return dict(pid=70, hwnd=90, creation_time='100', root_id='1,2', owner_hwnd=80, owner_pid=70,
                title=mod.TITLE, body=mod.BODY, class_name=mod.CLASS, unsupported_controls=[],
                complete=True, observed_at=time.time(), controls=[
                    dict(id=f'1,{i}', name=name, kind='ControlType.Button', enabled=True, selected=None)
                    for i, name in enumerate(('Yes', 'No', 'Cancel'), 3)])


def test_exact_yes_preserves_evidence_and_unknown_stop(monkeypatch):
    calls = []
    monkeypatch.setattr(mod, '_bridge', lambda req: calls.append(req) or dict(action_requested=True))
    observed = snapshot(); original = copy.deepcopy(observed)
    result = mod.confirm_yes(observed, authorization_note='User authorized stopping original job',
                             confirm_stop=True, source_job_id='job-original')
    assert observed == original
    assert calls[0]['action'] == 'confirm_abort'
    assert result['action_requested'] is True
    assert result['original_call_returned'] == 'unknown'
    assert result['solver_stopped_verified'] is result['ds_idle_verified'] is False
    assert result['native_job_binding_verified'] is False


CHANGES = ['title', 'body', 'class_name', 'root_id', 'owner_hwnd', 'owner_pid', 'stale', 'future',
           'incomplete', 'extra', 'missing', 'rename', 'kind', 'disabled', 'duplicate_id',
           'root_as_button', 'unsupported', 'selected', 'pid', 'hwnd', 'creation_time']


def change(value, name):
    if name in ('title', 'body', 'class_name', 'root_id'): value[name] = 'unknown'
    elif name == 'owner_hwnd': value[name] = 0
    elif name == 'owner_pid': value[name] = 71
    elif name == 'stale': value['observed_at'] = time.time()-31
    elif name == 'future': value['observed_at'] = time.time()+31
    elif name == 'incomplete': value['complete'] = False
    elif name == 'extra': value['controls'].append(copy.deepcopy(value['controls'][0]))
    elif name == 'missing': value['controls'].pop()
    elif name == 'rename': value['controls'][1]['name'] = 'Yes'
    elif name == 'kind': value['controls'][1]['kind'] = 'ControlType.RadioButton'
    elif name == 'disabled': value['controls'][0]['enabled'] = False
    elif name == 'duplicate_id': value['controls'][1]['id'] = value['controls'][0]['id']
    elif name == 'root_as_button': value['controls'][0]['id'] = value['root_id']
    elif name == 'unsupported': value['unsupported_controls'] = ['ControlType.Edit']
    elif name == 'selected': value['controls'][0]['selected'] = True
    elif name in ('pid', 'hwnd'): value[name] = False
    elif name == 'creation_time': value[name] = 'unknown'


@pytest.mark.parametrize('field', CHANGES)
def test_bad_snapshot_never_launches_uia(monkeypatch, field):
    observed = snapshot(); change(observed, field)
    monkeypatch.setattr(mod, '_bridge', lambda req: pytest.fail('No UIA process allowed'))
    with pytest.raises(ValueError):
        mod.confirm_yes(observed, authorization_note='Authorized', confirm_stop=True, source_job_id='original')


@pytest.mark.parametrize('kwargs', [dict(authorization_note=''), dict(confirm_stop=False),
                                  dict(confirm_stop=1), dict(source_job_id=''), dict(source_job_id='x'*129)])
def test_missing_explicit_stop_authorization(monkeypatch, kwargs):
    args = dict(authorization_note='Authorized', confirm_stop=True, source_job_id='original')
    args.update(kwargs)
    monkeypatch.setattr(mod, '_bridge', lambda req: pytest.fail('No UIA process allowed'))
    with pytest.raises(ValueError):
        mod.confirm_yes(snapshot(), **args)


def test_inspection_only_and_unknown_refusal(monkeypatch):
    calls = []
    observed = snapshot()
    monkeypatch.setattr(mod, '_bridge', lambda req: calls.append(req) or observed)
    assert mod.inspect(pid=70, hwnd=90, expected_creation_time='100')['body'] == mod.BODY
    assert calls[0]['action'] == 'inspect_abort'
    observed['body'] = 'Save changes?'
    with pytest.raises(ValueError):
        mod.inspect(pid=70, hwnd=90, expected_creation_time='100')


@pytest.mark.skipif(os.name != 'nt', reason='Pure PowerShell guard, no desktop')
@pytest.mark.parametrize('field', ['none', 'title', 'body', 'class_name', 'root_id', 'owner_hwnd',
                                 'owner_pid', 'extra', 'missing', 'rename', 'kind', 'disabled',
                                 'duplicate_id', 'root_as_button', 'unsupported', 'selected'])
def test_actual_guard_rejects_changed_window(field):
    from cst_solver.result_cache_dialog import _GUARD_SCRIPT
    expected = snapshot(); actual = copy.deepcopy(expected)
    if field != 'none': change(actual, field)
    script = _GUARD_SCRIPT + "\n$ErrorActionPreference='Stop'; $a=$env:EXPECTED | ConvertFrom-Json; $b=$env:ACTUAL | ConvertFrom-Json; Assert-AbortSnapshot $b $a | ConvertTo-Json -Compress"
    ps = os.path.join(os.environ['SystemRoot'], 'System32', 'WindowsPowerShell', 'v1.0', 'powershell.exe')
    result = subprocess.run([ps, '-NoProfile', '-NonInteractive', '-Command', script],
                            env=dict(os.environ, EXPECTED=json.dumps(expected), ACTUAL=json.dumps(actual)),
                            capture_output=True, timeout=5, creationflags=0x08000000)
    assert (result.returncode == 0) == (field == 'none'), result.stderr
    if field == 'none': assert json.loads(result.stdout)['name'] == 'Yes'


@pytest.mark.skipif(os.name != 'nt', reason='PowerShell syntax only, no desktop')
def test_complete_bridge_parses_without_execution():
    from cst_solver.result_cache_dialog import _GUARD_SCRIPT, _SCRIPT
    ps = os.path.join(os.environ['SystemRoot'], 'System32', 'WindowsPowerShell', 'v1.0', 'powershell.exe')
    code = "$t=$null;$e=$null;[void][System.Management.Automation.Language.Parser]::ParseInput($env:SOURCE,[ref]$t,[ref]$e);if($e.Count){$e|Out-String;exit 1}"
    result = subprocess.run([ps, '-NoProfile', '-NonInteractive', '-Command', code],
                            env=dict(os.environ, SOURCE=_GUARD_SCRIPT+_SCRIPT), capture_output=True,
                            timeout=5, creationflags=0x08000000)
    assert result.returncode == 0, result.stdout+result.stderr
