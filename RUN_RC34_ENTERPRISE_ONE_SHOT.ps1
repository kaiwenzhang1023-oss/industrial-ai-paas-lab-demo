# PowerShell 5.1 / Windows 11. Explicit isolated PG16 opt-in; no Docker, no migrations,
# no database creation and no changes to frozen A/RC2 or existing Render services.
[CmdletBinding()]
param(
    [string]$PythonExe = '',
    [switch]$RunIsolatedPG16,
    [switch]$RunLiveBrowser
)
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -LiteralPath $root

if (-not $PythonExe) {
    $candidate = 'D:\Anaconda3\python.exe'
    if (Test-Path -LiteralPath $candidate) { $PythonExe = $candidate }
    else {
        $command = Get-Command py -ErrorAction SilentlyContinue
        if ($command) { $PythonExe = 'py' }
    }
}
if (-not $PythonExe) { throw 'Python 3.14 not found. Supply -PythonExe with the absolute 3.14 interpreter path.' }

function Invoke-GatePython([string]$ScriptPath) {
    if ($PythonExe -eq 'py') {
        & py -3.14 $ScriptPath | Out-Host
    } else {
        & $PythonExe $ScriptPath | Out-Host
    }
    $nativeCode = $LASTEXITCODE
    return [int]$nativeCode
}
if ($PythonExe -eq 'py') { $version = & py -3.14 -c 'import sys;print("%d.%d"%sys.version_info[:2])' }
else { $version = & $PythonExe -c 'import sys;print("%d.%d"%sys.version_info[:2])' }
if ($LASTEXITCODE -ne 0 -or $version -ne '3.14') { throw 'Python 3.14 required. Do not use a Python 3.10 environment.' }

if ($RunIsolatedPG16) {
    if (-not $env:V19B_RC34_ISOLATED_TEST_DATABASE_URL) {
        Write-Warning 'Isolated PG16 URL is not configured. PG16 enterprise gate remains HOLD; no database accessed.'
    } else {
        Write-Host 'PG16 isolated test mutation explicitly enabled. Frozen RC2 remains inaccessible by guard.'
        $env:V19B_RC34_ENABLE_ISOLATED_MUTATIONS = 'YES'
        $pgCode = Invoke-GatePython (Join-Path $root 'tests\enterprise_pg16_gate.py')
        Write-Host ('ISOLATED_PG16_EXIT=' + $pgCode)
        Remove-Item Env:\V19B_RC34_ENABLE_ISOLATED_MUTATIONS -ErrorAction SilentlyContinue
    }
}
if ($RunLiveBrowser) {
    Write-Host 'Starting candidate-only live browser workflow gate (will fail closed on stale brand).'
    $browserCode = Invoke-GatePython (Join-Path $root 'tests\live_business_workflow_gate.py')
    Write-Host ('LIVE_BROWSER_EXIT=' + $browserCode)
}
$gateCode = Invoke-GatePython (Join-Path $root 'RUN_FINAL_RELEASE_GATE.py')
Write-Host ('FINAL_RELEASE_GATE_EXIT=' + $gateCode)
Write-Host ('SUMMARY=' + (Join-Path $root 'release_evidence\FINAL_RELEASE_GATE_RESULT.json'))
Write-Host ('PG16=' + (Join-Path $root 'release_evidence\pg16_enterprise\RESULT.json'))
Write-Host ('LIVE_BROWSER=' + (Join-Path $root 'release_evidence\live_business\RESULT.json'))
if ($gateCode -ne 0) { Write-Warning 'Final Release Gate remains HOLD/FAIL; do not freeze or deploy as final release.' }
exit $gateCode
