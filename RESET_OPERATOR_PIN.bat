@echo off
setlocal
cd /d "%~dp0"
echo This will remove the operator PIN from this local installation.
choice /M "Continue"
if errorlevel 2 exit /b 0
if exist security.json del /q security.json
echo PIN removed. Restart the Command Center to create a new PIN.
pause
