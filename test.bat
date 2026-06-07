@echo off
set "ROOT=%~dp0"
if "%ROOT:~-1%"=="\" set "ROOT=%ROOT:~0,-1%"
set "PY=%ROOT%\portable\python\python.exe"
if not exist "%PY%" set "PY=python"
"%PY%" "%ROOT%\manage.py" test %*
