# Install git hook to strip Cursor co-author from commits
$ErrorActionPreference = "Stop"
$Root = Split-Path $PSScriptRoot -Parent
$HookSrc = Join-Path $Root "scripts\hooks\prepare-commit-msg"
$HookDst = Join-Path $Root ".git\hooks\prepare-commit-msg"

if (-not (Test-Path (Join-Path $Root ".git"))) {
    Write-Error "Run from the SuperMemory repo (no .git folder found)."
}

Copy-Item $HookSrc $HookDst -Force
Write-Host "Installed prepare-commit-msg hook -> $HookDst"
Write-Host "Cursor co-author lines will be removed from future commits."
