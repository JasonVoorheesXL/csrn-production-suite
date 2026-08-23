@echo off
setlocal
cd /d "%~dp0"

echo CSRN Phase 3.2 - Roster Repository Integration
echo.
python tools\apply_phase_3_2.py app.py --check
if errorlevel 1 (
  echo.
  echo Validation failed. app.py was not changed.
  pause
  exit /b 1
)

echo.
choice /M "Apply Phase 3.2 to app.py and create a backup"
if errorlevel 2 exit /b 0

python tools\apply_phase_3_2.py app.py
if errorlevel 1 (
  echo.
  echo Integration failed. Review the error above.
  pause
  exit /b 1
)

echo.
echo Running syntax validation...
python -m py_compile app.py persistence_engine.py roster_repository.py
if errorlevel 1 (
  echo Syntax validation failed. Restore app.py.phase-3.2.bak before launching.
  pause
  exit /b 1
)

echo Running Phase 3.2 tests...
python -m pytest tests\test_roster_repository.py tests\test_phase_3_2_migrator.py
if errorlevel 1 (
  echo Phase 3.2 tests failed. Restore app.py.phase-3.2.bak before launching.
  pause
  exit /b 1
)

echo.
echo Phase 3.2 integration completed.
pause
