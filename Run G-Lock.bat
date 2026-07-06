@echo off
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo Requesting administrative privileges...
    powershell -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
    exit /b
)

setlocal
cd /d "%~dp0"


set "POETRY_EXE=C:\Users\typuctttv\AppData\Roaming\Python\Python311\Scripts\poetry.exe"

if not exist "%POETRY_EXE%" (
    echo ERROR: poetry.exe not found at "%POETRY_EXE%".
    echo Reinstall it with: py -3.11 -m pip install --user poetry
    pause
    exit /b 1
)

"%POETRY_EXE%" install
if errorlevel 1 (
    echo ERROR: poetry install failed. See the output above.
    pause
    exit /b 1
)

"%POETRY_EXE%" run python g_lock
set EXITCODE=%ERRORLEVEL%

echo.
if not "%EXITCODE%"=="0" (
    echo G-Lock exited with an error (code %EXITCODE%). See the output above.
)
pause
endlocal
