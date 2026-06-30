<#
  Fetch a static FFmpeg build into tools/ffmpeg/ (gitignored, host-provided).

  FFmpeg is invoked only as a SEPARATE PROCESS (subprocess) by the playspace media
  player -- never linked or imported -- so its GPL/LGPL terms do not propagate into
  this AGPL repo (the same boundary used for Piper). It lets the media player handle
  formats Godot can't decode natively (FLAC, and non-Theora video) by transcoding to
  WAV / Ogg on demand.

    .\fetch_ffmpeg.ps1          # download + extract if missing
    .\fetch_ffmpeg.ps1 -Force   # re-download
#>
param([switch]$Force)

$Root = (Resolve-Path "$PSScriptRoot\..").Path        # repo root (script lives in clients/)
$dir  = Join-Path $Root "tools\ffmpeg"
$exe  = Join-Path $dir "ffmpeg.exe"

if ((Test-Path $exe) -and -not $Force) {
  Write-Host "have ffmpeg: $exe"
  & $exe -version | Select-Object -First 1
  return
}

New-Item -ItemType Directory -Force -Path $dir | Out-Null
$zip = Join-Path $env:TEMP "ffmpeg_dl.zip"
$url = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
Write-Host "downloading $url ..."
Invoke-WebRequest -Uri $url -OutFile $zip -UseBasicParsing

$tmp = Join-Path $env:TEMP "ffmpeg_extract"
if (Test-Path $tmp) { Remove-Item -Recurse -Force $tmp }
Expand-Archive -Path $zip -DestinationPath $tmp -Force

$bin = Get-ChildItem -Path $tmp -Recurse -Filter "ffmpeg.exe" | Select-Object -First 1
if ($null -eq $bin) { throw "ffmpeg.exe not found in the downloaded archive" }
Copy-Item $bin.FullName $exe -Force
$probe = Join-Path $bin.DirectoryName "ffprobe.exe"
if (Test-Path $probe) { Copy-Item $probe (Join-Path $dir "ffprobe.exe") -Force }

Remove-Item -Recurse -Force $tmp
Remove-Item -Force $zip
Write-Host "installed: $exe"
& $exe -version | Select-Object -First 1
