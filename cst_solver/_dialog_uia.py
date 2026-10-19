# -*- coding: utf-8 -*-
"""有超时的 UI Automation 只读桥；进程隔离防止不可响应的 UIA provider 挂住巡检。"""
import json
import os
import subprocess

_SCRIPT = r'''
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes
$root = [System.Windows.Automation.AutomationElement]::FromHandle(
    [IntPtr]::new([Int64]::Parse($env:CST_DIALOG_HWND)))
$walker = [System.Windows.Automation.TreeWalker]::ControlViewWalker
$queue = [System.Collections.Generic.Queue[System.Windows.Automation.AutomationElement]]::new()
$queue.Enqueue($root)
$texts = @(); $buttons = @(); $count = 0; $progress = $false; $truncated = $false
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
        } elseif ($node -ne $root -and $current.Name) { $texts += $current.Name }
    }
    $child = $walker.GetFirstChild($node)
    while ($null -ne $child -and $queue.Count -lt 128) {
        $queue.Enqueue($child); $child = $walker.GetNextSibling($child)
    }
    if ($null -ne $child) { $truncated = $true }
}
@{body=($texts -join "`n"); buttons=@($buttons); has_progress=$progress;
  truncated=($truncated -or $queue.Count -gt 0)} |
    ConvertTo-Json -Depth 5 -Compress
'''


def read_content(hwnd):
    """参数：目标窗口 hwnd。返回值：正文、按钮、进度条；4s 内失败则抛异常。"""
    executable = os.path.join(os.environ.get('SystemRoot', r'C:\Windows'),
                              'System32', 'WindowsPowerShell', 'v1.0', 'powershell.exe')
    result = subprocess.run([executable, '-NoProfile', '-NonInteractive', '-Command', _SCRIPT],
                            env=dict(os.environ, CST_DIALOG_HWND=str(int(hwnd))),
                            capture_output=True, encoding='utf-8', errors='replace',
                            timeout=4, creationflags=0x08000000)
    if result.returncode:
        raise OSError(result.stderr.strip() or 'UI Automation 读取失败')
    return json.loads(result.stdout.lstrip('\ufeff'))
