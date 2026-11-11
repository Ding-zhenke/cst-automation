"""Explicit, bounded Windows UIA cache choice. Never a native CST SDK API."""
import copy
import json
import math
import os
import subprocess
import time

TITLE = 'Results May Get Incompatible With Model'
CHOICE = 'Store current results in result cache'

_GUARD_SCRIPT = r'''
function Test-HistoryPassiveNode($node) {
    try {
        $kind = $node.Current.ControlType.ProgrammaticName
        if ($kind -notin @('ControlType.Text','ControlType.Document','ControlType.Pane',
                'ControlType.Group','ControlType.Window') -and $node.Current.ClassName -ne 'QLabel') {
            return $false
        }
        foreach ($pattern in $node.GetSupportedPatterns()) {
            if ($pattern.ProgrammaticName -eq 'ValuePatternIdentifiers.Pattern') {
                if (-not $node.GetCurrentPattern($pattern).Current.IsReadOnly) { return $false }
            } elseif ($pattern.ProgrammaticName -in @('TextPatternIdentifiers.Pattern','TextPattern2Identifiers.Pattern')) {
                $readOnly = $node.GetCurrentPattern($pattern).DocumentRange.GetAttributeValue(
                    [System.Windows.Automation.TextPattern]::IsReadOnlyAttribute)
                if ($readOnly -isnot [bool] -or $readOnly -ne $true) { return $false }
            } else {
                return $false
            }
        }
        return $true
    } catch { return $false }
}
function Read-CacheText($node) {
    $text = $node.Current.Name
    if (-not $text) {
        try {
            $pattern = $null
            if ($node.TryGetCurrentPattern([System.Windows.Automation.TextPattern]::Pattern, [ref]$pattern)) {
                $text = $pattern.DocumentRange.GetText(8193)
            } elseif ($node.TryGetCurrentPattern([System.Windows.Automation.ValuePattern]::Pattern, [ref]$pattern)) {
                $text = $pattern.Current.Value
            }
        } catch { return @{text='';complete=$false} }
    }
    if (-not $text -or $text.Length -gt 8192) { return @{text='';complete=$false} }
    return @{text=$text;complete=$true}
}
function Assert-DialogSnapshot($snapshot, $expected) {
    if ($snapshot.complete -ne $true -or $expected.complete -ne $true -or -not $snapshot.body -or
        $snapshot.title -cne $expected.title -or $snapshot.body -cne $expected.body -or
        $snapshot.root_id -cne $expected.root_id -or $snapshot.controls.Count -ne $expected.controls.Count) {
        throw 'Dialog content changed'
    }
    foreach ($control in $snapshot.controls) {
        $match = @($expected.controls | Where-Object { $_.id -ceq $control.id })
        if ($match.Count -ne 1 -or $match[0].name -cne $control.name -or
            $match[0].kind -cne $control.kind -or $match[0].enabled -ne $control.enabled -or
            $match[0].selected -ne $control.selected) { throw 'Controls or selection changed' }
    }
}
function Assert-HistoryErrorSnapshot($snapshot, $expected) {
    Assert-DialogSnapshot $snapshot $expected
    if ($snapshot.unsupported_controls -or $expected.unsupported_controls) { throw 'Unsupported input controls' }
    if ($snapshot.title -cnotin @('History Error','CST MICROWAVE STUDIO - History Error') -or
        $snapshot.controls.Count -lt 1 -or $snapshot.controls.Count -gt 2) { throw 'Unknown history error dialog' }
    foreach ($control in $snapshot.controls) {
        if ($control.kind -cne 'ControlType.Button' -or $control.name -cnotin @('OK','Details >>')) {
            throw 'History error contains a choice or unknown control'
        }
    }
    $ok = @($snapshot.controls | Where-Object { $_.name -ceq 'OK' })
    if ($ok.Count -ne 1 -or -not $ok[0].enabled) { throw 'Unique enabled OK required' }
    return $ok[0]
}
function Assert-CacheSnapshot($snapshot, $expected) {
    Assert-DialogSnapshot $snapshot $expected
    if ($snapshot.title -cne 'Results May Get Incompatible With Model') { throw 'Unknown cache dialog' }
    $choice = @($snapshot.controls | Where-Object { $_.name -ceq 'Store current results in result cache' -and $_.kind -ceq 'ControlType.RadioButton' })
    $ok = @($snapshot.controls | Where-Object { $_.name -ceq 'OK' -and $_.kind -ceq 'ControlType.Button' })
    if ($choice.Count -ne 1 -or $ok.Count -ne 1 -or -not $choice[0].enabled -or -not $ok[0].enabled) { throw 'Unsupported controls' }
    return @{choice=$choice[0];ok=$ok[0]}
}
function Assert-AbortSnapshot($snapshot, $expected) {
    Assert-DialogSnapshot $snapshot $expected
    if ($snapshot.title -cne 'CST MICROWAVE STUDIO 2026' -or
        $snapshot.body -cne 'Do you really want to abort this calculation?' -or
        $snapshot.class_name -cne 'Qt683QWindow' -or $snapshot.class_name -cne $expected.class_name -or
        $snapshot.owner_hwnd -le 0 -or $snapshot.owner_hwnd -eq $snapshot.hwnd -or
        $snapshot.owner_hwnd -ne $expected.owner_hwnd -or $snapshot.owner_pid -ne $snapshot.pid -or
        $snapshot.owner_pid -ne $expected.owner_pid -or $snapshot.unsupported_controls -or
        $expected.unsupported_controls -or $snapshot.controls.Count -ne 3) { throw 'Unknown abort dialog' }
    $names = @(); $ids = @($snapshot.root_id)
    foreach ($control in $snapshot.controls) {
        if ($control.kind -cne 'ControlType.Button' -or $control.name -cnotin @('Yes','No','Cancel') -or
            $control.enabled -ne $true -or $null -ne $control.selected -or -not $control.id -or
            $ids -ccontains $control.id -or $names -ccontains $control.name) { throw 'Invalid abort buttons' }
        $names += $control.name; $ids += $control.id
    }
    return @($snapshot.controls | Where-Object { $_.name -ceq 'Yes' })[0]
}
'''

_SCRIPT = r'''
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes
$request = $env:CST_CACHE_REQUEST | ConvertFrom-Json
function Check-Identity {
    $process = Get-Process -Id $request.pid -ErrorAction Stop
    if (-not $process.ProcessName.StartsWith('CST',[StringComparison]::OrdinalIgnoreCase) -or
        $process.StartTime.ToUniversalTime().ToFileTimeUtc().ToString() -cne $request.creation_time) {
        throw 'Process identity changed or is not CST'
    }
}
Check-Identity
$root = [System.Windows.Automation.AutomationElement]::FromHandle([IntPtr]::new([Int64]$request.hwnd))
if ($root.Current.ProcessId -ne $request.pid -or $root.Current.NativeWindowHandle -ne $request.hwnd -or
    $root.Current.IsOffscreen) { throw 'Window identity changed or hidden' }
$walker = [System.Windows.Automation.TreeWalker]::RawViewWalker
$queue = [System.Collections.Generic.Queue[System.Windows.Automation.AutomationElement]]::new()
$queue.Enqueue($root)
$nodes = @{}; $controls = @(); $texts = @(); $count = 0; $complete = $true; $messageNodes = 0
$unsupported = @()
while ($queue.Count -gt 0) {
    $node = $queue.Dequeue(); $count++
    if ($count -gt 128) { throw 'Incomplete control tree' }
    $current = $node.Current
    if ($current.ProcessId -ne $request.pid) { throw 'Foreign control' }
    if (-not $current.IsOffscreen -and $node -ne $root) {
        $kind = $current.ControlType.ProgrammaticName
        if ($kind -notin @('ControlType.RadioButton','ControlType.Button') -and
                -not (Test-HistoryPassiveNode $node)) {
            $unsupported += $kind
        }
        $id = $node.GetRuntimeId() -join ','
        $selected = $null
        if ($kind -eq 'ControlType.RadioButton') {
            $selected = $node.GetCurrentPattern([System.Windows.Automation.SelectionItemPattern]::Pattern).Current.IsSelected
        }
        if ($kind -in @('ControlType.RadioButton','ControlType.Button')) {
            if ($nodes.ContainsKey($id)) { throw 'Duplicate runtime identity' }
            $nodes[$id] = $node
            $controls += @{id=$id;kind=$kind;name=$current.Name;enabled=$current.IsEnabled;selected=$selected}
        } elseif ($kind -in @('ControlType.Text','ControlType.Edit','ControlType.Document') -or $current.ClassName -eq 'QLabel') {
            $messageNodes++
            $read = Read-CacheText $node
            if (-not $read.complete) { $complete = $false }
            if ($read.text) { $texts += $read.text }
        } elseif ($current.Name) {
            # Preserve other accessible labels for change detection, but they
            # cannot by themselves establish a readable message.
            $texts += $current.Name
        }
    }
    $child = $walker.GetFirstChild($node)
    while ($null -ne $child) {
        if ($queue.Count + $count -ge 128) { throw 'Incomplete control tree' }
        $queue.Enqueue($child); $child = $walker.GetNextSibling($child)
    }
}
$body = $texts -join "`n"
if ($body.Length -gt 8192) { throw 'Message exceeds bound' }
$snapshot = @{pid=$request.pid;hwnd=$request.hwnd;creation_time=$request.creation_time;
    title=$root.Current.Name;root_id=($root.GetRuntimeId() -join ',');body=$body;
    complete=($complete -and $messageNodes -gt 0 -and [bool]$body);controls=@($controls);
    unsupported_controls=@($unsupported)}
if ($request.action -in @('inspect_abort','confirm_abort')) {
    Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
public static class AbortWindowIdentity {
    [DllImport("user32.dll")] public static extern IntPtr GetWindow(IntPtr hWnd, uint command);
    [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr hWnd, out uint pid);
}
'@
    $owner = [AbortWindowIdentity]::GetWindow([IntPtr]::new([Int64]$request.hwnd), 4)
    [uint32]$ownerPid = 0
    [void][AbortWindowIdentity]::GetWindowThreadProcessId($owner, [ref]$ownerPid)
    $snapshot.owner_hwnd = $owner.ToInt64(); $snapshot.owner_pid = $ownerPid
    $snapshot.class_name = $root.Current.ClassName
    $checkedAbort = Assert-AbortSnapshot $snapshot $snapshot
    Check-Identity
    if ($request.action -eq 'inspect_abort') { $snapshot | ConvertTo-Json -Depth 8 -Compress; exit }
    $age = [DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds()/1000.0 - $request.snapshot.observed_at
    if ($request.confirm_stop -ne $true -or -not ($request.authorization_note -is [string]) -or
        -not $request.authorization_note.Trim() -or $request.authorization_note.Length -gt 2048 -or
        $age -lt 0 -or $age -gt 30) { throw 'Fresh explicit stop authorization required' }
    $yes = Assert-AbortSnapshot $snapshot $request.snapshot
    Check-Identity
    if ($root.Current.ProcessId -ne $request.pid -or $root.Current.IsOffscreen -or
        $root.Current.NativeWindowHandle -ne $request.hwnd -or
        ([AbortWindowIdentity]::GetWindow([IntPtr]::new([Int64]$request.hwnd), 4)).ToInt64() -ne $snapshot.owner_hwnd) {
        throw 'Abort window identity changed'
    }
    $nodes[$yes.id].GetCurrentPattern([System.Windows.Automation.InvokePattern]::Pattern).Invoke()
    @{action=$request.action;action_requested=$true} | ConvertTo-Json -Compress
    exit
}
Check-Identity
if ($request.action -eq 'inspect') { $snapshot | ConvertTo-Json -Depth 8 -Compress; exit }
$expected = $request.snapshot
if ($request.action -eq 'acknowledge_history_error') {
    $ok = Assert-HistoryErrorSnapshot $snapshot $expected
    Check-Identity
    $nodes[$ok.id].GetCurrentPattern([System.Windows.Automation.InvokePattern]::Pattern).Invoke()
    @{action=$request.action;action_requested=$true} | ConvertTo-Json -Compress
    exit
}
$checked = Assert-CacheSnapshot $snapshot $expected
$choice = $checked.choice; $ok = $checked.ok
Check-Identity
if ($request.action -eq 'select') {
    $nodes[$choice.id].GetCurrentPattern([System.Windows.Automation.SelectionItemPattern]::Pattern).Select()
} elseif ($request.action -eq 'confirm' -and $choice.selected -eq $true) {
    if (-not $nodes[$choice.id].GetCurrentPattern([System.Windows.Automation.SelectionItemPattern]::Pattern).Current.IsSelected) {
        throw 'Cache choice no longer selected'
    }
    $nodes[$ok.id].GetCurrentPattern([System.Windows.Automation.InvokePattern]::Pattern).Invoke()
} else { throw 'Unsupported action or unselected cache choice' }
@{action=$request.action;action_requested=$true} | ConvertTo-Json -Compress
'''


def _bridge(request):
    payload = json.dumps(request, ensure_ascii=True, allow_nan=False)
    if len(payload) > 30000:
        raise ValueError('UIA request exceeds bound')
    executable = os.path.join(os.environ.get('SystemRoot', r'C:\Windows'),
                              'System32', 'WindowsPowerShell', 'v1.0', 'powershell.exe')
    try:
        result = subprocess.run([executable, '-NoProfile', '-NonInteractive', '-Command', _GUARD_SCRIPT + _SCRIPT],
                                env=dict(os.environ, CST_CACHE_REQUEST=payload), capture_output=True,
                                encoding='utf-8', errors='replace', timeout=4, creationflags=0x08000000)
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError('UIA call timed out; action outcome unknown; inspect before any retry') from exc
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or 'UIA failed; action outcome requires review')
    return json.loads(result.stdout.lstrip('\ufeff'))


def _identity(pid, hwnd, creation_time):
    if (type(pid) is not int or pid <= 0 or type(hwnd) is not int or hwnd <= 0 or
            not isinstance(creation_time, str) or not creation_time.isdecimal() or int(creation_time) <= 0):
        raise ValueError('Exact process/window identity required')


def inspect(*, pid, hwnd, expected_creation_time):
    """Read one exact window; absence/failure is not interpreted as completion."""
    _identity(pid, hwnd, expected_creation_time)
    result = _bridge(dict(action='inspect', pid=pid, hwnd=hwnd, creation_time=expected_creation_time))
    return dict(result, observed_at=time.time())


def _action(action, snapshot, authorization_note):
    observed = copy.deepcopy(snapshot)
    _identity(observed.get('pid'), observed.get('hwnd'), observed.get('creation_time'))
    stamp = observed.get('observed_at')
    if (not isinstance(authorization_note, str) or not 0 < len(authorization_note.strip()) <= 2048 or
            observed.get('title') != TITLE or observed.get('complete') is not True or
            not isinstance(observed.get('body'), str) or not observed['body'].strip() or
            len(observed['body']) > 8192 or not observed.get('root_id') or
            type(stamp) not in (int, float) or not math.isfinite(stamp) or not 0 <= time.time() - stamp <= 30):
        raise ValueError('Fresh complete known dialog and explicit authorization required')
    controls = observed.get('controls')
    if not isinstance(controls, list) or not 2 <= len(controls) <= 128:
        raise ValueError('Complete bounded controls required')
    choices = [c for c in controls if c.get('name') == CHOICE and c.get('kind') == 'ControlType.RadioButton']
    buttons = [c for c in controls if c.get('name') == 'OK' and c.get('kind') == 'ControlType.Button']
    if (len(choices) != 1 or len(buttons) != 1 or choices[0].get('enabled') is not True or
            buttons[0].get('enabled') is not True):
        raise ValueError('Unique enabled cache choice and OK required')
    if action == 'confirm' and choices[0].get('selected') is not True:
        raise ValueError('Independent snapshot must show cache choice selected')
    result = _bridge(dict(action=action, pid=observed['pid'], hwnd=observed['hwnd'],
                          creation_time=observed['creation_time'], snapshot=observed))
    return dict(result, authorization_note=authorization_note, before=observed,
                original_call_returned='unknown', cache_verified=False,
                next_step='independent_inspect' if action == 'select' else 'review_original_job_and_cache')


def select(snapshot, *, authorization_note):
    """Request only selection; never confirms in this call."""
    return _action('select', snapshot, authorization_note)


def confirm(snapshot, *, authorization_note):
    """Confirm only a freshly observed selected cache option; never a generic OK."""
    return _action('confirm', snapshot, authorization_note)
