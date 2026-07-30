@echo off
setlocal
cd /d "%~dp0"

where py >nul 2>&1
if errorlevel 1 (
  echo Python Launcher for Windows was not found.
  echo Install Python 3.13 from https://www.python.org/downloads/windows/
  pause
  exit /b 1
)

py -3.13 tools\setup_environment.py --profile runtime
if errorlevel 1 (
  echo.
  echo CSRN runtime environment setup did not complete.
  pause
  exit /b 1
)

echo.
echo CSRN runtime environment setup is complete.
pause
