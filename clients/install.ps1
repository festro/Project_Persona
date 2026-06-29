<#
  Project_Persona -- Windows client installer (Phase 4 + Phase 5).

  Fetches the host-provided engines and models this box needs to act as a voice +
  avatar CLIENT to the EVO-X2 persona API:
    - Whisper.cpp (STT)      -> tools\whisper\   (gitignored)
    - Piper (TTS, GPL-3.0)   -> tools\piper\     (gitignored, used as a separate process)
    - Godot 4 (avatar)       -> tools\godot\     (gitignored)
    - ggml-base.en (STT)     -> models\          (gitignored)
    - en_US-lessac-medium    -> models\          (gitignored)

  Idempotent: each item is skipped if already present. Re-run with -Force to refetch.
  Pinned versions live below so a re-install is reproducible.
#>
param([switch]$Force)

$ErrorActionPreference = "Stop"
$Root  = (Resolve-Path "$PSScriptRoot\..").Path
$Tools = Join-Path $Root "tools"
$Models = Join-Path $Root "models"
$Tmp   = Join-Path $env:TEMP "persona_client_dl"
New-Item -ItemType Directory -Force -Path $Tools, $Models, $Tmp | Out-Null

# -- pinned sources --------------------------------------------------------
$WHISPER_ZIP = "https://github.com/ggml-org/whisper.cpp/releases/download/v1.9.1/whisper-bin-x64.zip"
$PIPER_ZIP   = "https://github.com/rhasspy/piper/releases/download/2023.11.14-2/piper_windows_amd64.zip"
$GODOT_ZIP   = "https://github.com/godotengine/godot/releases/download/4.7-stable/Godot_v4.7-stable_win64.exe.zip"
$WHISPER_MODEL = "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-base.en.bin"
$WHISPER_MODEL_ALT = "https://huggingface.co/ggml-org/whisper.cpp/resolve/main/ggml-base.en.bin"
$PIPER_ONNX  = "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/en_US-lessac-medium.onnx"
$PIPER_JSON  = "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/en_US-lessac-medium.onnx.json"

function Fetch($url, $dest, $alt = $null) {
  if ((Test-Path $dest) -and -not $Force) { Write-Host "  skip (exists): $dest"; return }
  Write-Host "  GET $url"
  & curl.exe -fL --retry 3 --retry-delay 2 -o $dest $url
  if (($LASTEXITCODE -ne 0 -or -not (Test-Path $dest)) -and $alt) {
    Write-Host "  retry alt: $alt"
    & curl.exe -fL --retry 3 -o $dest $alt
  }
  if (-not (Test-Path $dest)) { throw "download failed: $url" }
}

function Unzip($zip, $dst) {
  Write-Host "  unzip -> $dst"
  Expand-Archive -Path $zip -DestinationPath $dst -Force
}

Write-Host "[1/3] Whisper.cpp (STT)"
if ($Force -or -not (Test-Path "$Tools\whisper\Release\whisper-cli.exe")) {
  Fetch $WHISPER_ZIP "$Tmp\whisper.zip"; Unzip "$Tmp\whisper.zip" "$Tools\whisper"
} else { Write-Host "  skip (exists): whisper-cli.exe" }
Fetch $WHISPER_MODEL "$Models\ggml-base.en.bin" $WHISPER_MODEL_ALT

Write-Host "[2/3] Piper (TTS) + Godot (avatar)"
if ($Force -or -not (Test-Path "$Tools\piper\piper\piper.exe")) {
  Fetch $PIPER_ZIP "$Tmp\piper.zip"; Unzip "$Tmp\piper.zip" "$Tools\piper"
} else { Write-Host "  skip (exists): piper.exe" }
Fetch $PIPER_ONNX "$Models\en_US-lessac-medium.onnx"
Fetch $PIPER_JSON "$Models\en_US-lessac-medium.onnx.json"
if ($Force -or -not (Test-Path "$Tools\godot\Godot_v4.7-stable_win64.exe")) {
  Fetch $GODOT_ZIP "$Tmp\godot.zip"; Unzip "$Tmp\godot.zip" "$Tools\godot"
} else { Write-Host "  skip (exists): Godot_v4.7-stable_win64.exe" }

Write-Host "[3/3] Verify"
$py = Join-Path $Root "portable\python\python.exe"
if (-not (Test-Path $py)) { $py = "python" }
& $py (Join-Path $PSScriptRoot "voice\persona_voice.py") selftest --no-play

Write-Host ""
Write-Host "Done. Next:"
Write-Host "  Voice : clients\voice\run_voice.ps1 say ""Hello from Project Persona"""
Write-Host "  Voice : clients\voice\run_voice.ps1 listen        (needs: pip install sounddevice)"
Write-Host "  Avatar: clients\godot\run_avatar.ps1              (-Editor to open the Godot editor)"
