@echo off
setlocal

cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo The local Python environment was not found.
    echo Run setup.bat first, then run this file again.
    echo.
    if not defined HFSS_EXPORTER_NO_PAUSE pause
    exit /b 1
)

echo.
echo === PyAEDT HFSS Exporter ===
echo.
echo Tip: Open your HFSS project before running this tool. To open a file explicitly, pass --project.
echo.

".venv\Scripts\python.exe" "%~dp0hfss_exporter.py" %*
set "EXIT_CODE=%ERRORLEVEL%"

echo.
if "%EXIT_CODE%"=="0" (
    echo Exporter finished.
) else (
    echo Exporter stopped with exit code %EXIT_CODE%.
)

echo.
if not defined HFSS_EXPORTER_NO_PAUSE pause
exit /b %EXIT_CODE%
