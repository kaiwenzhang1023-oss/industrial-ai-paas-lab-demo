# Backward-compatible entrypoint: delegates to the consolidated PowerShell 5.1 gate.
[CmdletBinding()]
param(
    [string]$PythonExe = '',
    [switch]$RunIsolatedPG16,
    [switch]$RunLiveBrowser
)
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$args = @('-NoProfile','-ExecutionPolicy','Bypass','-File',(Join-Path $root 'RUN_RC34_ENTERPRISE_ONE_SHOT.ps1'))
if ($PythonExe) { $args += @('-PythonExe',$PythonExe) }
if ($RunIsolatedPG16) { $args += '-RunIsolatedPG16' }
if ($RunLiveBrowser) { $args += '-RunLiveBrowser' }
& powershell.exe @args
exit $LASTEXITCODE
