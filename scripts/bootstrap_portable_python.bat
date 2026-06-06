@echo off
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0bootstrap_portable_python.ps1" %*
