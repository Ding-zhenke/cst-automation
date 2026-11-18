# Run a noninteractive text command. PowerShell streams 1 and 2 receive its
# output lines, and the caller can propagate the child's status with exit $LASTEXITCODE.
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string] $Executable,
    [AllowEmptyCollection()]
    [AllowEmptyString()]
    [string[]] $ArgumentList = @(),
    [string] $WorkingDirectory = (Get-Location).Path,
    [string] $TextEncoding = 'utf-8'
)

$ErrorActionPreference = 'Stop'
$start = [System.Diagnostics.ProcessStartInfo]::new()
if (Test-Path -LiteralPath $Executable -PathType Leaf) {
    $start.FileName = (Resolve-Path -LiteralPath $Executable).ProviderPath
}
else {
    $start.FileName = (Get-Command -Name ([WildcardPattern]::Escape($Executable)) -CommandType Application |
        Select-Object -First 1).Source
}
$start.WorkingDirectory = (Resolve-Path -LiteralPath $WorkingDirectory).ProviderPath
$start.UseShellExecute = $false
$start.CreateNoWindow = $true
$start.RedirectStandardInput = $true
$start.RedirectStandardOutput = $true
$start.RedirectStandardError = $true

if ($start.PSObject.Properties['ArgumentList']) {
    foreach ($item in $ArgumentList) { $start.ArgumentList.Add($item) }
}
else {
    # Windows PowerShell 5.1 has no ArgumentList. Quote for the Windows C
    # runtime, including empty arguments and backslashes before quotes/end.
    $quoted = foreach ($item in $ArgumentList) {
        $escaped = $item -replace '(\\*)"', '$1$1\"' -replace '(\\+)$', '$1$1'
        '"' + $escaped + '"'
    }
    $start.Arguments = $quoted -join ' '
}

# Python with redirected pipes can default to the Windows ANSI code page.
# Match both ends of the text pipes. For other executables that write a
# legacy code page, pass their actual encoding to the reader.
$encoding = [Text.Encoding]::GetEncoding($TextEncoding)
$start.EnvironmentVariables['PYTHONIOENCODING'] = $encoding.WebName
$start.StandardOutputEncoding = $encoding
$start.StandardErrorEncoding = $encoding

$process = [Diagnostics.Process]::new()
$process.StartInfo = $start
try {
    [void] $process.Start()
    $process.StandardInput.Close()
    # Keep both pipes draining, including when the child fills stderr before
    # writing stdout. Waiting on a single pipe first could deadlock.
    $outLine = $process.StandardOutput.ReadLineAsync()
    $errLine = $process.StandardError.ReadLineAsync()
    while ($outLine -or $errLine) {
        $pending = @(@($outLine, $errLine) | Where-Object { $null -ne $_ })
        [void] [Threading.Tasks.Task]::WaitAny([Threading.Tasks.Task[]] $pending)
        if ($outLine -and $outLine.IsCompleted) {
            $line = $outLine.GetAwaiter().GetResult()
            $outLine = $null
            if ($null -ne $line) {
                $PSCmdlet.WriteObject($line)
                $outLine = $process.StandardOutput.ReadLineAsync()
            }
        }
        if ($errLine -and $errLine.IsCompleted) {
            $line = $errLine.GetAwaiter().GetResult()
            $errLine = $null
            if ($null -ne $line) {
                # A diagnostic line is independent of the child's exit code.
                # Keep stream 2 redirectable even under the caller's Stop policy.
                $exception = [System.Management.Automation.RemoteException]::new($line)
                $record = [System.Management.Automation.ErrorRecord]::new(
                    $exception, 'NativeCommandError', 'NotSpecified', $null)
                Write-Error -ErrorRecord $record -ErrorAction Continue
                $errLine = $process.StandardError.ReadLineAsync()
            }
        }
    }
    $process.WaitForExit()
    exit $process.ExitCode
}
finally {
    $process.Dispose()
}
