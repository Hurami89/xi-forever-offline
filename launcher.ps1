# Starts MariaDB + the 5 server programs, then launches the game.
# Plain mode: through xiloader.  Ashita mode: "ashita_dir" and "ashita_boot" set in config.json.
# Server windows stay visible so you can read any errors. Closing the game stops the servers.
$cfg = Get-Content "$PSScriptRoot\config.json" | ConvertFrom-Json
$procs = @()
$sidecar = $null

function Fail($msg) {
  Write-Host "`nERROR: $msg" -ForegroundColor Red
  Get-Process xi_connect,xi_world,xi_search,xi_profile,xi_map -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
  if ($script:sidecar -and -not $script:sidecar.HasExited) { Stop-Process -Id $script:sidecar.Id -Force -ErrorAction SilentlyContinue }
  exit 1
}

# 0. Clean slate: stop leftovers from earlier runs (old servers on the same ports make new ones fail)
Get-Process xi_connect,xi_world,xi_search,xi_profile,xi_map,xiloader -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
Get-CimInstance Win32_Process -Filter "name='pythonw.exe' OR name='python.exe'" -ErrorAction SilentlyContinue |
  Where-Object { $_.CommandLine -like '*squad_chat.py*' } |
  ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
Start-Sleep 2

# 1. Database
$svc = Get-Service $cfg.mariadb_service -ErrorAction SilentlyContinue
if (-not $svc) { Fail "MariaDB service '$($cfg.mariadb_service)' not found - check mariadb_service in config.json" }
if ($svc.Status -ne "Running") { Start-Service $svc; Start-Sleep 3 }

# 2. Server programs (each in its own window, started inside the server folder)
foreach ($exe in "xi_connect","xi_world","xi_search","xi_profile","xi_map") {
  $path = Join-Path $cfg.server_dir "$exe.exe"
  if (-not (Test-Path $path)) { Fail "Missing $path - did the build finish?" }
  $procs += Start-Process $path -WorkingDirectory $cfg.server_dir -PassThru
  Write-Host "Started $exe"
  Start-Sleep 3
}

# The map server takes a while to load all game data. Wait so the game does not start before it is ready.
$wait = if ($cfg.map_wait_seconds) { $cfg.map_wait_seconds } else { 45 }
for ($i = $wait; $i -gt 0; $i--) { Write-Host -NoNewline "`rWaiting for the map server to load... $i s  "; Start-Sleep 1 }
Write-Host ""

# Make sure all five are still alive (one that crashed on startup is a common cause of 'net connect failed')
foreach ($exe in "xi_connect","xi_world","xi_search","xi_profile","xi_map") {
  if (-not (Get-Process $exe -ErrorAction SilentlyContinue)) { Fail "$exe stopped right after starting. Look at its window, or run it by hand to see why." }
}

# 2.5 Squad chat: the local Ollama sidecar that lets squad mates answer in party chat.
$sidecarDir = Join-Path $PSScriptRoot "squad-chat"
$sidecarScript = Join-Path $sidecarDir "squad_chat.py"
if (Test-Path $sidecarScript) {
  $pythonw = (Get-Command pythonw.exe -ErrorAction SilentlyContinue).Source
  if (-not $pythonw) { $pythonw = (Get-Command python.exe -ErrorAction SilentlyContinue).Source }
  if ($pythonw) {
    $sidecar = Start-Process $pythonw -ArgumentList "`"$sidecarScript`"" -WorkingDirectory $sidecarDir -WindowStyle Hidden -PassThru
    Write-Host "Started squad chat sidecar"
  } else {
    Write-Host "Python not found - squad mates will not talk in party chat" -ForegroundColor Yellow
  }
} else {
  Write-Host "squad-chat\squad_chat.py not found - squad mates will not talk in party chat" -ForegroundColor Yellow
}

# 3. Game
if ($cfg.ashita_dir) {
  $cli = Join-Path $cfg.ashita_dir "Ashita-cli.exe"
  if (-not (Test-Path $cli)) { Fail "Missing $cli" }

  # Ashita starts the loader from its own bootloader folder. Keep a copy of the one we built there.
  $built = Get-ChildItem $cfg.xiloader_dir -Recurse -Filter xiloader.exe | Select-Object -First 1
  $dest  = Join-Path $cfg.ashita_dir "bootloader\xiloader.exe"
  if ($built -and ((-not (Test-Path $dest)) -or ($built.LastWriteTime -gt (Get-Item $dest).LastWriteTime))) {
    Copy-Item $built.FullName $dest -Force
    Write-Host "Updated $dest"
  }

  Write-Host "Starting game through Ashita ($($cfg.ashita_boot))"
  Start-Process $cli -WorkingDirectory $cfg.ashita_dir -ArgumentList $cfg.ashita_boot
  # Ashita closes itself once the game starts, so wait on xiloader (it stays open while the game runs).
  $game = $null
  for ($i = 0; $i -lt 60 -and -not $game; $i++) { Start-Sleep 1; $game = Get-Process xiloader -ErrorAction SilentlyContinue | Select-Object -First 1 }
  if (-not $game) { Fail "xiloader never started. Read the Ashita window for the error message." }
} else {
  $loader = Get-ChildItem $cfg.xiloader_dir -Recurse -Filter xiloader.exe | Select-Object -First 1
  if (-not $loader) { Fail "xiloader.exe not found - did setup finish?" }
  Write-Host "Starting game via $($loader.FullName)"
  $game = Start-Process $loader.FullName -WorkingDirectory $cfg.ffxi_client_dir -ArgumentList "--server 127.0.0.1 --user $($cfg.game_user) --pass $($cfg.game_pass)" -PassThru
}

try { $game | Wait-Process } finally {
  Write-Host "Game closed. Stopping servers..."
  Get-Process xi_connect,xi_world,xi_search,xi_profile,xi_map -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
  if ($script:sidecar -and -not $script:sidecar.HasExited) { Stop-Process -Id $script:sidecar.Id -Force -ErrorAction SilentlyContinue }
}
