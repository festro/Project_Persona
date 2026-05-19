@echo off
setlocal enabledelayedexpansion

REM ============================================================
REM  Project_Persona portable Windows setup (Stage 1)
REM  Downloads PortableGit, then hands off to bash for the rest.
REM  Requires Windows 10 1803+ (for curl.exe).
REM ============================================================

set "ROOT=%~dp0"
if "%ROOT:~-1%"=="\" set "ROOT=%ROOT:~0,-1%"

set "PORTABLE=%ROOT%\portable"
set "PG_DIR=%PORTABLE%\PortableGit"
set "PG_EXE=%PORTABLE%\PortableGit-installer.7z.exe"

echo ============================================================
echo  Project_Persona portable Windows setup
echo  Root: %ROOT%
echo ============================================================
echo.

REM ---- Pre-flight ------------------------------------------------
where curl.exe >NUL 2>&1
if errorlevel 1 (
    echo ERROR: curl.exe not found. Windows 10 1803+ ships it natively.
    pause
    exit /b 1
)
where powershell.exe >NUL 2>&1
if errorlevel 1 (
    echo ERROR: powershell.exe not found.
    pause
    exit /b 1
)

if not exist "%PORTABLE%" mkdir "%PORTABLE%"

REM ---- Step 1: PortableGit --------------------------------------
if exist "%PG_DIR%\bin\bash.exe" (
    echo [1/3] [SKIP] PortableGit already present at:
    echo       %PG_DIR%
    goto :stage2
)

REM Manual override: if you pre-dropped the installer, skip the API call.
if exist "%PG_EXE%" (
    echo [1/3] [PREDOWNLOADED] Using existing %PG_EXE%
    goto :extract
)

echo [1/3] Resolving latest PortableGit release URL via GitHub API...

REM Use PowerShell's .Where() method instead of '|' to avoid cmd-pipe-escape issues.
set "PG_URL="
for /f "usebackq delims=" %%U in (`powershell -NoProfile -ExecutionPolicy Bypass -Command "$ErrorActionPreference='Stop'; $ProgressPreference='SilentlyContinue'; try { [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; $r = Invoke-RestMethod -Uri 'https://api.github.com/repos/git-for-windows/git/releases/latest' -Headers @{ 'User-Agent' = 'Project_Persona-portable-setup' }; $a = $r.assets.Where({ $_.name -like 'PortableGit-*-64-bit.7z.exe' }); if ($a.Count -gt 0) { Write-Output $a[0].browser_download_url } } catch { Write-Error $_.Exception.Message }"`) do set "PG_URL=%%U"

REM Trim accidental whitespace/CR.
if defined PG_URL set "PG_URL=!PG_URL: =!"

REM Validate: must start with https://
echo !PG_URL!| findstr /b "https://" >NUL
if errorlevel 1 (
    echo ERROR: could not resolve PortableGit download URL from GitHub API.
    echo        Got: "!PG_URL!"
    echo.
    echo Possible causes:
    echo   - No internet, or api.github.com rate-limited from your IP ^(60/hr unauth^)
    echo   - PowerShell execution policy blocked the call
    echo   - TLS 1.2 not negotiated
    echo.
    echo Manual fallback:
    echo   1^) Browse to https://github.com/git-for-windows/git/releases/latest
    echo   2^) Download the asset named "PortableGit-X.Y.Z-64-bit.7z.exe"
    echo   3^) Save it as: %PG_EXE%
    echo   4^) Re-run windows_portable_setup.bat
    pause
    exit /b 1
)

echo       URL: !PG_URL!
echo       Downloading (about 55 MB)...
curl.exe -L --fail --progress-bar -o "%PG_EXE%" "!PG_URL!"
if errorlevel 1 (
    echo ERROR: PortableGit download failed.
    pause
    exit /b 1
)

:extract
echo       Extracting silently to %PG_DIR%
"%PG_EXE%" -y -o"%PG_DIR%" -bso0 -bsp0 -bsm0 >NUL
if errorlevel 1 (
    echo ERROR: PortableGit extraction failed.
    pause
    exit /b 1
)
del "%PG_EXE%" >NUL 2>&1

if not exist "%PG_DIR%\bin\bash.exe" (
    echo ERROR: bash.exe still missing after extraction.
    pause
    exit /b 1
)
echo       PortableGit ready: %PG_DIR%\bin\bash.exe

:stage2
echo.
echo [2/3] [3/3] Handing off to portable bash for
echo       llama.cpp + Qwen3.6 model downloads...
echo.

"%PG_DIR%\bin\bash.exe" "%ROOT%\scripts\portable_setup_win.sh"
if errorlevel 1 (
    echo.
    echo ERROR: portable_setup_win.sh failed. See output above.
    pause
    exit /b 1
)

echo.
echo ============================================================
echo  SETUP COMPLETE
echo  Launch with: windows_portable_run.bat (double-click)
echo ============================================================
echo.
pause
