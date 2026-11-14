# Tells you whether the server needs a REBUILD (C++ changed) or just a RESTART (Lua/SQL changed).
# Usage:  cd C:\FFXISOLO; .\check-rebuild.ps1
# It only looks at file dates; it never changes anything.
$ErrorActionPreference = "SilentlyContinue"
$cfg    = Get-Content "$PSScriptRoot\config.json" | ConvertFrom-Json
$server = $cfg.server_dir
$exe    = Join-Path $server "xi_map.exe"

Write-Host ""
if (-not (Test-Path $exe)) {
    Write-Host "REBUILD NEEDED: xi_map.exe is missing." -ForegroundColor Red
    Write-Host "Close the game, then double-click 'Rebuild server.bat' in C:\FFXISOLO."
    exit 1
}

$built = (Get-Item $exe).LastWriteTime
Write-Host ("Server program last built: {0:ddd MMM d, h:mm tt}" -f $built)

# C++ / CMake files newer than the server program
$codeDirs = @((Join-Path $server "src"), (Join-Path $server "modules"), (Join-Path $server "cmake"))
$code = foreach ($d in $codeDirs) {
    Get-ChildItem $d -Recurse -File -Include *.cpp, *.h, *.hpp, CMakeLists.txt, *.cmake |
        Where-Object { $_.LastWriteTime -gt $built }
}
$code += Get-ChildItem (Join-Path $server "CMakeLists.txt") | Where-Object { $_.LastWriteTime -gt $built }

if ($code) {
    Write-Host ""
    Write-Host "REBUILD NEEDED: these C++ files changed after the last build:" -ForegroundColor Red
    $code | Sort-Object LastWriteTime | ForEach-Object { Write-Host ("   " + $_.FullName.Replace($server + "\", "")) }
    Write-Host ""
    Write-Host "Close the game, then double-click 'Rebuild server.bat' in C:\FFXISOLO, then PLAY." -ForegroundColor Yellow
    exit 1
}

Write-Host "No rebuild needed: no C++ file changed since the last build." -ForegroundColor Green

# Lua / SQL / settings changed while the server is running -> STOP and PLAY
$map = Get-Process xi_map | Select-Object -First 1
if ($map) {
    $started = $map.StartTime
    $scriptDirs = @((Join-Path $server "modules"), (Join-Path $server "scripts"), (Join-Path $server "settings"))
    $changed = foreach ($d in $scriptDirs) {
        Get-ChildItem $d -Recurse -File -Include *.lua, *.sql, *.txt |
            Where-Object { $_.LastWriteTime -gt $started }
    }
    if ($changed) {
        Write-Host ""
        Write-Host ("RESTART NEEDED: {0} script file(s) changed since the server started:" -f @($changed).Count) -ForegroundColor Yellow
        $changed | Sort-Object LastWriteTime | Select-Object -Last 10 |
            ForEach-Object { Write-Host ("   " + $_.FullName.Replace($server + "\", "")) }
        Write-Host "Press STOP, then PLAY in the launcher (no rebuild)." -ForegroundColor Yellow
    } else {
        Write-Host "No restart needed: the running server already has the latest scripts." -ForegroundColor Green
    }
} else {
    Write-Host "The server is not running: PLAY loads the latest scripts." -ForegroundColor Green
}
Write-Host ""
