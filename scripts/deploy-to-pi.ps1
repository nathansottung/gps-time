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
$TtyOpt = if ([Console]::IsInputRedirected -or [Console]::IsOutputRedirected) { @() } else { @('-t') }
Write-Host 'Verifying the upload and installing on the Raspberry Pi ...'
$RemoteCmd = "set -e; cd ~/$RemoteDir && echo '$Sha  gps-time-pi-deploy.tar.gz' | sha256sum -c - && tar -xzf gps-time-pi-deploy.tar.gz && cd gps-time && sudo bash install.sh"
Invoke-Native ssh ($TtyOpt + @($Remote, $RemoteCmd))
Write-Host "Open http://$PiHost/"
