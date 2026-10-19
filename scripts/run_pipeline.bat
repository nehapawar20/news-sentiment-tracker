@echo off
rem Runs the whole pipeline once. Used by Windows Task Scheduler.
set PYTHONUTF8=1
cd /d "%~dp0.."
if not exist logs mkdir logs
".venv\Scripts\python.exe" manage.py run_pipeline --enrich-limit 20 > logs\last_run.log 2>&1
exit /b %ERRORLEVEL%
