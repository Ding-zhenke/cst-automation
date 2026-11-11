# -*- coding: utf-8 -*-
"""有超时的 UI Automation 只读桥；进程隔离防止不可响应的 UIA provider 挂住巡检。"""
import json
import os
import subprocess
import time

_SCRIPT = r'''
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes
$root = [System.Windows.Automation.AutomationElement]::FromHandle(
    [IntPtr]::new([Int64]::Parse($env:CST_DIALOG_HWND)))
$walker = [System.Windows.Automation.TreeWalker]::ControlViewWalker
if ($env:CST_DIALOG_VIEW -eq 'raw') {
    $walker = [System.Windows.Automation.TreeWalker]::RawViewWalker
}
$queue = [System.Collections.Generic.Queue[System.Windows.Automation.AutomationElement]]::new()
$queue.Enqueue($root)
$texts = @(); $buttons = @(); $count = 0; $progress = $false; $truncated = $false; $errors = @()
while ($queue.Count -gt 0 -and $count -lt 128) {
    $node = $queue.Dequeue(); $count++
    $current = $node.Current
    if (-not $current.IsOffscreen) {
        $kind = $current.ControlType.ProgrammaticName
        # 部分 provider 仅报告 Pane，ClassName 仍能识别标准/Qt 按钮。
        if ($kind -eq 'ControlType.Button' -or $current.ClassName -in @('Button','QPushButton','QToolButton')) {
            $buttons += @{text=$current.Name; ctrl_id=0; hwnd=$current.NativeWindowHandle;
                          enabled=$current.IsEnabled; visible=$true}
        } elseif ($kind -eq 'ControlType.ProgressBar' -or $current.ClassName -in @('msctls_progress32','QProgressBar')) { $progress = $true
        } elseif ($node -ne $root) {
            $text = $current.Name
            # Text-only patterns: never infer the message from button labels.
            if (-not $text -and $kind -in @('ControlType.Text','ControlType.Edit','ControlType.Document')) {
                try {
                    $pattern = $null
                    if ($node.TryGetCurrentPattern([System.Windows.Automation.TextPattern]::Pattern, [ref]$pattern)) {
                        $text = $pattern.DocumentRange.GetText(8193)
                    } elseif ($node.TryGetCurrentPattern([System.Windows.Automation.ValuePattern]::Pattern, [ref]$pattern)) {
                        $text = $pattern.Current.Value
                    }
                } catch { $errors += $_.Exception.Message }
            }
            if ($text) {
                if ($text.Length -gt 8192) { $text = $text.Substring(0,8192); $truncated = $true }
                $texts += $text
            }
        }
    }
    $child = $walker.GetFirstChild($node)
    while ($null -ne $child -and $queue.Count -lt 128) {
        $queue.Enqueue($child); $child = $walker.GetNextSibling($child)
    }
    if ($null -ne $child) { $truncated = $true }
}
@{body=($texts -join "`n"); buttons=@($buttons); has_progress=$progress; read_errors=@($errors);
  truncated=($truncated -or $queue.Count -gt 0)} |
    ConvertTo-Json -Depth 5 -Compress
'''


def read_content(hwnd):
    """Read two bounded UIA views; preserve missing text and failed attempts."""
    if type(hwnd) is not int or hwnd <= 0:
        raise ValueError('hwnd must be a positive integer')
    executable = os.path.join(os.environ.get('SystemRoot', r'C:\Windows'),
                              'System32', 'WindowsPowerShell', 'v1.0', 'powershell.exe')
    deadline = time.monotonic() + 4
    attempts = []
    selected = dict(body='', buttons=[], has_progress=False, truncated=False, read_errors=[])
    for view in ('control', 'raw'):
        try:
            remaining = min(2, deadline - time.monotonic())
            if remaining <= 0:
                raise OSError('UI Automation total read deadline reached')
            result = subprocess.run(
                [executable, '-NoProfile', '-NonInteractive', '-Command', _SCRIPT],
                env=dict(os.environ, CST_DIALOG_HWND=str(hwnd), CST_DIALOG_VIEW=view),
                capture_output=True, encoding='utf-8', errors='replace',
                timeout=remaining, creationflags=0x08000000)
            if result.returncode:
                raise OSError(result.stderr.strip() or 'UI Automation 读取失败')
            current = json.loads(result.stdout.lstrip('\ufeff'))
            if not isinstance(current, dict) or not isinstance(current.get('body'), str):
                raise ValueError('Invalid UIA content response')
            current.setdefault('read_errors', [])
            attempts.append(dict(current, view=view, status='read'))
            if not any(a['status'] == 'read' for a in attempts[:-1]) or current['body']:
                selected = current
            if current['body']:
                break
        except (OSError, ValueError, subprocess.SubprocessError) as exc:
            attempts.append(dict(view=view, status='failed', error=f'{type(exc).__name__}: {exc}'))
    errors = [a['error'] for a in attempts if a['status'] == 'failed']
    # A failed view remains evidence; a successful fallback is not permission to act.
    return dict(selected, read_errors=list(selected.get('read_errors', [])) + errors,
                read_attempts=attempts, text_view=attempts[-1]['view'])
