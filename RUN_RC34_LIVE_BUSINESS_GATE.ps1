[CmdletBinding()]
param([string]$PythonExe='D:\Anaconda3\python.exe')
$ErrorActionPreference='Stop'
$root=Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -LiteralPath $root
& $PythonExe (Join-Path $root 'tests\live_business_workflow_gate.py')
$exitCode=$LASTEXITCODE
Write-Host ('LIVE_BUSINESS_GATE exit='+$exitCode)
Write-Host ('Evidence: '+(Join-Path $root 'release_evidence\live_business\RESULT.json'))
if ($exitCode -ne 0) { Write-Warning 'HOLD/FAIL: do not deploy or freeze; inspect evidence.' }
exit $exitCode
