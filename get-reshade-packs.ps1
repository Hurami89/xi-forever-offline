# Downloads the ReShade shader packs your preset uses straight from GitHub and puts each one where ReShade.ini expects it:
#   <loader folder>\reshade-shaders\Shaders\<Pack>   (and ...\Textures\<Pack> when a pack has textures)
# Close the game first. Needs internet. Safe to run again (it only adds and replaces files inside the pack folders).
# Run:  cd C:\FFXISOLO ; Set-ExecutionPolicy -Scope Process Bypass ; .\get-reshade-packs.ps1
$ErrorActionPreference = "Continue"
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
$cfg  = Get-Content "$PSScriptRoot\config.json" | ConvertFrom-Json
$boot = Join-Path $cfg.ashita_dir "bootloader"
if (-not (Test-Path $boot)) { throw "Loader folder not found: $boot" }
$shaders  = Join-Path $boot "reshade-shaders\Shaders"
$textures = Join-Path $boot "reshade-shaders\Textures"
New-Item -ItemType Directory -Force $shaders, $textures | Out-Null
$work = Join-Path $env:TEMP "reshade-packs"
Remove-Item -Recurse -Force $work -ErrorAction SilentlyContinue
New-Item -ItemType Directory $work | Out-Null

# folder name in ReShade.ini  ->  GitHub owner/repo and the branches to try
$packs = [ordered]@{
  "qUINT"        = @("martymcmodding/qUINT", "master", "main")
  "PD80"         = @("prod80/prod80-ReShade-Repository", "master", "main")
  "Depth3D"      = @("BlueSkyDefender/Depth3D", "master", "main")
  "AstrayFX"     = @("BlueSkyDefender/AstrayFX", "master", "main")
  "OtisFX"       = @("Otis-Inf/OtisFX", "master", "main")
  "FGFX"         = @("AlexTuduran/FGFX", "main", "master")
  "brussell"     = @("brussell1/Shaders", "master", "main")
  "Daodan"       = @("Daodan317081/reshade-shaders", "master", "main")
  "Fubax"        = @("Fubaxiusz/fubax-shaders", "master", "main")
  "luluco250"    = @("luluco250/FXShaders", "master", "main")
  "RSRetroArch"  = @("Matsilagi/RSRetroArch", "main", "master")
  "CorgiFX"      = @("originalnicoder/CorgiFX", "main", "master")
  "Radegast"     = @("Radegast-FFXIV/Radegast-ReShade-Shaders", "main", "master")
  "CobraFX"      = @("LordKobra/CobraFX", "master", "main")
  "VRToolkit"    = @("retroluxfilm/reshade-vrtoolkit", "master", "main")
}
# "Insane-Shaders" is in your settings too, but I do not know its GitHub page, so it is not downloaded here.

$ok = @(); $failed = @(); $withTextures = @()

# The packs need ReShade's own header files (ReShade.fxh). If they are missing, fetch ReShade's standard shader set first.
if (-not (Test-Path (Join-Path $shaders "ReShade.fxh"))) {
  Write-Host "  ReShade.fxh is missing - fetching ReShade's standard shaders first..."
  try {
    $zip = Join-Path $work "standard.zip"
    Invoke-WebRequest -UseBasicParsing -Uri "https://github.com/crosire/reshade-shaders/archive/refs/heads/slim.zip" -OutFile $zip -ErrorAction Stop
    $dest = Join-Path $work "standard-x"
    Expand-Archive -Path $zip -DestinationPath $dest -Force
    $root = Get-ChildItem $dest -Directory | Select-Object -First 1
    Copy-Item -Path (Join-Path $root.FullName "Shaders\*") -Destination $shaders -Recurse -Force
    if (Test-Path (Join-Path $root.FullName "Textures")) { Copy-Item -Path (Join-Path $root.FullName "Textures\*") -Destination $textures -Recurse -Force }
    Write-Host "  ok      standard shaders" -ForegroundColor Green
  } catch { Write-Host "  FAILED  standard shaders: $($_.Exception.Message)" -ForegroundColor Red }
}

foreach ($name in $packs.Keys) {
  $repo = $packs[$name][0]; $branches = $packs[$name][1..2]
  $zip = Join-Path $work "$name.zip"; $got = $false; $lastError = ""
  foreach ($branch in $branches) {
    try {
      Invoke-WebRequest -UseBasicParsing -Uri "https://github.com/$repo/archive/refs/heads/$branch.zip" -OutFile $zip -ErrorAction Stop
      $got = $true; break
    } catch { $lastError = $_.Exception.Message }
  }
  if (-not $got) { Write-Host "  FAILED  $name ($repo): $lastError" -ForegroundColor Red; $failed += $name; continue }

  $dest = Join-Path $work "$name-x"
  Expand-Archive -Path $zip -DestinationPath $dest -Force
  $root = Get-ChildItem $dest -Directory | Select-Object -First 1
  if (-not $root) { Write-Host "  FAILED  $name (empty download)" -ForegroundColor Red; $failed += $name; continue }

  # the shader files: a 'Shaders' folder in the repo, or else the whole repo
  $srcShaders = Get-ChildItem $root.FullName -Directory -Recurse -Depth 1 -Filter "Shaders" | Select-Object -First 1
  $srcFolder = if ($srcShaders) { $srcShaders.FullName } else { $root.FullName }
  $target = Join-Path $shaders $name
  New-Item -ItemType Directory -Force $target | Out-Null
  Copy-Item -Path (Join-Path $srcFolder "*") -Destination $target -Recurse -Force
  $count = @(Get-ChildItem $target -Recurse -Include *.fx, *.fxh -ErrorAction SilentlyContinue).Count

  $srcTextures = Get-ChildItem $root.FullName -Directory -Recurse -Depth 1 -Filter "Textures" | Select-Object -First 1
  if ($srcTextures) {
    $tt = Join-Path $textures $name
    New-Item -ItemType Directory -Force $tt | Out-Null
    Copy-Item -Path (Join-Path $srcTextures.FullName "*") -Destination $tt -Recurse -Force
    $withTextures += $name
  }
  Write-Host "  ok      $name  ($count shader files)" -ForegroundColor Green
  $ok += $name
}

# Make sure ReShade.ini looks in every pack folder (a backup is saved first)
$ini = Join-Path $boot "ReShade.ini"
if (Test-Path $ini) {
  if (-not (Test-Path "$ini.before-packs")) { Copy-Item $ini "$ini.before-packs" }
  $lines = Get-Content $ini
  for ($i = 0; $i -lt $lines.Count; $i++) {
    if ($lines[$i] -match '^EffectSearchPaths=(.*)$') {
      $have = $Matches[1] -split ','
      foreach ($n in $ok) { $p = ".\reshade-shaders\Shaders\$n"; if ($have -notcontains $p) { $have += $p } }
      $lines[$i] = "EffectSearchPaths=" + (($have | Where-Object { $_ }) -join ",")
    }
    if ($lines[$i] -match '^TextureSearchPaths=(.*)$') {
      $have = $Matches[1] -split ','
      foreach ($n in $withTextures) { $p = ".\reshade-shaders\Textures\$n"; if ($have -notcontains $p) { $have += $p } }
      $lines[$i] = "TextureSearchPaths=" + (($have | Where-Object { $_ }) -join ",")
    }
  }
  Set-Content $ini $lines
}

Write-Host ""
Write-Host "Installed $($ok.Count) of $($packs.Count) packs: $($ok -join ', ')" -ForegroundColor Cyan
if ($failed.Count) { Write-Host "Failed: $($failed -join ', ')  (copy the red lines above into the chat)" -ForegroundColor Yellow }
Write-Host "Next: open the launcher's SHADERS page and press 'Check shaders', then start the game."
