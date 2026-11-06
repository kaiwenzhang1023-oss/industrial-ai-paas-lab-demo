# RC3.6 independent gate. Never executes RC3.5 write gates or schema migrations.
[CmdletBinding()]
param([string]$PythonExe = 'D:\Anaconda3\python.exe', [switch]$RunPg16ReadOnly)
$ErrorActionPreference='Stop'
$root=Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -LiteralPath $root
$out=Join-Path $root 'release_evidence\rc36'
New-Item -ItemType Directory -Path $out -Force | Out-Null
if (-not (Test-Path -LiteralPath $PythonExe)) { throw 'Python executable missing' }
$version=(& $PythonExe --version 2>&1 | Out-String).Trim()
if ($version -notmatch '^Python 3\.14(?:\.|$)') { throw ('Requires Python 3.14: '+$version) }
$env:PYTHONPATH=$root+';'+(Join-Path $root 'backend')
try {
    & $PythonExe -m pytest -q tests 2>&1 | Tee-Object -FilePath (Join-Path $out 'LOCAL_PYTEST.log')
    if ($LASTEXITCODE -ne 0) { throw 'LOCAL_FAIL: pytest' }
    $node=Get-Command node -ErrorAction SilentlyContinue
    if (-not $node) { throw 'LOCAL_HOLD: Node unavailable' }
    & node --check (Join-Path $root 'enterprise_workbench\site\enterprise-console.js') 2>&1 | Tee-Object -FilePath (Join-Path $out 'LOCAL_NODE.log')
    if ($LASTEXITCODE -ne 0) { throw 'LOCAL_FAIL: JS syntax' }
    'LOCAL=PASS' | Set-Content -Path (Join-Path $out 'LOCAL_STATUS.txt')
    if ($RunPg16ReadOnly) {
        $secure=Read-Host 'RC3.6 NEW isolated PG16 database URL (database name must begin rc36_)' -AsSecureString
        $ptr=[IntPtr]::Zero
        try {
            $ptr=[Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
            $env:RC36_ISOLATED_PG16_DSN=[Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr)
            & $PythonExe (Join-Path $root 'gates\rc36_pg16_readonly.py')
            if ($LASTEXITCODE -ne 0) { Write-Warning 'PG16=HOLD/FAIL; see report' }
        } finally {
            Remove-Item Env:\RC36_ISOLATED_PG16_DSN -ErrorAction SilentlyContinue
            if ($ptr -ne [IntPtr]::Zero) { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr) }
            if ($secure) { $secure.Dispose() }
        }
    } else {
        'PG16=HOLD (isolated database not provided)' | Set-Content -Path (Join-Path $out 'PG16_STATUS.txt')
    }
} finally { Remove-Item Env:\PYTHONPATH -ErrorAction SilentlyContinue }
