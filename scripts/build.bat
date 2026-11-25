@echo off
setlocal
cd /d "%~dp0.."

if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" scripts\build_deploy.py %*
) else (
    python scripts\build_deploy.py %*
)
endlocal
