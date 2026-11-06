# Windows PowerShell 5.1; read-only live browser, no PG16 mutations.
[CmdletBinding()]
param([string]$PythonExe = 'D:\Anaconda3\python.exe')
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -LiteralPath $root
& $PythonExe (Join-Path $root 'tests\live_readonly_browser_gate.py')
$exitCode = $LASTEXITCODE
Write-Host ('LIVE_READONLY_BROWSER exit='+$exitCode)
Write-Host ('Evidence: '+(Join-Path $root 'release_evidence\live_readonly\RESULT.json'))
if ($exitCode -ne 0) { Write-Warning 'Live read-only browser gate HOLD/FAIL; inspect RESULT.json. No deployment was changed.' }
exit $exitCode
