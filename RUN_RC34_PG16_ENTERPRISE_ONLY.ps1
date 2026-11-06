# Windows PowerShell 5.1/11. Runs ONLY the isolated Neon PG16 enterprise gate.
# It does not deploy, migrate, create containers/branches, or touch frozen RC2.
[CmdletBinding()]
param([string]$PythonExe = 'D:\Anaconda3\python.exe')
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -LiteralPath $root

if (-not (Test-Path -LiteralPath $PythonExe)) {
    throw "Python executable not found: $PythonExe. Supply the Python 3.14 executable path."
}
$version = & $PythonExe -c 'import sys; print("%d.%d" % sys.version_info[:2])'
if ($LASTEXITCODE -ne 0 -or $version -ne '3.14') {
    throw 'Python 3.14 is required. Do not use Python 3.10.'
}
& $PythonExe -c 'import fastapi, httpx, psycopg; print("DEPENDENCIES=PASS")'
if ($LASTEXITCODE -ne 0) {
    throw 'Missing Python dependency. Install/repair psycopg[binary], fastapi and httpx in this Python 3.14 environment, then rerun.'
}
$node = Get-Command node -ErrorAction SilentlyContinue
if (-not $node) { throw 'Node.js is required for independent native Version A RC8 comparison. Install/use the existing Node.js runtime; no download is started by this script.' }

$hadDsn = Test-Path Env:\V19B_RC34_ISOLATED_TEST_DATABASE_URL
$oldDsn = $env:V19B_RC34_ISOLATED_TEST_DATABASE_URL
$secure = $null
$bstr = [IntPtr]::Zero
try {
    if (-not $env:V19B_RC34_ISOLATED_TEST_DATABASE_URL) {
        Write-Host ''
        Write-Host '请从 Neon Console 复制现有隔离分支的连接字符串。输入会隐藏，不会写入日志或证据。' -ForegroundColor Cyan
        Write-Host '目标必须是 branch: v19b-ux-rc31-isolated-acceptance / database: industrial_v19b_preview。' -ForegroundColor Cyan
        $secure = Read-Host 'Neon 隔离 PG16 connection string（隐藏输入）' -AsSecureString
        $bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
        $env:V19B_RC34_ISOLATED_TEST_DATABASE_URL = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr)
    }
    Write-Host ''
    Write-Host '本门禁只会在 endpoint ep-twilight-violet-bb8pm1v6 上创建唯一测试租户和 MRP 记录。' -ForegroundColor Yellow
    Write-Host '不会运行迁移、TRUNCATE、DELETE，不会修改 mock_erp/mock_wms，不会访问冻结 RC2。' -ForegroundColor Yellow
    $confirm = Read-Host '确认仅对上述隔离 Neon 分支执行 PG16 集成测试？输入 RUN_ISOLATED_PG16_TESTS 继续'
    if ($confirm -cne 'RUN_ISOLATED_PG16_TESTS') {
        Write-Host '用户未确认，已退出；没有连接或写入数据库。' -ForegroundColor Yellow
        $gateCode = 2
    } else {
        $env:V19B_RC34_ENABLE_ISOLATED_MUTATIONS = 'YES'
        $env:PGCONNECT_TIMEOUT = '15'
        & $PythonExe (Join-Path $root 'tests\enterprise_pg16_gate.py')
        $gateCode = $LASTEXITCODE
        Write-Host ''
        Write-Host ('RC34_ENTERPRISE_PG16_EXIT=' + $gateCode)
        Write-Host ('EVIDENCE=' + (Join-Path $root 'release_evidence\pg16_enterprise\RESULT.json'))
        Write-Host 'What-if before/after evidence: release_evidence\pg16_enterprise\WHAT_IF_*_BEFORE.json / WHAT_IF_*_AFTER.json'
        if ($gateCode -ne 0) {
            Write-Warning 'PG16 gate is HOLD/FAIL. Do not freeze or deploy as final release; send RESULT.json and sanitized error details.'
        }
    }
}
finally {
    Remove-Item Env:\V19B_RC34_ENABLE_ISOLATED_MUTATIONS -ErrorAction SilentlyContinue
    Remove-Item Env:\PGCONNECT_TIMEOUT -ErrorAction SilentlyContinue
    if ($hadDsn) { $env:V19B_RC34_ISOLATED_TEST_DATABASE_URL = $oldDsn }
    else { Remove-Item Env:\V19B_RC34_ISOLATED_TEST_DATABASE_URL -ErrorAction SilentlyContinue }
    if ($bstr -ne [IntPtr]::Zero) { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr) }
    if ($secure) { $secure.Dispose() }
}

if ($null -eq $gateCode) { $gateCode = 2 }
exit $gateCode
