# Making a release

Players get two things from GitHub releases: the server package (repo `xi-forever-offline-server`) and the launcher
(repo `xi-forever-offline`). The first-run setup downloads the newest server release by itself.

## Server
1. Commit everything in the server folder, then build it (`Rebuild server.bat`).
2. Make the package (in the kit folder; `--list` first shows what goes in):
   ```powershell
   cd C:\FFXISOLO
   python package_server.py v0.1.0 --list
   python package_server.py v0.1.0
   ```
   It writes `dist\xi-forever-offline-server-v0.1.0-win64.zip` and `dist\SHA256SUMS.txt`. Only files git tracks go in
   (plus the navmeshes and ximeshes submodules); never backups, logs, crash dumps, this PC's settings or the
   `.cert`/`.key` files (the server makes its own on first start).
3. Tag the commit and publish it as the `release` branch (your `beta` branch keeps following Phoenix):
   ```powershell
   cd C:\ffxi-local\server
   git tag -a v0.1.0 -m "XI: Forever Offline server v0.1.0"
   git push xiforever HEAD:refs/heads/release
   git push xiforever v0.1.0
   ```
4. On GitHub, xi-forever-offline-server > Releases > Draft a new release: choose the tag, attach both files from `dist\`, publish.

## Launcher
1. Commit and push the kit, then build the exe: `.\build_release.ps1`.
2. Tag it (`git tag -a v0.1.0 -m "..."`, `git push origin v0.1.0`) and attach `XI Forever Offline.exe` to a release
   of xi-forever-offline.

While the repos are private, players cannot download either release.
