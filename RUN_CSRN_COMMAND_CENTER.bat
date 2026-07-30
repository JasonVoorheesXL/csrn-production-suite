@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  echo The CSRN Python environment is not installed.
  echo Run SETUP_CSRN_ENVIRONMENT.bat once, then start Command Center again.
  pause
  exit /b 1
)

echo Verifying the offline CSRN runtime environment...
".venv\Scripts\python.exe" tools\environment_check.py --profile runtime
if errorlevel 1 (
  echo.
  echo The CSRN environment is missing, stale, or incompatible.
  echo Run SETUP_CSRN_ENVIRONMENT.bat, then start Command Center again.
  pause
  exit /b 1
)

echo Running game-day storage preflight and safety snapshot...
".venv\Scripts\python.exe" tools\game_day_preflight.py
if errorlevel 1 (
  echo.
  echo Game-day preflight failed. The application was not started.
  echo Correct the reported storage or data problem and run this launcher again.
  pause
  exit /b 1
)

echo Recording game-day application startup...
".venv\Scripts\python.exe" tools\game_day_recovery.py startup
if errorlevel 1 (
  echo.
  echo Recovery startup tracking failed. The application was not started.
  pause
  exit /b 1
)

echo.
echo Starting CSRN Production Suite - Command Center...
".venv\Scripts\python.exe" app.py
set "CSRN_EXIT=%ERRORLEVEL%"
if "%CSRN_EXIT%"=="0" (
  echo Recording clean application shutdown...
  ".venv\Scripts\python.exe" tools\game_day_recovery.py shutdown
) else (
  echo.
  echo WARNING: CSRN ended unexpectedly. The recovery marker was retained.
)
pause
exit /b %CSRN_EXIT%
