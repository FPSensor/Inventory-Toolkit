@echo off
cd /d "%~dp0"
echo ===================================================
echo     Inventory Toolkit CLI environment setup
echo ===================================================
echo.

:: 1. Check whether Python is already installed
python --version >nul 2>&1
IF %ERRORLEVEL% EQU 0 (
    echo [OK] Python is already installed on this system.
    goto install_dependencies
)

:: 2. If missing, download the installer through PowerShell
echo [!] Python was not detected. Downloading the installer...
powershell -Command "Invoke-WebRequest -Uri 'https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe' -OutFile 'python_installer.exe'"

:: 3. Install silently and add Python to PATH
echo [!] Installing Python silently (this may take a few minutes)...
start /wait python_installer.exe /quiet InstallAllUsers=0 PrependPath=1 Include_test=0
del python_installer.exe
echo [OK] Python installation completed.

:install_dependencies
echo.
echo ===================================================
echo [!] Installing dependencies from requirements.txt...
:: Upgrade pip before installing dependencies
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

echo.
echo ===================================================
echo [OK] Environment setup completed.
echo ===================================================
pause