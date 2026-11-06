# RC3.6 isolated Neon PG16 one-shot gate.
# Scope is fixed to the RC3.6 child branch and least-privilege runtime role.
# No migrations/DDL are executed. Business DML + one application-level Worker
# failure/retry injection require an explicit typed acknowledgement.
[CmdletBinding()]
param(
    [string]$PythonExe = '',
    [switch]$ReadOnlyOnly
)
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -LiteralPath $root
$out = Join-Path $root 'release_evidence\rc36'
New-Item -ItemType Directory -Path $out -Force | Out-Null
$statusPath = Join-Path $out 'GATE_STATUS.json'
$localLog = Join-Path $out 'LOCAL_PYTEST_PG16.log'
$depsLog = Join-Path $out 'PG16_DEPENDENCIES.log'
$readonlyLog = Join-Path $out 'PG16_READONLY.log'
$businessLog = Join-Path $out 'PG16_BUSINESS.log'
$venv = Join-Path $root '.rc36-pg16-venv-py314'
$venvPython = Join-Path $venv 'Scripts\python.exe'
$status = [ordered]@{
    release = 'RC3.6'
    LOCAL = 'HOLD'
    BROWSER_MOCK = 'PASS_USER_REPORTED_4_OF_4'
    PG16_BRANCH_METADATA = 'PASS_READ_ONLY_CONNECTOR_INSPECTION'
    PG16_READONLY = 'HOLD_NOT_RUN'
    PG16_BUSINESS = 'HOLD_NOT_RUN'
    PG16 = 'HOLD'
    BROWSER_REAL_E2E = 'HOLD_NOT_RUN'
    RENDER = 'HOLD_NOT_RUN'
    migrations_executed = $false
    ddl_executed = $false
    source_erp_wms_mutations = $false
    worker_fault_injection_executed = $false
    target = [ordered]@{
        project_id = 'super-glade-55757112'
        branch_id = 'br-green-glade-bbnahfli'
        branch_name = 'rc36-pg16-isolated-20261106'
        parent_branch_id = 'br-divine-glitter-bb7wf2ve'
        parent_branch_name = 'rc35-final-gate-isolated-20261105'
        endpoint_id = 'ep-holy-star-bbv8lyg7'
        database = 'industrial_v19b_preview'
        required_role = 'v19b_app_runtime'
    }
}
$exitCode = 0
$secure = $null
$ptr = [IntPtr]::Zero
$plainDsn = $null
$hadDsn = Test-Path Env:\RC36_ISOLATED_PG16_DSN
$oldDsn = $env:RC36_ISOLATED_PG16_DSN
$oldPyPath = $env:PYTHONPATH
$oldDbUrl = $env:DATABASE_URL
$oldWriteAck = $env:RC36_ENABLE_ISOLATED_WRITES
$oldFaultAck = $env:RC36_ENABLE_WORKER_FAULT_INJECTION

# Run Python through a Python subprocess so native stderr warnings are captured in
# the evidence log, not promoted to terminating PowerShell errors on Windows PS 5.1.
function Invoke-PythonGateLogged {
    param([string]$Python, [string]$LogPath, [string[]]$Arguments)
    $runner = 'import subprocess,sys; p=sys.argv[1]; log=sys.argv[2]; args=sys.argv[3:]; f=open(log,chr(119),encoding=chr(117)+chr(116)+chr(102)+chr(45)+chr(56)); result=subprocess.run([p]+args,stdout=f,stderr=subprocess.STDOUT,check=False); f.close(); sys.exit(result.returncode)'
    & $Python -c $runner $Python $LogPath @Arguments
    return $LASTEXITCODE
}

function Resolve-Python314 {
    param([string]$Requested)
    if (-not [string]::IsNullOrWhiteSpace($Requested)) {
        if (-not (Test-Path -LiteralPath $Requested)) { throw "PYTHON_NOT_FOUND: $Requested" }
        return (Resolve-Path -LiteralPath $Requested).Path
    }
    $launcher = Get-Command py.exe -ErrorAction SilentlyContinue
    if ($launcher) {
        $candidate = & $launcher.Source -3.14 -c 'import sys;print(sys.executable)' 2>$null
        if ($LASTEXITCODE -eq 0 -and $candidate) {
            $candidate = ([string]$candidate | Select-Object -Last 1).Trim()
            if (Test-Path -LiteralPath $candidate) { return (Resolve-Path -LiteralPath $candidate).Path }
        }
    }
    $python = Get-Command python.exe -ErrorAction SilentlyContinue
    if ($python) {
        $candidate = $python.Source
        $version = & $candidate -c 'import sys;print(sys.version_info.major*100+sys.version_info.minor)' 2>$null
        if ($LASTEXITCODE -eq 0 -and ([string]$version).Trim() -eq '314') { return $candidate }
    }
    throw 'PYTHON_314_NOT_FOUND: install/register Python 3.14 or pass -PythonExe with the full python.exe path.'
}

try {
    Write-Host 'RC3.6 PG16 GATE: LOCAL -> READ-ONLY PREFLIGHT -> EXPLICITLY AUTHORIZED ISOLATED BUSINESS DML' -ForegroundColor Cyan
    Write-Host 'Target branch: rc36-pg16-isolated-20261106 / ep-holy-star-bbv8lyg7 / industrial_v19b_preview'
    Write-Host 'Required database role: v19b_app_runtime (least privilege; owner/superuser roles are rejected).'
    Write-Host 'No migrations or DDL are run by this script.'

    $PythonExe = Resolve-Python314 -Requested $PythonExe
    $version = & $PythonExe -c 'import sys;print(sys.version_info.major,sys.version_info.minor,sys.version_info.micro,sep=chr(46))' 2>&1
    if ($LASTEXITCODE -ne 0 -or ([string]$version).Trim() -notmatch '^3\.14\.') {
        throw "PYTHON_VERSION_HOLD: RC3.6 PG16 gate requires Python 3.14.x; detected $version"
    }
    Write-Host "PYTHON_BASE=$PythonExe; VERSION=$version"

    if (-not (Test-Path -LiteralPath $venvPython)) {
        Write-Host 'STEP=CREATE_ISOLATED_PG16_VENV'
        & $PythonExe -m venv $venv
        if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $venvPython)) {
            throw 'LOCAL_HOLD: unable to create isolated Python 3.14 environment.'
        }
    }
    $venvVersion = & $venvPython -c 'import sys;print(sys.version_info.major,sys.version_info.minor,sys.version_info.micro,sep=chr(46))' 2>&1
    if ($LASTEXITCODE -ne 0 -or ([string]$venvVersion).Trim() -notmatch '^3\.14\.') {
        throw "LOCAL_HOLD: isolated venv is not Python 3.14.x: $venvVersion"
    }

    Write-Host 'STEP=INSTALL_OR_VERIFY_GATE_DEPENDENCIES'
    & $venvPython -m pip install --disable-pip-version-check -r (Join-Path $root 'requirements-rc36-pg16-gate.txt') *> $depsLog
    $pipExit = $LASTEXITCODE
    Get-Content -LiteralPath $depsLog | Out-Host
    if ($pipExit -ne 0) { throw 'LOCAL_HOLD: Python gate dependencies could not be installed.' }

    $node = Get-Command node.exe -ErrorAction SilentlyContinue
    if (-not $node) { $node = Get-Command node -ErrorAction SilentlyContinue }
    if (-not $node) { throw 'LOCAL_HOLD: Node.js is required for native Version A RC8 execution.' }
    $nodeVersion = & $node.Source --version 2>&1
    if ($LASTEXITCODE -ne 0) { throw 'LOCAL_HOLD: Node.js version probe failed.' }
    Write-Host "NODE=$($node.Source); VERSION=$nodeVersion"

    $env:PYTHONPATH = $root + ';' + (Join-Path $root 'backend') + ';' + (Join-Path $root 'tests')
    Write-Host 'STEP=LOCAL_FULL_PYTHON_REGRESSION (Browser Mock is intentionally not rerun)'
    $pytestExit = Invoke-PythonGateLogged -Python $venvPython -LogPath $localLog -Arguments @('-m','pytest','-q','tests')
    Get-Content -LiteralPath $localLog | Out-Host
    if ($pytestExit -ne 0) { $status.LOCAL = 'FAIL'; throw 'LOCAL_FAIL: Python regression failed; no database connection was attempted.' }
    foreach ($file in @('enterprise_workbench\site\engine.js','g3\a_rc8_adapter.js','enterprise_workbench\site\enterprise-console.js')) {
        & $node.Source --check (Join-Path $root $file)
        if ($LASTEXITCODE -ne 0) { $status.LOCAL = 'FAIL'; throw "LOCAL_FAIL: Node syntax check failed: $file" }
    }
    $status.LOCAL = 'PASS'
    Write-Host 'LOCAL=PASS'

    Write-Host ''
    Write-Host 'Paste the connection string copied from THIS Neon branch only.' -ForegroundColor Yellow
    Write-Host 'Neon project : industrial-ai-paas-v19-version-b-preview (super-glade-55757112)'
    Write-Host 'Branch       : rc36-pg16-isolated-20261106 (br-green-glade-bbnahfli)'
    Write-Host 'Endpoint     : ep-holy-star-bbv8lyg7.c-15.us-east-1.aws.neon.tech'
    Write-Host 'Database     : industrial_v19b_preview'
    Write-Host 'Role         : v19b_app_runtime'
    Write-Host 'Do NOT use owner, cloud_admin, RC3.5, default, preview, or pooled connection strings.'
    $secure = Read-Host 'RC3.6 isolated PostgreSQL connection string (hidden input)' -AsSecureString
    $ptr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
    $plainDsn = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr)
    $env:RC36_ISOLATED_PG16_DSN = $plainDsn

    Write-Host 'STEP=PG16_READ_ONLY_PREFLIGHT (SELECT only; transaction_read_only=on)'
    $readonlyExit = Invoke-PythonGateLogged -Python $venvPython -LogPath $readonlyLog -Arguments @((Join-Path $root 'gates\rc36_pg16_readonly.py'))
    Get-Content -LiteralPath $readonlyLog | Out-Host
    $readonlyReportPath = Join-Path $out 'PG16_READONLY_RESULT.json'
    if (Test-Path -LiteralPath $readonlyReportPath) {
        $readonlyReport = Get-Content -LiteralPath $readonlyReportPath -Raw | ConvertFrom-Json
        $status.PG16_READONLY = [string]$readonlyReport.status
    }
    if ($readonlyExit -ne 0 -or $status.PG16_READONLY -ne 'PASS') {
        $status.PG16 = 'HOLD'
        throw 'PG16_READONLY_HOLD: target identity, schema, privileges, seed data or read-only preflight did not PASS. No business writes were started.'
    }
    Write-Host 'PG16_READONLY=PASS'

    if ($ReadOnlyOnly) {
        $status.PG16_BUSINESS = 'HOLD_READ_ONLY_ONLY_REQUESTED'
        $status.PG16 = 'HOLD'
        Write-Warning 'Read-only preflight passed; business writes and fault injection were not requested.'
    } else {
        Write-Host ''
        Write-Host 'NEXT STEP WILL INSERT ONLY NEW rc36gate-* test tenants/runs/decisions/outbox/receipts/audit rows on this child branch.' -ForegroundColor Yellow
        Write-Host 'It will NOT run migrations, alter mock_ERP/WMS source rows, call external MES/SRM, or touch the RC3.5 parent branch.'
        Write-Host 'It WILL perform one application-level Worker failure/retry injection and verify lease recovery.'
        $ack = Read-Host 'Type RUN_RC36_ISOLATED_PG16_WRITES_AND_FAULT_TESTS to authorize these isolated test writes and the one Worker fault injection'
        if ($ack -cne 'RUN_RC36_ISOLATED_PG16_WRITES_AND_FAULT_TESTS') {
            $status.PG16_BUSINESS = 'HOLD_USER_ACK_NOT_GIVEN'
            $status.PG16 = 'HOLD'
            Write-Warning 'No exact acknowledgement supplied. No business writes or fault injection were executed.'
        } else {
            $env:RC36_ENABLE_ISOLATED_WRITES = 'YES'
            $env:RC36_ENABLE_WORKER_FAULT_INJECTION = 'YES'
            Write-Host 'STEP=PG16_REAL_BUSINESS_GATE'
            $businessExit = Invoke-PythonGateLogged -Python $venvPython -LogPath $businessLog -Arguments @((Join-Path $root 'tests\rc36_isolated_pg16_gate.py'))
            Get-Content -LiteralPath $businessLog | Out-Host
            $businessReportPath = Join-Path $out 'PG16_BUSINESS_RESULT.json'
            if (Test-Path -LiteralPath $businessReportPath) {
                $businessReport = Get-Content -LiteralPath $businessReportPath -Raw | ConvertFrom-Json
                $status.PG16_BUSINESS = [string]$businessReport.status
                $status.worker_fault_injection_executed = ([string]$businessReport.checks.worker_fault_injected.status -eq 'PASS')
            } elseif ($businessExit -ne 0) {
                $status.PG16_BUSINESS = 'FAIL_NO_REPORT'
            }
            if ($businessExit -eq 0 -and $status.PG16_BUSINESS -eq 'PASS') {
                $status.PG16 = 'PASS'
            } elseif ($status.PG16_BUSINESS -like 'HOLD*') {
                $status.PG16 = 'HOLD'
            } else {
                $status.PG16 = 'FAIL'
            }
        }
    }
    if ($status.PG16 -ne 'PASS') { $exitCode = 5 }
} catch {
    $status.error = ([string]$_).Split([Environment]::NewLine)[0]
    if ($status.LOCAL -ne 'PASS') { $exitCode = 2 }
    elseif ($status.PG16_READONLY -ne 'PASS') { $exitCode = 3 }
    elseif ($status.PG16 -eq 'FAIL') { $exitCode = 4 }
    else { $exitCode = 5 }
    Write-Host ('GATE_STOPPED: ' + $status.error) -ForegroundColor Red
} finally {
    $status.evidence_bundle = 'RC36_PG16_EVIDENCE.zip'
    $status | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath $statusPath -Encoding UTF8
    Remove-Item Env:\RC36_ISOLATED_PG16_DSN -ErrorAction SilentlyContinue
    Remove-Item Env:\RC36_ENABLE_ISOLATED_WRITES -ErrorAction SilentlyContinue
    Remove-Item Env:\RC36_ENABLE_WORKER_FAULT_INJECTION -ErrorAction SilentlyContinue
    if ($hadDsn) { $env:RC36_ISOLATED_PG16_DSN = $oldDsn }
    if ($null -ne $oldDbUrl) { $env:DATABASE_URL = $oldDbUrl } else { Remove-Item Env:\DATABASE_URL -ErrorAction SilentlyContinue }
    if ($null -ne $oldPyPath) { $env:PYTHONPATH = $oldPyPath } else { Remove-Item Env:\PYTHONPATH -ErrorAction SilentlyContinue }
    if ($null -ne $oldWriteAck) { $env:RC36_ENABLE_ISOLATED_WRITES = $oldWriteAck }
    if ($null -ne $oldFaultAck) { $env:RC36_ENABLE_WORKER_FAULT_INJECTION = $oldFaultAck }
    if ($ptr -ne [IntPtr]::Zero) { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr) }
    if ($secure) { $secure.Dispose() }
    $plainDsn = $null
    try {
        $evidenceZip = Join-Path $root 'RC36_PG16_EVIDENCE.zip'
        if (Test-Path -LiteralPath $evidenceZip) { Remove-Item -LiteralPath $evidenceZip -Force }
        Compress-Archive -Path (Join-Path $out '*') -DestinationPath $evidenceZip -CompressionLevel Optimal -Force
        Write-Host ('EVIDENCE_BUNDLE=' + $evidenceZip)
    } catch {
        Write-Host ('EVIDENCE_BUNDLE=HOLD: ' + ([string]$_).Split([Environment]::NewLine)[0]) -ForegroundColor Yellow
    }
    Write-Host ''
    Write-Host ('LOCAL=' + $status.LOCAL)
    Write-Host ('BROWSER_MOCK=' + $status.BROWSER_MOCK)
    Write-Host ('PG16_READONLY=' + $status.PG16_READONLY)
    Write-Host ('PG16_BUSINESS=' + $status.PG16_BUSINESS)
    Write-Host ('PG16=' + $status.PG16)
    Write-Host ('RENDER=' + $status.RENDER)
    Write-Host ('GATE_STATUS=' + $statusPath)
}
exit $exitCode
