# Looks at the Phoenix server repository for new commits WITHOUT changing anything: it only downloads the list of changes.
# Run:  cd C:\FFXISOLO ; Set-ExecutionPolicy -Scope Process Bypass ; .\check-updates.ps1
# Optional:  .\check-updates.ps1 -Show 60     (how many of the newest changes to list)
param([int]$Show = 30)
$ErrorActionPreference = "Stop"
$cfg  = Get-Content "$PSScriptRoot\config.json" | ConvertFrom-Json
$root = $cfg.server_dir
if (-not (Get-Command git -ErrorAction SilentlyContinue)) { throw "git was not found on this PC." }
if (-not (Test-Path "$root\.git")) { throw "$root is not a git checkout, so there is nothing to compare with." }

$report = New-Object System.Collections.Generic.List[string]
function Say($text) { Write-Host $text; $report.Add([string]$text) }

Say "Server folder: $root"
Say "Remotes:"
(& git -C $root remote -v) | ForEach-Object { Say "  $_" }
$branch = (& git -C $root rev-parse --abbrev-ref HEAD).Trim()
Say "Branch: $branch"
Say ("Your latest commit: " + (& git -C $root log -1 --date=short --pretty="format:%ad  %s"))

Write-Host "`nChecking for new commits (needs the internet)..." -ForegroundColor Cyan
& git -C $root fetch origin --quiet
if ($LASTEXITCODE -ne 0) { throw "git fetch failed: no internet, or the remote can not be reached." }
$upstream = "origin/$branch"
& git -C $root rev-parse --verify --quiet $upstream | Out-Null
if ($LASTEXITCODE -ne 0) { throw "There is no $upstream on the remote." }

$behind = [int](& git -C $root rev-list --count "HEAD..$upstream")
$ahead  = [int](& git -C $root rev-list --count "$upstream..HEAD")
Say ""
Say "New commits upstream: $behind      Commits only on your server: $ahead"

if ($behind -eq 0) {
  Say "You are up to date."
} else {
  Say ""
  Say "Newest changes:"
  (& git -C $root log "HEAD..$upstream" --date=short --pretty="format:%ad  %s" -n $Show) | ForEach-Object { Say "  $_" }

  $theirs = @(& git -C $root diff --name-only "HEAD..$upstream")
  Say ""
  Say ("Files changed upstream: {0}. Where:" -f $theirs.Count)
  $theirs | ForEach-Object { $p = $_ -split '/'; if ($p.Count -ge 2) { "$($p[0])/$($p[1])" } else { $p[0] } } |
    Group-Object | Sort-Object Count -Descending | Select-Object -First 15 | ForEach-Object { Say ("  {0,5}  {1}" -f $_.Count, $_.Name) }

  # The files WE changed in the server code (our core patches, the Goblin Tailor quest, init.txt ...)
  $ours = @(& git -C $root diff --name-only HEAD)
  Say ""
  Say ("Files in the server that you (or our patches) changed: {0}" -f $ours.Count)
  $ours | ForEach-Object { Say "  $_" }
  $overlap = @($ours | Where-Object { $theirs -contains $_ })
  Say ""
  if ($overlap.Count -gt 0) {
    Say "!! Upstream ALSO changed these, so updating needs care (Claude can help merge them):"
    $overlap | ForEach-Object { Say "   $_" }
  } else {
    Say "None of your changed files were touched upstream, so an update should apply cleanly."
  }
}

Set-Content "$PSScriptRoot\update-report.txt" $report -Encoding UTF8
Write-Host "`nSaved to $PSScriptRoot\update-report.txt" -ForegroundColor Green
