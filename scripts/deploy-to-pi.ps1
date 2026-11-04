# Build the Pi bundle, upload it, verify it on the Pi, install. Stops at the
# first failure (review GPS-021). In Windows PowerShell 5.1,
# $ErrorActionPreference = 'Stop' does not stop on a native command's non-zero
# exit, so every python/scp/ssh call goes through Invoke-Native, which checks
# $LASTEXITCODE. A failed build never uploads an old archive, and install.sh
# never runs on an archive whose SHA-256 doesn't match.
param(
  [Parameter(Mandatory=$true)][string]$PiHost,
  [string]$PiUser = 'pi'
)
$ErrorActionPreference = 'Stop'

# install.sh's optional flags (docs/deploy/sdr-stack.md, websdr.md; the chrony steps), taken from
# this shell's environment and passed to `sudo env ... bash install.sh` on the Pi:
#   $env:GTP_WEBSDR = '1'; .\scripts\deploy-to-pi.ps1 -PiHost ...
# Only these names are passed (tests/test_deploy_scripts.py keeps the list in step with install.sh).
# Values reach a remote shell, so they are checked first: letters, digits, space and . _ : , / -
# only. A bad value stops the deploy before anything is built or uploaded.
$InstallFlags = @(
  'GTP_INDEPENDENT_REFS',
  'GTP_NODE',
  'GTP_NODE_STATION',
  'GTP_KEEP_DHCP_NTP',
  'GTP_SDR',
  'GTP_SDR_1090_SERIAL',
  'GTP_SDR_978_SERIAL',
  'GTP_SDR_NODE',
  'GTP_SDR_PPS_SERIAL',
  'GTP_WEBSDR',
  'GTP_WEBSDR_MAX_HOURS',
  'GTP_WEBSDR_PORT',
  'GTP_WEBSDR_SERIAL'
)
$FlagValue = '^[A-Za-z0-9 ._:,/-]{1,200}$'
$Assign = New-Object System.Collections.Generic.List[string]
foreach ($Name in $InstallFlags) {
  $Value = [Environment]::GetEnvironmentVariable($Name)
  if ([string]::IsNullOrEmpty($Value)) { continue }
  if ($Value -cnotmatch $FlagValue) {
    throw "$Name has characters an install flag can't have (letters, digits, space and . _ : , / - only); deploy stopped, nothing built or uploaded."
  }
  $Assign.Add("$Name='$Value'")
}
$Ignored = @(Get-ChildItem env: | Where-Object { $_.Name -like 'GTP_*' -and $_.Name -ne 'GTP_DEPLOY_TTY' -and $InstallFlags -notcontains $_.Name } | ForEach-Object { $_.Name })
if ($Ignored.Count) { Write-Host "Not passed to install.sh (not install flags): $($Ignored -join ', ')" }
$Install = 'sudo bash install.sh'
if ($Assign.Count) {
  $Install = "sudo env $($Assign -join ' ') bash install.sh"
  Write-Host "Install flags passed to the Pi: $($Assign -join ' ')"
}

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
$RemoteCmd = "set -e; cd ~/$RemoteDir && echo '$Sha  gps-time-pi-deploy.tar.gz' | sha256sum -c - && tar -xzf gps-time-pi-deploy.tar.gz && cd gps-time && $Install"
# Build the argument list element by element. An `if` expression unwraps a
# one-element array to a string, and string + array concatenates into ONE
# argument ("-tuser@host ..."), which ssh then reads as a run of flags.
$SshArgs = New-Object System.Collections.Generic.List[string]
if ($UseTty) { $SshArgs.Add('-t') }
$SshArgs.Add($Remote)
$SshArgs.Add($RemoteCmd)
Invoke-Native ssh $SshArgs.ToArray()
Write-Host "Open http://$PiHost/"
