@echo off
setlocal
cd /d "%~dp0"

echo CSRN Phase 2.4 - Production Repository Integration
echo.
python tools\apply_phase_2_4.py app.py --check
if errorlevel 1 (
  echo.
  echo Validation failed. app.py was not changed.
  pause
  exit /b 1
)

echo.
choice /M "Apply Phase 2.4 to app.py and create a backup"
if errorlevel 2 exit /b 0

python tools\apply_phase_2_4.py app.py
if errorlevel 1 (
  echo.
  echo Integration failed. Review the error above.
  pause
  exit /b 1
)

echo.
echo Running syntax validation...
python -m py_compile app.py persistence_engine.py core_repositories.py
if errorlevel 1 (
  echo Syntax validation failed. Restore app.py.phase-2.4.bak before launching.
  pause
  exit /b 1
)

echo Phase 2.4 integration completed.
pause
