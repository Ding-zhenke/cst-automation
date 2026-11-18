[CmdletBinding()]
param(
    [Parameter(Mandatory)][string]$AdsAgent,
    [Parameter(Mandatory)][string]$Workspace,
    [Parameter(Mandatory)][string]$AdsInstance,
    [Parameter(Mandatory)][string]$Slot
)

$agentPath = (Resolve-Path -LiteralPath $AdsAgent -ErrorAction Stop).Path
$workspacePath = (Resolve-Path -LiteralPath $Workspace -ErrorAction Stop).Path
if (-not $env:ADS_AGENT_HOME) { throw 'Set ADS_AGENT_HOME to the configured bridge state directory.' }

$settings = Get-ItemProperty -LiteralPath 'HKCU:\Software\Keysight\EEsof License Configuration' -ErrorAction Stop
$savedProduct = $settings.ADS_PRODSEL_PREVIOUS
if (-not $savedProduct) { throw 'ADS has no saved startup product for this Windows user.' }

$previousProduct = $env:ADS_PRODSEL_PREVIOUS
$previousAutostart = $env:ADS_PRODSEL_AUTOSTART
try {
    $env:ADS_PRODSEL_PREVIOUS = $savedProduct
    $env:ADS_PRODSEL_AUTOSTART = 'TRUE'
    & $agentPath --pretty launch --workspace $workspacePath --ads $AdsInstance --slot $Slot
    $launchExitCode = $LASTEXITCODE
}
finally {
    $env:ADS_PRODSEL_PREVIOUS = $previousProduct
    $env:ADS_PRODSEL_AUTOSTART = $previousAutostart
}
exit $launchExitCode
