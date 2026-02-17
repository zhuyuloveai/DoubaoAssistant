param(
  [string]$SpecPath = ".\DoubaoAssistant.spec",
  [string]$OutDir = ".\release",
  [string]$ZipName = ""
)

$ErrorActionPreference = "Stop"

# Make console output UTF-8 to reduce garbled messages.
try {
  [Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()
  $OutputEncoding = [Console]::OutputEncoding
} catch {}

function Resolve-AbsPath([string]$p) {
  $resolved = Resolve-Path -LiteralPath $p
  # Resolve-Path may return an array in edge cases; always take the first.
  return [string]$resolved[0].Path
}

$repoRoot = $PSScriptRoot
if ([string]::IsNullOrWhiteSpace($repoRoot)) {
  $repoRoot = (Get-Location).Path
}
$repoRoot = [string](@($repoRoot)[0])

if ([System.IO.Path]::IsPathRooted($SpecPath)) {
  $specAbs = Resolve-AbsPath $SpecPath
} else {
  $specAbs = Resolve-AbsPath (Join-Path $repoRoot $SpecPath)
}

$resourcesDir = [System.IO.Path]::Combine($repoRoot, "resources")
$venvPython = [System.IO.Path]::Combine($repoRoot, "venv", "Scripts", "python.exe")

if (-not (Test-Path -Path $resourcesDir -PathType Container)) {
  throw "resources directory not found: $resourcesDir"
}
if (-not (Test-Path -Path $venvPython -PathType Leaf)) {
  throw "venv python not found: $venvPython"
}

Write-Host "== 1) Build exe with PyInstaller =="
Write-Host "Using python: $venvPython"
& $venvPython -m PyInstaller $specAbs

# PyInstaller default output: .\dist\DoubaoAssistant\DoubaoAssistant.exe or .\dist\DoubaoAssistant.exe
$distDir = [System.IO.Path]::Combine($repoRoot, "dist")
if (-not (Test-Path $distDir)) {
  throw "dist directory not found (PyInstaller may have failed): $distDir"
}

$exeCandidates = @(
  [System.IO.Path]::Combine([string]$distDir, "DoubaoAssistant", "DoubaoAssistant.exe"),
  [System.IO.Path]::Combine([string]$distDir, "DoubaoAssistant.exe")
)

$exePath = $exeCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $exePath) {
  $found = Get-ChildItem -Path $distDir -Recurse -Filter "DoubaoAssistant*.exe" -File | Select-Object -First 5
  throw "DoubaoAssistant.exe not found under dist. dist sample:`n$($found | Format-List | Out-String)"
}

Write-Host "== 2) Stage output (exe + resources) =="
if ([System.IO.Path]::IsPathRooted($OutDir)) {
  $outAbs = Resolve-AbsPath (New-Item -ItemType Directory -Force -Path $OutDir).FullName
} else {
  $outAbs = Resolve-AbsPath (New-Item -ItemType Directory -Force -Path (Join-Path $repoRoot $OutDir)).FullName
}

# Recreate staging directory
$staging = [System.IO.Path]::Combine([string]$outAbs, "staging")
if (Test-Path $staging) { Remove-Item -Recurse -Force $staging }
New-Item -ItemType Directory -Force -Path $staging | Out-Null

Copy-Item -Force -Path $exePath -Destination ([System.IO.Path]::Combine([string]$staging, "DoubaoAssistant.exe"))
Copy-Item -Recurse -Force -Path $resourcesDir -Destination ([System.IO.Path]::Combine([string]$staging, "resources"))

Write-Host "== 3) Create zip =="
if ([string]::IsNullOrWhiteSpace($ZipName)) {
  $ts = Get-Date -Format "yyyyMMdd_HHmmss"
  $ZipName = "DoubaoAssistant_$ts.zip"
}
$zipPath = Join-Path $outAbs $ZipName
if (Test-Path $zipPath) { Remove-Item -Force $zipPath }

Compress-Archive -Path ([System.IO.Path]::Combine([string]$staging, "*")) -DestinationPath $zipPath -Force

Write-Host ""
Write-Host "Done: $zipPath"
Write-Host "Staging contents:"
Get-ChildItem -Path $staging -Force
