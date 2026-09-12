@echo off
setlocal

rem ============================================================
rem  CSRN Production Suite - desktop launcher
rem  Opens the real pywebview shell (csrn_desktop.py) against the
rem  production project checkout, using that project's own .venv
rem  Python - never a system-wide Python.
rem
rem  This wrapper lives on the Desktop, so the project path is
rem  absolute (not %~dp0). If you ever move the checkout, update
rem  the PROJECT_DIR line below.
rem ============================================================

set "PROJECT_DIR=%~dp0."
set "VENV_PY=%PROJECT_DIR%\.venv\Scripts\python.exe"

cd /d "%PROJECT_DIR%" || (
  echo Could not find the CSRN project folder:
  echo   %PROJECT_DIR%
  pause
  exit /b 1
)

if not exist "%VENV_PY%" (
  echo The CSRN Python environment is not installed at:
  echo   %VENV_PY%
  echo Run SETUP_CSRN_ENVIRONMENT.bat in the project folder once, then try again.
  pause
  exit /b 1
)

echo Starting CSRN Production Suite desktop shell...
echo   project: %PROJECT_DIR%
echo   python : %VENV_PY%
echo.
"%VENV_PY%" csrn_desktop.py
set "CSRN_EXIT=%ERRORLEVEL%"

if not "%CSRN_EXIT%"=="0" (
  echo.
  echo CSRN Production Suite exited with code %CSRN_EXIT%.
  pause
)
exit /b %CSRN_EXIT%
