# Build the Pi bundle, upload it, verify it on the Pi, install. Stops at the
# first failure (review GPS-021). In Windows PowerShell 5.1,
# $ErrorActionPreference = 'Stop' does not stop on a native command's non-zero
# exit, so every python/scp/ssh call goes through Invoke-Native, which checks
# $LASTEXITCODE. A failed build never uploads an old archive, and install.sh
# never runs on an archive whose SHA-256 doesn't match.
param(
  [Parameter(Mandatory=$true)][string]$PiHost,
  [string]$PiUser = 'pi',
  [switch]$UseDemoLayout
)
$ErrorActionPreference = 'Stop'

function Invoke-Native {
  param([Parameter(Mandatory=$true)][string]$Exe, [string[]]$Arguments = @())
  & $Exe @Arguments
  if ($LASTEXITCODE -ne 0) { throw "$Exe failed (exit $LASTEXITCODE); deploy stopped." }
}

$Repo = Split-Path -Parent $PSScriptRoot
Set-Location $Repo
$Archive = Join-Path $Repo 'dist\gps-time-pi-deploy.tar.gz'
$Remote = "$PiUser@$PiHost"
# Upload into a fresh directory in the remote user's home, not a fixed /tmp name.
$RemoteDir = 'gps-time-deploy'

if ($UseDemoLayout) { Invoke-Native python @('tools/promote_dashboard.py') }
if (Test-Path $Archive) { Remove-Item $Archive -Force }
# The bundle ships the built web UI (/app/). Build it from this checkout;
# build_bundles.py refuses a web/dist built from another version.
Push-Location (Join-Path $Repo 'web')
try {
  Invoke-Native corepack @('pnpm', 'install', '--frozen-lockfile')
  Invoke-Native corepack @('pnpm', 'run', 'build')
} finally { Pop-Location }
Invoke-Native python @('tools/build_bundles.py')
if (-not (Test-Path $Archive) -or (Get-Item $Archive).Length -eq 0) { throw "Build did not produce $Archive; deploy stopped." }
$Sha = (Get-FileHash -Algorithm SHA256 $Archive).Hash.ToLowerInvariant()
Write-Host "Built $Archive (SHA-256 $Sha)"

Write-Host "Uploading to $Remote ..."
Invoke-Native ssh @($Remote, "rm -rf ~/$RemoteDir && mkdir -m 0700 ~/$RemoteDir")
Invoke-Native scp @($Archive, "${Remote}:$RemoteDir/gps-time-pi-deploy.tar.gz")

# A remote terminal only when this console is interactive: sudo can then
# prompt, and install.sh shows the admin token on the terminal only, so
# redirected output never captures it. Without one, sudo must not need a password.
# GTP_DEPLOY_TTY=1 or 0 overrides the detection (the tests use it).
$UseTty = -not ([Console]::IsInputRedirected -or [Console]::IsOutputRedirected)
if ($env:GTP_DEPLOY_TTY -eq '1') { $UseTty = $true } elseif ($env:GTP_DEPLOY_TTY -eq '0') { $UseTty = $false }
Write-Host 'Verifying the upload and installing on the Raspberry Pi ...'
$RemoteCmd = "set -e; cd ~/$RemoteDir && echo '$Sha  gps-time-pi-deploy.tar.gz' | sha256sum -c - && tar -xzf gps-time-pi-deploy.tar.gz && cd gps-time && sudo bash install.sh"
# Build the argument list element by element. An `if` expression unwraps a
# one-element array to a string, and string + array concatenates into ONE
# argument ("-tuser@host ..."), which ssh then reads as a run of flags.
$SshArgs = New-Object System.Collections.Generic.List[string]
if ($UseTty) { $SshArgs.Add('-t') }
$SshArgs.Add($Remote)
$SshArgs.Add($RemoteCmd)
Invoke-Native ssh $SshArgs.ToArray()
Write-Host "Open http://$PiHost/"
