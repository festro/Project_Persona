<#
  Launch the Project_Persona playspace -- the starship-bridge 3D scene (Phase 4,
  flatscreen + XR-ready). Separate from run_avatar.ps1 (the 2D STATE-driven face);
  the avatar lands on the command deck in a later pass.

    .\run_playspace.ps1            run the playspace (flatscreen, mouse-look)
    .\run_playspace.ps1 -Editor    open the Godot project in the editor
    .\run_playspace.ps1 -Shot out.png   render one frame to PNG, then quit (proof path)

  Controls: WASD move, mouse look, Shift sprint, Space/Ctrl up/down, Esc frees the cursor.
#>
param(
  [switch]$Editor,
  [string]$Shot = ""
)

$godot = Join-Path $PSScriptRoot "..\..\tools\godot\Godot_v4.7-stable_win64.exe"
if (-not (Test-Path $godot)) { throw "Godot not found at $godot -- run clients\install.ps1 first" }

if ($Editor) {
  & $godot -e --path $PSScriptRoot
} elseif ($Shot -ne "") {
  $env:PERSONA_PLAYSPACE_SHOT = $Shot
  & $godot --path $PSScriptRoot res://playspace.tscn
} else {
  & $godot --path $PSScriptRoot res://playspace.tscn
}
