param(
  [Parameter(Mandatory=$true)][string]$PiHost,
  [string]$PiUser = 'pi',
  [switch]$UseDemoLayout
)
$ErrorActionPreference = 'Stop'
$Repo = Split-Path -Parent $PSScriptRoot
Set-Location $Repo
if ($UseDemoLayout) { python tools/promote_dashboard.py }
python tools/build_bundles.py
$Archive = Join-Path $Repo 'dist\gps-time-pi-deploy.tar.gz'
$Remote = "$PiUser@$PiHost"
Write-Host "Uploading to $Remote ..."
scp $Archive "${Remote}:/tmp/gps-time-pi-deploy.tar.gz"
Write-Host 'Installing on Raspberry Pi (sudo will prompt remotely if required)...'
ssh $Remote "rm -rf ~/gps-time-deploy && mkdir -p ~/gps-time-deploy && tar -xzf /tmp/gps-time-pi-deploy.tar.gz -C ~/gps-time-deploy && cd ~/gps-time-deploy/gps-time && sudo bash install.sh"
Write-Host "Open http://$PiHost/"
