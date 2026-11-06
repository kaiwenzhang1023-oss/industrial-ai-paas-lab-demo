<#
Publish ONLY a new UX candidate branch from the frozen RC2 commit.
PowerShell 5.1+, Git for Windows. This does not require an existing local .git.
It NEVER pushes to main or v19-version-b-preview and does not touch Render/Neon.
Run after extracting the FULL SOURCE ZIP, from any PowerShell working directory:
  powershell.exe -NoProfile -ExecutionPolicy Bypass -File "<EXTRACTED_ROOT>\RUN_PUBLISH_UX_RC31_CANDIDATE.ps1"
#>
[CmdletBinding()]
param(
 [string]$Remote = 'https://github.com/kaiwenzhang1023-oss/industrial-ai-paas-lab.git',
 [string]$BaselineBranch = 'v19-version-b-preview',
 [string]$CandidateBranch = 'v19-version-b-enterprise-ux-rc31-candidate'
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$Expected = 'ea20d05f24f9d641442339dcff3d1b48e063d091'
$SourceRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$Repo = Join-Path $env:TEMP ('v19b_uxrc31_' + [guid]::NewGuid().ToString('N'))
$Allowed = @(
 'enterprise_workbench/site/index.html',
 'enterprise_workbench/site/enterprise-console.js',
 'enterprise_workbench/site/enterprise-console.css',
 'tests/browser_enterprise_rc3.py',
 'README_ENTERPRISE_CONSOLE_RC3.md'
)
if (-not (Get-Command git -ErrorAction SilentlyContinue)) { throw 'HOLD_GIT_NOT_INSTALLED' }
if (-not (Test-Path -LiteralPath (Join-Path $SourceRoot 'enterprise_workbench\site\enterprise-console.js'))) { throw 'HOLD_EXTRACTED_SOURCE_ROOT_NOT_FOUND' }
if ($Remote -notmatch '^https://github\.com/kaiwenzhang1023-oss/industrial-ai-paas-lab\.git$') { throw 'HOLD_UNEXPECTED_REPOSITORY' }
if ($CandidateBranch -eq $BaselineBranch -or $CandidateBranch -eq 'main') { throw 'HOLD_REF_NOT_ISOLATED' }
if ($CandidateBranch -notmatch '^v19-version-b-enterprise-ux-rc31-candidate$') { throw 'HOLD_UNEXPECTED_CANDIDATE_BRANCH' }
New-Item -ItemType Directory -Path $Repo -Force | Out-Null
Write-Host 'PHASE 1/4: Clone frozen RC2 branch in an isolated TEMP directory...' -ForegroundColor Cyan
& git clone --no-tags --depth 1 --single-branch --branch $BaselineBranch $Remote $Repo
if ($LASTEXITCODE -ne 0) { throw 'HOLD_BASELINE_CLONE_FAILED' }
$Actual = @(& git -C $Repo rev-parse HEAD)[0]
if ($LASTEXITCODE -ne 0 -or $Actual.Trim() -ne $Expected) { throw ('HOLD_BASELINE_COMMIT_MISMATCH ' + $Actual) }
$Current = @(& git -C $Repo status --porcelain)
if ($LASTEXITCODE -ne 0 -or $Current.Count -ne 0) { throw 'HOLD_BASELINE_NOT_CLEAN' }
& git -C $Repo ls-remote --exit-code --heads origin $CandidateBranch 2>$null | Out-Null
if ($LASTEXITCODE -eq 0) { throw 'HOLD_CANDIDATE_BRANCH_ALREADY_EXISTS' }
if ($LASTEXITCODE -ne 2) { throw 'HOLD_REMOTE_BRANCH_CHECK_FAILED' }
Write-Host 'PHASE 2/4: Apply the UX-only whitelist to a new candidate branch...' -ForegroundColor Cyan
& git -C $Repo switch -c $CandidateBranch
if ($LASTEXITCODE -ne 0) { throw 'HOLD_LOCAL_BRANCH_CREATION_FAILED' }
foreach($Rel in $Allowed){
  $Src = Join-Path $SourceRoot ($Rel.Replace('/','\'))
  $Dst = Join-Path $Repo ($Rel.Replace('/','\'))
  if (-not (Test-Path -LiteralPath $Src -PathType Leaf)) { throw ('HOLD_CANDIDATE_FILE_MISSING: ' + $Rel) }
  $DstFolder = Split-Path -Parent $Dst
  if (-not (Test-Path -LiteralPath $DstFolder)) { New-Item -ItemType Directory -Path $DstFolder -Force | Out-Null }
  Copy-Item -LiteralPath $Src -Destination $Dst -Force
}
& git -C $Repo add -- $Allowed
if ($LASTEXITCODE -ne 0) { throw 'HOLD_GIT_STAGE_FAILED' }
$Staged = @(& git -C $Repo diff --cached --name-only)
if ($LASTEXITCODE -ne 0 -or $Staged.Count -lt 3) { throw 'HOLD_CANDIDATE_STAGING_INCOMPLETE' }
foreach($Path in $Staged){if($Allowed -notcontains $Path){throw ('HOLD_NON_UX_FILE_STAGED ' + $Path)}}
$UserName = (& git -C $Repo config user.name | Out-String).Trim()
$UserEmail = (& git -C $Repo config user.email | Out-String).Trim()
if (-not $UserName -or -not $UserEmail) {
  Write-Host 'Missing Git commit identity; GitHub sign-in is separate from commit metadata.' -ForegroundColor Yellow
  if (-not $UserName) { $UserName = Read-Host 'Git commit display name' }
  if (-not $UserEmail) { $UserEmail = Read-Host 'Git commit email (existing verified GitHub email)' }
  if (-not $UserName -or -not $UserEmail) { throw 'HOLD_GIT_COMMIT_IDENTITY_REQUIRED' }
}
Write-Host 'PHASE 3/4: Commit isolated UX files without altering the RC2 baseline...' -ForegroundColor Cyan
& git -C $Repo -c "user.name=$UserName" -c "user.email=$UserEmail" commit -m 'Version B enterprise console UX RC3.1 candidate; preserve frozen RC2 backend'
if ($LASTEXITCODE -ne 0) { throw 'HOLD_CANDIDATE_COMMIT_FAILED' }
Write-Host 'PHASE 4/4: Push NEW branch only; no force and no changes to frozen branch...' -ForegroundColor Cyan
& git -C $Repo push -u origin "HEAD:refs/heads/$CandidateBranch"
if ($LASTEXITCODE -ne 0) { throw 'HOLD_GITHUB_PUSH_FAILED' }
$Sha = @(& git -C $Repo rev-parse HEAD)[0]
Write-Host ('CANDIDATE_BRANCH=' + $CandidateBranch)
Write-Host ('CANDIDATE_COMMIT=' + $Sha)
Write-Host ('CANDIDATE_URL=https://github.com/kaiwenzhang1023-oss/industrial-ai-paas-lab/tree/' + $CandidateBranch)
Write-Host 'V19B_RC31_CANDIDATE_PUBLISH=PASS' -ForegroundColor Green
