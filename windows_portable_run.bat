@echo off
setlocal

REM Project_Persona portable Windows launcher.
REM Thin OS doorknob only: find the bundled Python and hand off to manage.py.
REM All lifecycle logic lives in manage.py (cross-platform). No bash required.

set "ROOT=%~dp0"
if "%ROOT:~-1%"=="\" set "ROOT=%ROOT:~0,-1%"
set "PY=%ROOT%\portable\python\python.exe"

if not exist "%PY%" (
    echo ERROR: bundled Python not found at %PY%
    echo Run windows_portable_setup.bat first.
    pause
    exit /b 1
)

"%PY%" "%ROOT%\manage.py" up
echo.
echo Stack launched via manage.py. To stop:  "%PY%" "%ROOT%\manage.py" down
echo Status:  "%PY%" "%ROOT%\manage.py" status
pause
