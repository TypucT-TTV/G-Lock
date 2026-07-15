@echo off
setlocal

net session >nul 2>&1
if %errorLevel% neq 0 (
    echo Requesting administrative privileges...
    set "GLOCK_LAUNCHER=%~f0"
    powershell.exe -NoProfile -Command "Start-Process -FilePath $env:GLOCK_LAUNCHER -Verb RunAs"
    exit /b
)

cd /d "%~dp0"

where npm >nul 2>&1
if errorlevel 1 (
    echo ERROR: npm was not found in PATH.
    echo Install the current Node.js LTS release and reopen this terminal.
    pause
    exit /b 1
)

if not exist "node_modules" (
    echo Installing frontend dependencies...
    call npm ci
    if errorlevel 1 goto :error
)

call npm run tauri dev
if errorlevel 1 goto :error
exit /b 0

:error
echo.
echo G-Lock exited with an error. Review the output above.
pause
exit /b 1
