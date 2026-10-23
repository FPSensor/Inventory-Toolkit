@echo off
cd /d "%~dp0"
:: Force UTF-8 for the console process
chcp 65001 > nul
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8

:: The build manifest selects the interface without importing the other frontend.
python -m inventory_toolkit %*
