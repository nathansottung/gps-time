@echo off
setlocal
cd /d "%~dp0\.."
if not exist .dev mkdir .dev
set GTP_DEMO=1
set GTP_PORT=8080
set GTP_BIND=127.0.0.1
set GTP_CONFIG=%CD%\.dev\config.json
set GTP_DASHBOARD_CONFIG=%CD%\.dev\dashboard.json
start "GPS Time Demo" http://127.0.0.1:8080/
where python >nul 2>nul && python -m gps_time_pi.server && goto :eof
where py >nul 2>nul && py -3 -m gps_time_pi.server && goto :eof
echo Python 3 was not found on PATH.
exit /b 1
