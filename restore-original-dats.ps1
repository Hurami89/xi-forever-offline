# Undoes install-era-dats.ps1: puts the original files back and removes files the Era-DATs added.
# Run in an ADMINISTRATOR PowerShell from the kit folder:  .\restore-original-dats.ps1
$ErrorActionPreference = "Stop"
$cfg    = Get-Content "$PSScriptRoot\config.json" | ConvertFrom-Json
$game   = $cfg.ffxi_client_dir
$backup = Join-Path $PSScriptRoot "dat-backup"
$manifest = Join-Path $backup "new-files.txt"
if (-not (Test-Path $backup)) { throw "No backup folder at $backup - nothing to restore." }

Get-ChildItem $backup -Recurse -File | Where-Object { $_.Name -ne "new-files.txt" } | ForEach-Object {
  $rel = $_.FullName.Substring($backup.Length).TrimStart('\')
  Copy-Item $_.FullName (Join-Path $game $rel) -Force
}
if (Test-Path $manifest) {
  Get-Content $manifest | Where-Object { $_ } | ForEach-Object {
    $p = Join-Path $game $_
    if (Test-Path $p) { Remove-Item $p -Force }
  }
}
Rename-Item $backup ("dat-backup-restored-" + (Get-Date -Format yyyyMMdd-HHmmss))
Write-Host "Original game files restored." -ForegroundColor Green
