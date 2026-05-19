@echo off
setlocal enabledelayedexpansion

REM ============================================================
REM  Project_Persona portable Windows launcher
REM  Uses portable PortableGit for this session only; no system
REM  PATH modifications survive after this window closes.
REM ============================================================

set "ROOT=%~dp0"
if "%ROOT:~-1%"=="\" set "ROOT=%ROOT:~0,-1%"

set "PG_DIR=%ROOT%\portable\PortableGit"

if not exist "%PG_DIR%\bin\bash.exe" (
    echo ERROR: PortableGit not found at %PG_DIR%.
    echo Run windows_portable_setup.bat first.
    pause
    exit /b 1
)

REM Session-scoped PATH only.
set "PATH=%PG_DIR%\bin;%PG_DIR%\usr\bin;%PG_DIR%\mingw64\bin;%PATH%"

REM Convert D:\Projects\Git\Project_Persona to /D/Projects/Git/Project_Persona
REM Pure-cmd path translation — no cygpath subprocess, no quote-escape headaches.
REM (Git Bash on case-insensitive Windows treats /D/ and /d/ identically.)
set "BASH_ROOT=/%ROOT::=%"
set "BASH_ROOT=!BASH_ROOT:\=/!"

echo ============================================================
echo  Launching llama-server (portable Windows mode)
echo  Project root (Win):   %ROOT%
echo  Project root (POSIX): !BASH_ROOT!
echo ============================================================
echo.

"%PG_DIR%\bin\bash.exe" -lc "export AI_ROOT='!BASH_ROOT!'; cd '!BASH_ROOT!' && chmod +x scripts/start_llama_server_win.sh && ./scripts/start_llama_server_win.sh"

echo.
echo ============================================================
echo  Launcher returned. llama-server may still be running in the
echo  background (check run/persona_win.pid).
echo  Stop it via:
echo    "%PG_DIR%\bin\bash.exe" -lc "kill \$(cat !BASH_ROOT!/run/persona_win.pid)"
echo  Or just kill the llama-server.exe process via Task Manager.
echo ============================================================
echo.
pause
