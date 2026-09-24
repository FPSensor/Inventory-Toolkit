@echo off
cd /d "%~dp0"
:: Force UTF-8 for the console process
chcp 65001 > nul
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8

:: Prefer Windows Terminal; fall back to the classic command prompt
start wt.exe -d . python cli.py || python cli.py