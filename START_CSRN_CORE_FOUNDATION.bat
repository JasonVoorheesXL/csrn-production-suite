@echo off
setlocal
cd /d "%~dp0"

echo.
echo CSRN Production Suite v1.13 Foundation
echo Core repository runtime integration
echo.

where py >nul 2>nul
if %errorlevel%==0 (
    py -3 run_core_foundation.py
) else (
    python run_core_foundation.py
)

if errorlevel 1 (
    echo.
    echo CSRN did not start successfully.
    echo Review the error shown above.
    pause
)

endlocal
