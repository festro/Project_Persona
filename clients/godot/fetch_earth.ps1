<#
  Fetch NASA Blue Marble / Black Marble imagery for the playspace Earth.
  Public domain (NASA Visible Earth). Downloaded into clients/godot/assets/earth/
  (gitignored -- host-provided, not committed); playspace.gd loads them at runtime
  (Image.load) so no editor import step is needed. If a texture is missing the
  Earth shader falls back to its procedural look.

    .\fetch_earth.ps1          # download any missing textures
    .\fetch_earth.ps1 -Force   # re-download all
#>
param([switch]$Force)

$dir = Join-Path $PSScriptRoot "assets\earth"
New-Item -ItemType Directory -Force -Path $dir | Out-Null

$assets = @(
  @{ name = "earth_day.jpg";    url = "https://eoimages.gsfc.nasa.gov/images/imagerecords/73000/73909/world.topo.bathy.200412.3x5400x2700.jpg" },
  @{ name = "earth_clouds.jpg"; url = "https://eoimages.gsfc.nasa.gov/images/imagerecords/57000/57747/cloud_combined_2048.jpg" },
  @{ name = "earth_night.jpg";  url = "https://eoimages.gsfc.nasa.gov/images/imagerecords/79000/79765/dnb_land_ocean_ice.2012.3600x1800.jpg" }
)

foreach ($a in $assets) {
  $path = Join-Path $dir $a.name
  if ((Test-Path $path) -and -not $Force) { Write-Host "have   $($a.name)"; continue }
  Write-Host "fetch  $($a.name) ..."
  Invoke-WebRequest -Uri $a.url -OutFile $path -UseBasicParsing
}
Write-Host "Earth textures in $dir"
