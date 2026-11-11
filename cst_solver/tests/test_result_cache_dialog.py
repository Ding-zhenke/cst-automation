import copy
import time
import json
import os
import subprocess

import pytest


def snapshot():
    return dict(pid=70, hwnd=90, creation_time='100', title='Results May Get Incompatible With Model',
                body='Fixture cache question', root_id='1,2,3', complete=True,
                controls=[dict(id='1,2,4', kind='ControlType.RadioButton', name='Store current results in result cache',
                               enabled=True, selected=False),
                          dict(id='1,2,5', kind='ControlType.RadioButton', name='Delete all results', enabled=True, selected=False),
                          dict(id='1,2,6', kind='ControlType.Button', name='OK', enabled=True, selected=None)],
                observed_at=time.time())


def install_bridge(monkeypatch):
    from cst_solver import result_cache_dialog as mod
    calls = []
    def bridge(request):
        calls.append(copy.deepcopy(request))
        return dict(action=request['action'], action_requested=True)
    monkeypatch.setattr(mod, '_bridge', bridge)
    return mod, calls


def test_select_is_explicit_and_does_not_confirm(monkeypatch):
    mod, calls = install_bridge(monkeypatch)
    result = mod.select(snapshot(), authorization_note='User requested preserving results')
    assert [c['action'] for c in calls] == ['select']
    assert result['cache_verified'] is False
    assert result['original_call_returned'] == 'unknown'
    assert result['next_step'] == 'independent_inspect'


def test_confirm_requires_independently_observed_selected_option(monkeypatch):
    mod, calls = install_bridge(monkeypatch)
    with pytest.raises(ValueError, match='selected'):
        mod.confirm(snapshot(), authorization_note='Preserve cache')
    assert calls == []
    observed = snapshot()
    observed['controls'][0]['selected'] = True
    assert mod.confirm(observed, authorization_note='Preserve cache')['cache_verified'] is False
    assert [c['action'] for c in calls] == ['confirm']


@pytest.mark.parametrize('change', [
    {'body': ''}, {'complete': False}, {'title': 'Unknown Yes/No'},
    {'observed_at': 1}, {'pid': True}, {'creation_time': ''}, {'root_id': ''},
])
def test_unreadable_stale_or_unknown_dialog_never_acts(monkeypatch, change):
    mod, calls = install_bridge(monkeypatch)
    observed = snapshot(); observed.update(change)
    with pytest.raises(ValueError):
        mod.select(observed, authorization_note='Preserve cache')
    assert not calls


def test_no_authorization_no_action(monkeypatch):
    mod, calls = install_bridge(monkeypatch)
    with pytest.raises(ValueError):
        mod.select(snapshot(), authorization_note='')
    assert not calls


def test_ambiguous_choice_never_acts(monkeypatch):
    mod, calls = install_bridge(monkeypatch)
    observed = snapshot(); observed['controls'].append(dict(observed['controls'][0]))
    with pytest.raises(ValueError):
        mod.select(observed, authorization_note='Preserve cache')
    assert not calls


@pytest.mark.skipif(os.name != 'nt', reason='PowerShell boundary test; no desktop or CST')
@pytest.mark.parametrize('change', ['none', 'body', 'root_id', 'selection', 'enabled', 'label', 'duplicate', 'incomplete'])
def test_powershell_rechecks_real_snapshot_comparison(change):
    from cst_solver.result_cache_dialog import _GUARD_SCRIPT
    expected = snapshot(); current = copy.deepcopy(expected)
    if change in ('body', 'root_id'):
        current[change] = 'changed'
    elif change == 'selection':
        current['controls'][0]['selected'] = True
    elif change == 'enabled':
        current['controls'][0]['enabled'] = False
    elif change == 'label':
        current['controls'][0]['name'] = 'Delete all results'
    elif change == 'duplicate':
        current['controls'].append(dict(current['controls'][0]))
    elif change == 'incomplete':
        current['complete'] = False
    executable = os.path.join(os.environ['SystemRoot'], 'System32', 'WindowsPowerShell', 'v1.0', 'powershell.exe')
    code = _GUARD_SCRIPT + "\n$ErrorActionPreference='Stop'; $a=$env:TEST_EXPECTED | ConvertFrom-Json; $b=$env:TEST_CURRENT | ConvertFrom-Json; Assert-CacheSnapshot $b $a | ConvertTo-Json -Compress"
    result = subprocess.run([executable, '-NoProfile', '-NonInteractive', '-Command', code],
                            env=dict(os.environ, TEST_EXPECTED=json.dumps(expected), TEST_CURRENT=json.dumps(current)),
                            capture_output=True, timeout=5, creationflags=0x08000000)
    assert (result.returncode == 0) == (change == 'none'), result.stderr


@pytest.mark.skipif(os.name != 'nt', reason='PowerShell text-pattern stub; no desktop')
@pytest.mark.parametrize('mode', ['name', 'value', 'missing', 'oversized'])
def test_actual_text_reader_with_offline_pattern_stubs(mode):
    from cst_solver.result_cache_dialog import _GUARD_SCRIPT
    code = r'''
$ErrorActionPreference='Stop'
Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes
$node = [PSCustomObject]@{Current=[PSCustomObject]@{Name=''}}
if ($env:TEST_MODE -eq 'name') { $node.Current.Name = 'Original question' }
$node | Add-Member ScriptMethod TryGetCurrentPattern {
    param($pattern, [ref]$value)
    if ($env:TEST_MODE -in @('value','oversized') -and $pattern -eq [System.Windows.Automation.ValuePattern]::Pattern) {
        $text = 'Pattern question'
        if ($env:TEST_MODE -eq 'oversized') { $text = 'x' * 8193 }
        $value.Value = [PSCustomObject]@{Current=[PSCustomObject]@{Value=$text}}
        return $true
    }
    return $false
}
Read-CacheText $node | ConvertTo-Json -Compress
'''
    executable = os.path.join(os.environ['SystemRoot'], 'System32', 'WindowsPowerShell', 'v1.0', 'powershell.exe')
    result = subprocess.run([executable, '-NoProfile', '-NonInteractive', '-Command', _GUARD_SCRIPT+code],
                            env=dict(os.environ, TEST_MODE=mode), capture_output=True, timeout=5,
                            creationflags=0x08000000)
    assert result.returncode == 0, result.stderr
    actual = json.loads(result.stdout)
    expected = {'name': 'Original question', 'value': 'Pattern question'}.get(mode, '')
    assert actual == {'text': expected, 'complete': mode in ('name', 'value')}


@pytest.mark.parametrize('failure', ['timeout', 'exit', 'json'])
def test_bridge_failures_never_retry_or_claim_completion(monkeypatch, failure):
    from types import SimpleNamespace
    from cst_solver import result_cache_dialog as mod
    calls = []
    def run(*args, **kwargs):
        calls.append(1)
        if failure == 'timeout':
            raise subprocess.TimeoutExpired('fixture', 4)
        return SimpleNamespace(returncode=1 if failure == 'exit' else 0,
                               stderr='fixture failure', stdout='invalid json')
    monkeypatch.setattr(mod.subprocess, 'run', run)
    with pytest.raises((RuntimeError, ValueError)):
        mod._bridge(dict(action='select'))
    assert calls == [1]
