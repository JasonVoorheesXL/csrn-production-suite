@echo off
cd /d "%~dp0"
del /q INSTALL_VERSION_1_7*.txt 2>nul
del /q INSTALL_VERSION_1_8.txt 2>nul
echo Legacy installation-note files removed.
pause
