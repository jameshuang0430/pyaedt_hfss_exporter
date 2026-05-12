@echo off
setlocal

cd /d "%~dp0"

echo.
echo === PyAEDT HFSS Exporter Setup ===
echo.
echo This script will create a local Python environment in .venv
echo and install the packages listed in requirements.txt.
echo.

set "PY_CMD="

py -3 --version >nul 2>&1
if not errorlevel 1 set "PY_CMD=py -3"

if not defined PY_CMD (
    python --version >nul 2>&1
    if not errorlevel 1 set "PY_CMD=python"
)

if not defined PY_CMD (
    echo Python was not found.
    echo Please install Python 3.10 or newer from https://www.python.org/downloads/windows/
    echo During installation, select "Add python.exe to PATH", then run setup.bat again.
    goto fail
)

%PY_CMD% -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>&1
if errorlevel 1 (
    echo Python 3.10 or newer is required.
    echo Detected:
    %PY_CMD% --version
    goto fail
)

echo Python detected:
%PY_CMD% --version
echo.

if not exist "requirements.txt" (
    echo requirements.txt was not found in this folder.
    goto fail
)

if not exist ".venv\Scripts\python.exe" (
    echo Creating local Python environment...
    %PY_CMD% -m venv .venv
    if errorlevel 1 (
        echo Failed to create the local Python environment.
        goto fail
    )
) else (
    echo Existing .venv found. Reusing it.
)

echo.
echo Installing Python packages...
call ".venv\Scripts\activate.bat"
if errorlevel 1 (
    echo Failed to activate .venv.
    goto fail
)

python -m pip install --upgrade pip
if errorlevel 1 (
    echo Failed to upgrade pip.
    goto fail
)

python -m pip install -r requirements.txt
if errorlevel 1 (
    echo Failed to install Python packages.
    goto fail
)

echo.
echo Setup complete.
echo.
echo Next step:
echo   Double-click run_exporter.bat
echo.
echo Notes:
echo   - Ansys Electronics Desktop / HFSS must already be installed.
echo   - A valid AEDT/HFSS license is still required.
echo   - For best results, open your HFSS project before running the exporter.
goto done

:fail
echo.
echo Setup did not complete.
echo.
if not defined HFSS_EXPORTER_NO_PAUSE pause
exit /b 1

:done
if not defined HFSS_EXPORTER_NO_PAUSE pause
exit /b 0
