<#
  Launch the Project_Persona avatar client.
    .\run_avatar.ps1            run the avatar app (connects to the EVO-X2 API)
    .\run_avatar.ps1 -Editor    open the project in the Godot editor

  Override the target API with $env:PERSONA_API (default http://192.168.8.114:8000).
#>
param([switch]$Editor)

$Root  = (Resolve-Path "$PSScriptRoot\..\..").Path
$godot = Join-Path $Root "tools\godot\Godot_v4.7-stable_win64.exe"
if (-not (Test-Path $godot)) { throw "Godot not found at $godot -- run clients\install.ps1 first" }

if ($Editor) {
  & $godot -e --path $PSScriptRoot
} else {
  & $godot --path $PSScriptRoot
}
