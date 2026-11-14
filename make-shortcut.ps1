# Puts an "FFXI Solo" shortcut on your desktop that opens the launcher window (no console).
$pyw = (Get-Command pythonw -ErrorAction SilentlyContinue).Source
if (-not $pyw) { $pyw = Join-Path (Split-Path (Get-Command python).Source) "pythonw.exe" }
if (-not (Test-Path $pyw)) { Write-Host "Could not find pythonw.exe. Is Python installed?" -ForegroundColor Red; exit 1 }

python -c "import tkinter" 2>$null
if ($LASTEXITCODE -ne 0) {
  Write-Host "Your Python does not include tkinter (the window toolkit). Re-run the Python installer, choose Modify, and tick 'tcl/tk and IDLE'." -ForegroundColor Yellow
}

$lnk = Join-Path ([Environment]::GetFolderPath('Desktop')) "FFXI Solo.lnk"
$s = (New-Object -ComObject WScript.Shell).CreateShortcut($lnk)
$s.TargetPath = $pyw
$s.Arguments = "`"$PSScriptRoot\launcher_gui.pyw`""
$s.WorkingDirectory = $PSScriptRoot
$ico = Join-Path $PSScriptRoot "assets\solo.ico"
if (Test-Path $ico) { $s.IconLocation = $ico }
$s.Save()
Write-Host "Created: $lnk" -ForegroundColor Green
