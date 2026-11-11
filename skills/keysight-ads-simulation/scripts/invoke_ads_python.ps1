param(
    [Parameter(Mandatory = $true, Position = 0)]
    [string] $Script,
    [string] $AdsRoot,
    [string[]] $ScriptArgs = @()
)

$ErrorActionPreference = 'Stop'

function Write-FailureJson {
    param([string] $Message, [int] $Code)
    [ordered]@{
        tool = 'invoke_ads_python'
        status = 'failed'
        ads_version = $null
        de_api_version = $null
        workspace = $null
        netlist = $null
        dataset = $null
        return_code = $Code
        warnings = @()
        fatal_errors = @($Message)
        metrics = @{}
    } | ConvertTo-Json -Depth 6
}

try {
    $scriptPath = (Resolve-Path -LiteralPath $Script -ErrorAction Stop).Path
    $candidates = [System.Collections.Generic.List[string]]::new()
    $selectionSource = 'discovery'
    if ($AdsRoot) {
        $candidates.Add($AdsRoot)
        $selectionSource = 'explicit AdsRoot'
    }
    else {
        if ($env:HPEESOF_DIR) {
            $candidates.Add($env:HPEESOF_DIR)
            $selectionSource = 'HPEESOF_DIR'
        }
        else {
            foreach ($parent in @('D:\Program Files\Keysight', 'C:\Program Files\Keysight')) {
                if (Test-Path -LiteralPath $parent) {
                    Get-ChildItem -LiteralPath $parent -Directory -Filter 'ADS*' |
                        Sort-Object Name -Descending |
                        ForEach-Object { $candidates.Add($_.FullName) }
                }
            }
        }
    }

    $validCandidates = [System.Collections.Generic.List[string]]::new()
    foreach ($candidate in ($candidates | Select-Object -Unique)) {
        $python = Join-Path $candidate 'tools\python\python.exe'
        $ads = Join-Path $candidate 'bin\ads.exe'
        $sim = Join-Path $candidate 'bin\hpeesofsim.exe'
        if ((Test-Path -LiteralPath $python) -and (Test-Path -LiteralPath $ads) -and (Test-Path -LiteralPath $sim)) {
            $validCandidates.Add((Resolve-Path -LiteralPath $candidate).Path)
        }
    }
    $validCandidates = @($validCandidates | Select-Object -Unique)
    if ($validCandidates.Count -eq 0) {
        throw "No valid ADS installation found from $selectionSource (requires ads.exe, hpeesofsim.exe, and bundled Python)."
    }
    if ($selectionSource -eq 'discovery' -and $validCandidates.Count -gt 1) {
        throw "Multiple ADS installations found; pass -AdsRoot explicitly: $($validCandidates -join '; ')"
    }
    $selected = $validCandidates[0]

    $env:HPEESOF_DIR = $selected
    $pythonExe = Join-Path $selected 'tools\python\python.exe'
    & $pythonExe $scriptPath @ScriptArgs
    exit $LASTEXITCODE
}
catch {
    Write-FailureJson -Message $_.Exception.Message -Code 2
    exit 2
}
