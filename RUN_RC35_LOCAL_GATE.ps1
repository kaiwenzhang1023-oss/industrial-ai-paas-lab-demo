param([string]$PythonExe = "D:\Anaconda3\python.exe")
$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root
if (-not (Test-Path $PythonExe)) { throw "Python executable not found: $PythonExe" }
$ver = & $PythonExe -c "import sys; print('.'.join(map(str,sys.version_info[:2])))"
if ($LASTEXITCODE -ne 0 -or $ver.Trim() -ne '3.14') { throw "Python 3.14 required; detected $ver" }
Write-Host 'PYTHON_VERSION=PASS'
& $PythonExe -m compileall -q backend enterprise_workbench preview_cloud g3 g4 tests
if ($LASTEXITCODE -ne 0) { throw 'PYTHON_COMPILE=FAIL' }
Write-Host 'PYTHON_COMPILE=PASS'
$Node = Get-Command node -ErrorAction SilentlyContinue
if (-not $Node) { throw 'Node.js is required for JavaScript syntax validation' }
& node --check enterprise_workbench/site/app.js
if ($LASTEXITCODE -ne 0) { throw 'APP_JS_SYNTAX=FAIL' }
& node --check enterprise_workbench/site/enterprise-console.js
if ($LASTEXITCODE -ne 0) { throw 'ENTERPRISE_JS_SYNTAX=FAIL' }
Write-Host 'NODE_JS_SYNTAX=PASS'
& $PythonExe -m pytest -q
if ($LASTEXITCODE -ne 0) { throw 'PYTEST=FAIL' }
Write-Host 'PYTEST=PASS'
Write-Host 'RC35_LOCAL_GATE=PASS'
Write-Host 'NOTE=Local offline checks only; PG16 and cloud browser gates remain separate.'
