#requires -Version 5
[CmdletBinding()]
param(
  [switch]$CoreOnly,
  [switch]$Run
)

function Invoke-Native {
  param([Parameter(Mandatory)][string]$File, [string[]]$Arguments)
  & $File @Arguments
  if ($LASTEXITCODE -ne 0) { throw "Command failed (exit $LASTEXITCODE): $File $($Arguments -join ' ')" }
}

$RepoRoot = Split-Path -Parent $PSScriptRoot
$PyDir = Join-Path $RepoRoot "portable\python"
$Py = Join-Path $PyDir "python.exe"

if (-not (Test-Path $Py)) { throw "python.exe not found at $Py" }
Write-Host "==> Interpreter: $Py"
& $Py --version

$pth = Get-ChildItem -Path $PyDir -Filter "python*._pth" | Select-Object -First 1
if ($null -eq $pth) { throw "No python*._pth found in $PyDir" }
$content = Get-Content $pth.FullName
$patched = $content -replace '^\s*#\s*import\s+site\s*$', 'import site'
if (-not ($patched -contains 'import site')) { $patched += 'import site' }
Set-Content -Path $pth.FullName -Value $patched -Encoding ASCII
Write-Host "==> Enabled 'import site' in $($pth.Name)"

& $Py -m pip --version 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) {
  $getpip = Join-Path $env:TEMP "get-pip.py"
  Write-Host "==> Bootstrapping pip via get-pip.py"
  Invoke-WebRequest -Uri "https://bootstrap.pypa.io/get-pip.py" -OutFile $getpip -ErrorAction Stop
  Invoke-Native -File $Py -Arguments @($getpip)
} else {
  Write-Host "==> pip already present"
}

Invoke-Native -File $Py -Arguments @("-m","pip","install","--upgrade","pip","wheel","setuptools<82")

if ($CoreOnly) {
  Write-Host "==> Installing core API deps only (no RAG)"
  Invoke-Native -File $Py -Arguments @("-m","pip","install","fastapi>=0.110.0,<1.0.0","uvicorn[standard]>=0.29.0,<1.0.0","pydantic>=2.7.0,<3.0.0","httpx>=0.27.0,<1.0.0","tenacity>=8.0.0,<9.0.0")
} else {
  $reqs = Join-Path $RepoRoot "services\api\requirements.txt"
  Write-Host "==> Installing full stack requirements: $reqs"
  Invoke-Native -File $Py -Arguments @("-m","pip","install","-r",$reqs)
}

Write-Host "==> Core import smoke test"
Invoke-Native -File $Py -Arguments @("-c","import fastapi, uvicorn, pydantic, httpx, tenacity; print('core imports OK; pydantic', pydantic.VERSION)")

if ($Run) {
  $env:AI_ROOT = $RepoRoot
  $env:PERSONA_ROOT = Join-Path $RepoRoot "persona"
  $env:PROFILES_DIR = Join-Path $RepoRoot "persona\profiles"
  $env:GLOBAL_MEMORY_DIR = Join-Path $RepoRoot "persona\global_memory"
  foreach ($ef in @("run\llama-servers.env","run\config.env")) {
    $efp = Join-Path $RepoRoot $ef
    if (Test-Path $efp) {
      Write-Host "==> Loading $ef"
      Get-Content $efp | ForEach-Object {
        if ($_ -match '^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$') {
          Set-Item -Path ("Env:" + $matches[1]) -Value $matches[2].Trim()
        }
      }
    }
  }
  Write-Host "==> Launching API on http://127.0.0.1:8000 (Ctrl-C to stop)"
  & $Py -m uvicorn "server:app" --app-dir (Join-Path $RepoRoot "services\api") --host 127.0.0.1 --port 8000
} else {
  Write-Host "==> Done. To launch the API:  .\scripts\bootstrap_portable_python.bat -Run"
}
