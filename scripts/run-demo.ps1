param(
  [int]$Port = 8080
)

$ErrorActionPreference = 'Stop'
$Repo = Split-Path -Parent $PSScriptRoot
Set-Location $Repo
New-Item -ItemType Directory -Force -Path (Join-Path $Repo '.dev') | Out-Null

$env:GTP_DEMO = '1'
$env:GTP_PORT = "$Port"
$env:GTP_BIND = '127.0.0.1'
$env:GTP_CONFIG = (Join-Path $Repo '.dev\config.json')

$Python = $null
if (Get-Command python -ErrorAction SilentlyContinue) { $Python = @('python') }
elseif (Get-Command py -ErrorAction SilentlyContinue) { $Python = @('py','-3') }
else { throw 'Python 3 was not found on PATH. Install Python 3 and reopen VS Code.' }

$Url = "http://127.0.0.1:$Port/"
Write-Host "GPS Time demo: $Url"
Write-Host 'Sample data is enabled. Demo settings are saved under .dev/. Open /app/ (/ redirects there).'
Start-Job -ScriptBlock { param($u) Start-Sleep -Milliseconds 700; Start-Process $u } -ArgumentList $Url | Out-Null

if ($Python.Count -eq 1) { & $Python[0] -m gps_time_pi.server }
else { & $Python[0] $Python[1] -m gps_time_pi.server }
