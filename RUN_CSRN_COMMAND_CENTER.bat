@echo off
setlocal
cd /d "%~dp0"

where py >nul 2>&1
if errorlevel 1 (
  echo Python was not found.
  echo Install Python 3 from https://www.python.org/downloads/windows/
  echo During installation, check "Add python.exe to PATH".
  pause
  exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
  echo Creating local Python environment...
  py -3 -m venv .venv
  if errorlevel 1 (
    echo Failed to create the local Python environment.
    pause
    exit /b 1
  )
)

echo Updating installer tools...
".venv\Scripts\python.exe" -m pip install --disable-pip-version-check -q --upgrade pip setuptools wheel
if errorlevel 1 (
  echo Failed to update Python installer tools.
  pause
  exit /b 1
)

echo Installing required packages...
".venv\Scripts\python.exe" -m pip install --disable-pip-version-check -q -r requirements.txt
if errorlevel 1 (
  echo.
  echo Required package installation failed. The application was not started.
  echo Delete the .venv folder and run this launcher again after correcting the error.
  pause
  exit /b 1
)

echo Starting CSRN Production Suite - Command Center...
".venv\Scripts\python.exe" app.py
pause
