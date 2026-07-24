@echo off
echo ===================================================
echo     Instalador del Entorno para el CLI
echo ===================================================
echo.

:: 1. Verificar si Python ya esta instalado
python --version >nul 2>&1
IF %ERRORLEVEL% EQU 0 (
    echo [OK] Python ya esta instalado en el sistema.
    goto instalar_dependencias
)

:: 2. Si no esta, descargarlo via PowerShell
echo [!] Python no detectado. Descargando el instalador...
powershell -Command "Invoke-WebRequest -Uri 'https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe' -OutFile 'python_installer.exe'"

:: 3. Instalar silenciosamente y agregarlo al PATH
echo [!] Instalando Python de forma silenciosa (puede tardar unos minutos)...
start /wait python_installer.exe /quiet InstallAllUsers=0 PrependPath=1 Include_test=0
del python_installer.exe
echo [OK] Instalacion de Python completada.

:instalar_dependencias
echo.
echo ===================================================
echo [!] Instalando dependencias de requirements.txt...
:: Actualizamos pip primero para evitar advertencias
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

echo.
echo ===================================================
echo [OK] Todo listo! El entorno fue configurado.
echo ===================================================
pause