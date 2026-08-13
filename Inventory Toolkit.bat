@echo off
:: Fuerza el uso de UTF-8 en el proceso de la consola
chcp 65001 > nul
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8

:: Intenta lanzar Windows Terminal (la consola moderna), si falla, cae en el cmd clásico
start wt.exe -d . python cli.py || python cli.py