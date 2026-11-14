# Copies the Era-DATs into your FFXI game folder, after backing up every file it replaces.
# Run in an ADMINISTRATOR PowerShell from the kit folder:  .\install-era-dats.ps1
$ErrorActionPreference = "Stop"
$cfg    = Get-Content "$PSScriptRoot\config.json" | ConvertFrom-Json
$src    = $cfg.era_dats_dir
$game   = $cfg.ffxi_client_dir
$backup = Join-Path $PSScriptRoot "dat-backup"
$manifest = Join-Path $PSScriptRoot "dat-backup\new-files.txt"

if (-not (Test-Path $game)) { throw "Game folder not found: $game  (fix ffxi_client_dir in config.json)" }
if (-not (Test-Path "$game\ROM")) { throw "No ROM folder inside $game - that doesn't look like the FFXI game folder." }
if (Test-Path $backup) { throw "A backup already exists at $backup, so the Era-DATs were probably installed already. Run restore-original-dats.ps1 first if you want to redo it." }

$files = foreach ($rom in "ROM","ROM2","ROM3","ROM4") {
  if (Test-Path "$src\$rom") { Get-ChildItem "$src\$rom" -Recurse -File }
}
$replace = 0; $new = 0
foreach ($f in $files) { $rel = $f.FullName.Substring($src.Length).TrimStart('\'); if (Test-Path (Join-Path $game $rel)) { $replace++ } else { $new++ } }

Write-Host "Game folder : $game"
Write-Host "Files to copy: $($files.Count)  ($replace replace existing files, $new are new)"
Write-Host "Originals will be saved to: $backup"
if ((Read-Host "Type YES to continue") -ne "YES") { Write-Host "Cancelled. Nothing changed."; exit }

New-Item -ItemType Directory -Force $backup | Out-Null
$newList = @()
foreach ($f in $files) {
  $rel  = $f.FullName.Substring($src.Length).TrimStart('\')
  $dest = Join-Path $game $rel
  if (Test-Path $dest) {
    $b = Join-Path $backup $rel
    New-Item -ItemType Directory -Force (Split-Path $b) | Out-Null
    Copy-Item $dest $b -Force
  } else {
    $newList += $rel
    New-Item -ItemType Directory -Force (Split-Path $dest) | Out-Null
  }
  Copy-Item $f.FullName $dest -Force
}
$newList | Set-Content $manifest
Write-Host "Done. Era-DATs installed. To undo: .\restore-original-dats.ps1" -ForegroundColor Green
