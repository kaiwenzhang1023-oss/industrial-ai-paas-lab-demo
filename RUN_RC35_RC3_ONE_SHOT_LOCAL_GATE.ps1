param([string]$Python = 'python')
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root
$env:PYTHONPATH = (Join-Path $root 'backend') + [IO.Path]::PathSeparator + $root
$log = Join-Path $root 'RC35_RC3_LOCAL_GATE.log'
"RC3.5 RC3 LOCAL GATE - $(Get-Date -Format o)" | Out-File -FilePath $log -Encoding UTF8
& $Python -m compileall -q enterprise_workbench backend tests 2>&1 | Out-File -FilePath $log -Append -Encoding UTF8
if ($LASTEXITCODE -ne 0) { throw 'PYTHON_COMPILE_FAILED' }
& $Python -m pytest -q tests 2>&1 | Out-File -FilePath $log -Append -Encoding UTF8
if ($LASTEXITCODE -ne 0) { throw 'PYTEST_FAILED - inspect RC35_RC3_LOCAL_GATE.log' }
foreach ($f in @('app.js','enterprise-console.js','engine.js')) {
  & node --check (Join-Path $root "enterprise_workbench/site/$f") 2>&1 | Out-File -FilePath $log -Append -Encoding UTF8
  if ($LASTEXITCODE -ne 0) { throw "NODE_SYNTAX_FAILED $f" }
}
Write-Host 'RC35_RC3_LOCAL_GATE PASS (PG16 and browser/cloud gates NOT included)'
