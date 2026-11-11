import copy
import json
import os
import subprocess
import time

import pytest


def snapshot():
    return dict(pid=70, hwnd=90, creation_time='100', root_id='1,2',
                title='CST MICROWAVE STUDIO - History Error', body='Fixture native command error',
                complete=True, observed_at=time.time(), controls=[
                    dict(id='1,3', name='OK', kind='ControlType.Button', enabled=True, selected=None),
                    dict(id='1,4', name='Details >>', kind='ControlType.Button', enabled=True, selected=None)])


def test_explicit_history_confirmation_does_not_modify_snapshot(monkeypatch):
    from cst_solver import qt_history_error as mod
    calls=[]
    monkeypatch.setattr(mod, '_bridge', lambda r: calls.append(r) or dict(action_requested=True))
    observed=snapshot(); original=copy.deepcopy(observed)
    result=mod.acknowledge(observed, authorization_note='Allow the original failed call to return')
    assert observed==original
    assert calls[0]['action']=='acknowledge_history_error'
    assert result['recovery_verified'] is False
    assert result['original_call_returned']=='unknown'


@pytest.mark.parametrize('change', ['title','empty_body','incomplete','stale','radio','yes_no','disabled','duplicate','authorization','other_input'])
def test_unknown_or_incomplete_request_never_invokes(monkeypatch, change):
    from cst_solver import qt_history_error as mod
    monkeypatch.setattr(mod, '_bridge', lambda r: pytest.fail('Native UIA process launched'))
    observed=snapshot(); note='Explicit acknowledgement'
    if change=='title': observed['title']='Warning'
    elif change=='empty_body': observed['body']=''
    elif change=='incomplete': observed['complete']=False
    elif change=='stale': observed['observed_at']=1
    elif change=='radio': observed['controls'][1]['kind']='ControlType.RadioButton'
    elif change=='yes_no': observed['controls'][1]['name']='Yes'
    elif change=='disabled': observed['controls'][0]['enabled']=False
    elif change=='duplicate': observed['controls'].append(dict(observed['controls'][0]))
    elif change=='authorization': note=''
    elif change=='other_input': observed['unsupported_controls']=['ControlType.CheckBox']
    with pytest.raises(ValueError): mod.acknowledge(observed, authorization_note=note)


@pytest.mark.skipif(os.name!='nt',reason='Pure PowerShell comparison, no desktop')
@pytest.mark.parametrize('change', ['none','body','title','root_id','radio','yes_no','incomplete','other_input'])
def test_action_side_guard_uses_actual_fresh_snapshot(change):
    from cst_solver.result_cache_dialog import _GUARD_SCRIPT
    expected=snapshot(); actual=copy.deepcopy(expected)
    if change in ('body','title','root_id'): actual[change]='changed'
    elif change=='radio': actual['controls'][1]['kind']='ControlType.RadioButton'
    elif change=='yes_no': actual['controls'][1]['name']='Yes'
    elif change=='incomplete': actual['complete']=False
    elif change=='other_input': actual['unsupported_controls']=['ControlType.CheckBox']
    code=_GUARD_SCRIPT+"\n$ErrorActionPreference='Stop'; $a=$env:TEST_EXPECTED | ConvertFrom-Json; $b=$env:TEST_ACTUAL | ConvertFrom-Json; Assert-HistoryErrorSnapshot $b $a | ConvertTo-Json -Compress"
    ps=os.path.join(os.environ['SystemRoot'],'System32','WindowsPowerShell','v1.0','powershell.exe')
    result=subprocess.run([ps,'-NoProfile','-NonInteractive','-Command',code],
        env=dict(os.environ,TEST_EXPECTED=json.dumps(expected),TEST_ACTUAL=json.dumps(actual)),
        capture_output=True,timeout=5,creationflags=0x08000000)
    assert (result.returncode==0)==(change=='none'),result.stderr


@pytest.mark.skipif(os.name != 'nt', reason='Pure PowerShell stub, no desktop')
@pytest.mark.parametrize('kind,pattern,readonly,expected', [
    ('Document', 'TextPatternIdentifiers.Pattern', True, True),
    ('Document', 'TextPatternIdentifiers.Pattern', False, False),
    ('Document', 'TextPatternIdentifiers.Pattern', 'NotSupported', False),
    ('Document', 'ValuePatternIdentifiers.Pattern', True, True),
    ('Document', 'ValuePatternIdentifiers.Pattern', False, False),
    ('Pane', 'TogglePatternIdentifiers.Pattern', True, False),
    ('Text', 'SelectionPatternIdentifiers.Pattern', True, False),
    ('CheckBox', 'TextPatternIdentifiers.Pattern', True, False),
    ('Group', 'unknown', True, False),
])
def test_reader_classifies_actual_supported_patterns(kind, pattern, readonly, expected):
    from cst_solver.result_cache_dialog import _GUARD_SCRIPT
    code = _GUARD_SCRIPT + r'''
$ErrorActionPreference='Stop'
Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes
$fixture=$env:TEST_NODE | ConvertFrom-Json
$node=[pscustomobject]@{Current=[pscustomobject]@{
    ControlType=[pscustomobject]@{ProgrammaticName=('ControlType.'+$fixture.kind)};ClassName=''};
    Pattern=$fixture.pattern;ReadOnly=$fixture.readonly}
$node | Add-Member ScriptMethod GetSupportedPatterns { @([pscustomobject]@{ProgrammaticName=$this.Pattern}) }
$node | Add-Member ScriptMethod GetCurrentPattern {
    param($pattern)
    $range=[pscustomobject]@{ReadOnly=$this.ReadOnly}
    $range | Add-Member ScriptMethod GetAttributeValue { param($attribute) $this.ReadOnly }
    [pscustomobject]@{Current=[pscustomobject]@{IsReadOnly=$this.ReadOnly};DocumentRange=$range}
}
Test-HistoryPassiveNode $node | ConvertTo-Json -Compress
'''
    ps = os.path.join(os.environ['SystemRoot'], 'System32', 'WindowsPowerShell', 'v1.0', 'powershell.exe')
    result = subprocess.run([ps, '-NoProfile', '-NonInteractive', '-Command', code],
        env=dict(os.environ, TEST_NODE=json.dumps(dict(kind=kind, pattern=pattern, readonly=readonly))),
        capture_output=True, timeout=5, creationflags=0x08000000)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) is expected
