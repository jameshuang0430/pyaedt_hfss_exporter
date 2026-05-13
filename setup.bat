@echo off
setlocal

cd /d "%~dp0"

echo.
echo === PyAEDT HFSS Exporter Setup ===
echo.
echo This script will create a local Python environment in .venv
echo and install the packages listed in requirements.txt.
echo.

call :detect_supported_python

if not defined PY_CMD (
    echo A supported Python version was not found.
    echo Python 3.14 is not currently supported because pythonnet does not support it.
    echo.
    where winget >nul 2>&1
    if errorlevel 1 (
        echo winget was not found, so setup cannot install Python automatically.
        echo Please install Python 3.10 through 3.13 from https://www.python.org/downloads/windows/
        echo During installation, select "Add python.exe to PATH", then run setup.bat again.
        goto fail
    )

    echo Setup can install Python 3.13 automatically with winget.
    choice /C YN /N /M "Install Python 3.13 now? [Y/N] "
    if errorlevel 2 goto fail

    echo.
    echo Installing Python 3.13...
    winget install --id Python.Python.3.13 --source winget --scope user --accept-package-agreements --accept-source-agreements
    if errorlevel 1 (
        echo Failed to install Python 3.13 with winget.
        goto fail
    )

    echo.
    echo Detecting Python again...
    call :detect_supported_python
    if not defined PY_CMD (
        echo Python was installed, but setup still cannot find a supported Python command.
        echo Close this window, open a new Command Prompt, then run setup.bat again.
        goto fail
    )
)

%PY_CMD% -c "import sys; raise SystemExit(0 if (3, 10) <= sys.version_info[:2] < (3, 14) else 1)" >nul 2>&1
if errorlevel 1 (
    echo Python 3.10 through 3.13 is required. Python 3.14 is not currently supported because pythonnet does not support it.
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

if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" -c "import sys; raise SystemExit(0 if (3, 10) <= sys.version_info[:2] < (3, 14) else 1)" >nul 2>&1
    if errorlevel 1 (
        echo Existing .venv uses an unsupported Python version. Recreating local Python environment...
        rmdir /s /q ".venv"
        if exist ".venv" (
            echo Failed to remove the existing .venv folder.
            goto fail
        )
    )
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

:detect_supported_python
set "PY_CMD="

py -3.10 --version >nul 2>&1
if not errorlevel 1 set "PY_CMD=py -3.10"

if not defined PY_CMD (
    py -3.13 --version >nul 2>&1
    if not errorlevel 1 set "PY_CMD=py -3.13"
)

if not defined PY_CMD (
    py -3.12 --version >nul 2>&1
    if not errorlevel 1 set "PY_CMD=py -3.12"
)

if not defined PY_CMD (
    py -3.11 --version >nul 2>&1
    if not errorlevel 1 set "PY_CMD=py -3.11"
)

if not defined PY_CMD (
    python -c "import sys; raise SystemExit(0 if (3, 10) <= sys.version_info[:2] < (3, 14) else 1)" >nul 2>&1
    if not errorlevel 1 set "PY_CMD=python"
)

exit /b 0
