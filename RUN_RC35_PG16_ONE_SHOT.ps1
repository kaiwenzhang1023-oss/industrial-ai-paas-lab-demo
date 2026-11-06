# RC3.5 only: independent Neon PG16 branch; Windows PowerShell 5.1 compatible.
[CmdletBinding()]
param([string]$PythonExe = 'D:\Anaconda3\python.exe')
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -LiteralPath $root
if (-not (Test-Path -LiteralPath $PythonExe)) { throw "Python 3.14 not found: $PythonExe" }
$version = (& $PythonExe --version 2>&1 | Out-String).Trim()
Write-Host ('PYTHON_VERSION=' + $version)
if ($LASTEXITCODE -ne 0 -or $version -notmatch '^Python 3\.14(?:\.|$)') { throw 'Requires Python 3.14 (not Python 3.10).' }
& $PythonExe -c 'import fastapi, httpx, psycopg, pytest'
if ($LASTEXITCODE -eq 0) { Write-Host 'DEPENDENCIES=PASS' -ForegroundColor Green }
if ($LASTEXITCODE -ne 0) { throw 'DEPENDENCIES_FAIL: required modules could not be imported by the selected Python interpreter.' }
if (-not (Get-Command node -ErrorAction SilentlyContinue)) { throw 'Node.js is required for Version A/B reconciliation.' }
$env:PYTHONPATH = $root + ';' + (Join-Path $root 'backend')
Write-Host 'STEP 1: RC3.5 local Python regression' -ForegroundColor Cyan
& $PythonExe -m pytest -q tests
if ($LASTEXITCODE -ne 0) { throw 'LOCAL_GATE_FAIL: PG16 writes NOT attempted.' }
Write-Host 'STEP 2: RC3.5 isolated PG16 preflight' -ForegroundColor Cyan
Write-Host 'Only branch rc35-final-gate-isolated-20261105; database industrial_v19b_preview; endpoint ep-patient-wind-bbme3mck.'
Write-Host 'Existing preview, RC3.4, V1.8, and production are NOT targets.'
$secure = $null; $bstr = [IntPtr]::Zero
try {
    $secure = Read-Host 'Paste Neon RC3.5 isolated branch connection URL (hidden input)' -AsSecureString
    $bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
    $env:V19B_RC35_ISOLATED_TEST_DATABASE_URL = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr)
    $confirm = Read-Host 'This gate creates only isolated test tenants/runs. Type RUN_RC35_ISOLATED to confirm'
    if ($confirm -cne 'RUN_RC35_ISOLATED') { throw 'No PG16 write authorization; test not executed.' }
    $env:V19B_RC35_ENABLE_ISOLATED_MUTATIONS = 'YES'
    & $PythonExe (Join-Path $root 'tests\rc35_isolated_pg16_gate.py')
    $code = $LASTEXITCODE
    Write-Host ('RC35_PG16_GATE_EXIT=' + $code)
    Write-Host ('REPORT=' + (Join-Path $root 'release_evidence\pg16_enterprise\RESULT.json'))
    Write-Host ('GOLDEN_EVIDENCE=' + (Join-Path $root 'release_evidence\pg16_enterprise\RC35_GOLDEN_SCENARIOS_PG16.json'))
    if ($code -ne 0) { throw 'RC35 PG16 HOLD/FAIL. Do not deploy. Return RESULT.json.' }
    Write-Host 'RC35_PG16_GATE_PASS' -ForegroundColor Green
}
finally {
    Remove-Item Env:\V19B_RC35_ISOLATED_TEST_DATABASE_URL -ErrorAction SilentlyContinue
    Remove-Item Env:\V19B_RC35_ENABLE_ISOLATED_MUTATIONS -ErrorAction SilentlyContinue
    Remove-Item Env:\PYTHONPATH -ErrorAction SilentlyContinue
    if ($bstr -ne [IntPtr]::Zero) { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr) }
    if ($secure) { $secure.Dispose() }
}
