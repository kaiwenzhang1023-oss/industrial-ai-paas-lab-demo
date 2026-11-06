[CmdletBinding()]
param([string]$PythonExe='D:\Anaconda3\python.exe')
$ErrorActionPreference='Stop'
$root=Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -LiteralPath $root
if (-not (Test-Path -LiteralPath $PythonExe -PathType Leaf)) { throw "Python executable not found: $PythonExe" }
if (-not (Test-Path -LiteralPath '.\tests\live_business_workflow_gate_v4.py')) { throw 'V4 gate script missing. Extract the full V4 ZIP before running.' }
Write-Host 'RC34_LIVE_BROWSER_GATE=V4'
Write-Host 'TARGET=isolated Render RC3.4 candidate; one new guest tenant'
& $PythonExe (Join-Path $root 'tests\live_business_workflow_gate_v4.py')
$rc=$LASTEXITCODE
Write-Host ('LIVE_BUSINESS_EXIT='+$rc)
& $PythonExe (Join-Path $root 'RUN_RC34_FINAL_RELEASE_GATE_V4.py')
$finalEvidenceExit=$LASTEXITCODE
Write-Host ('V4_EVIDENCE_SUMMARY_EXIT='+$finalEvidenceExit)
Write-Host ('EVIDENCE='+(Join-Path $root 'release_evidence\live_business\RESULT.json'))
if ($rc -ne 0) { Write-Warning 'Live business gate HOLD/FAIL. Do not freeze. Return RESULT.json and FAIL_AT_STEP.png (if generated).' }
exit $rc
