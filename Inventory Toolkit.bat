@echo off
:: Fuerza la codificacion a UTF-8 para los iconos y ejecuta el script en PowerShell
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "[console]::InputEncoding = [console]::OutputEncoding = New-Object System.Text.UTF8Encoding; python cli.py"