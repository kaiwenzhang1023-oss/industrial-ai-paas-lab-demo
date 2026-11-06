# RC3.6 Windows browser gate. Isolated Python 3.14 venv; no browser policy bypass.
[CmdletBinding()]
param([string]$PythonExe = '')
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -LiteralPath $root
$out = Join-Path $root 'release_evidence\rc36'
New-Item -ItemType Directory -Path $out -Force | Out-Null
$log = Join-Path $out 'WINDOWS_BROWSER.log'
$status = Join-Path $out 'BROWSER_STATUS.txt'
"BROWSER=HOLD: not yet executed" | Set-Content -LiteralPath $status -Encoding UTF8
function Write-Gate([string]$Message) { $Message | Tee-Object -FilePath $log -Append | Out-Host }
function Invoke-Checked([string]$Exe, [string[]]$Arguments, [string]$Step) {
  Write-Gate "STEP=$Step"
  & $Exe @Arguments 2>&1 | Tee-Object -FilePath $log -Append | Out-Host
  if ($LASTEXITCODE -ne 0) { throw "$Step failed with exit code $LASTEXITCODE" }
}
try {
  if ($PythonExe) {
    if (-not (Test-Path -LiteralPath $PythonExe)) { throw "PythonExe not found: $PythonExe" }
    $baseExe = (Resolve-Path -LiteralPath $PythonExe).Path
    $baseArgs = @()
  } else {
    $launcher = Get-Command py.exe -ErrorAction SilentlyContinue
    if ($launcher) {
      $baseExe = $launcher.Source
      $baseArgs = @('-3.14')
    } else {
      $candidates = @(
        (Join-Path $env:USERPROFILE 'anaconda3\python.exe'),
        (Join-Path $env:USERPROFILE 'miniconda3\python.exe'),
        'C:\ProgramData\anaconda3\python.exe'
      )
      $baseExe = $null
      foreach ($candidate in $candidates) {
        if (Test-Path -LiteralPath $candidate) {
          $v = & $candidate -c 'import sys; print(sys.version_info.major, sys.version_info.minor, sep=chr(46))' 2>$null
          if ($v -eq '3.14') { $baseExe = $candidate; break }
        }
      }
      if (-not $baseExe) { throw 'Python 3.14 not found. Re-run with -PythonExe "C:\full\path\to\python.exe".' }
      $baseArgs = @()
    }
  }
  $version = & $baseExe @baseArgs -c 'import sys; print(sys.version_info.major, sys.version_info.minor, sep=chr(46))'
  if ($LASTEXITCODE -ne 0 -or $version -ne '3.14') { throw "RC3.6 requires Python 3.14, detected: $version" }
  Write-Gate "PYTHON_BASE=$baseExe; VERSION=$version"
  $venv = Join-Path $root '.rc36-browser-venv'
  $venvPython = Join-Path $venv 'Scripts\python.exe'
  if (-not (Test-Path -LiteralPath $venvPython)) {
    Invoke-Checked $baseExe ($baseArgs + @('-m','venv',$venv)) 'CREATE_ISOLATED_VENV'
  }
  Invoke-Checked $venvPython @('-m','pip','install','--disable-pip-version-check','pytest>=9,<10','playwright>=1.55,<2') 'INSTALL_BROWSER_TEST_DEPENDENCIES'
  Invoke-Checked $venvPython @('-m','playwright','install','chromium') 'INSTALL_PLAYWRIGHT_CHROMIUM'
  $env:PYTHONPATH = $root + ';' + (Join-Path $root 'backend')
  $env:RC36_BROWSER_EVIDENCE = $out
  Write-Gate 'BROWSER_TEST_START: mocked API only, NOT PostgreSQL E2E'
  & $venvPython -m pytest -v -s 'browser_gate\browser_mock_gate.py' 2>&1 | Tee-Object -FilePath $log -Append | Out-Host
  if ($LASTEXITCODE -ne 0) { throw "Browser tests failed with exit code $LASTEXITCODE" }
  'BROWSER_MOCK=PASS; PG16_E2E=HOLD; RENDER=HOLD' | Set-Content -LiteralPath $status -Encoding UTF8
  Write-Gate 'BROWSER_MOCK=PASS (mocked API, not PG16 E2E)'
} catch {
  $reason = $_.Exception.Message
  if ($reason -match 'ERR_BLOCKED_BY_ADMINISTRATOR|URLBlocklist|policy') {
    "BROWSER=ENVIRONMENT_BLOCKED / HOLD: $reason" | Set-Content -LiteralPath $status -Encoding UTF8
  } else {
    "BROWSER=HOLD/FAIL: $reason" | Set-Content -LiteralPath $status -Encoding UTF8
  }
  Write-Gate "BROWSER_GATE_STOPPED: $reason"
  throw
} finally {
  Remove-Item Env:\PYTHONPATH -ErrorAction SilentlyContinue
  Remove-Item Env:\RC36_BROWSER_EVIDENCE -ErrorAction SilentlyContinue
}
