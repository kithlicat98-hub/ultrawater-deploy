# ═══════════════════════════════════════════════════════
#  UltraWater Client — Windows PowerShell Installer
#  Usage: iwr -useb https://kithlicat98-hub.github.io/ultrawater/install.ps1 | iex
# ═══════════════════════════════════════════════════════
$ErrorActionPreference = 'Stop'

$GH_USER    = 'kithlicat98-hub'
$GH_REPO    = 'ultrawater'
$BASE       = "https://github.com/$GH_USER/$GH_REPO/releases/latest/download"
$SETUP_URL  = "$BASE/UltraWater-Setup.exe"
$ZIP_URL    = "$BASE/UltraWater-windows-x64.zip"
$INSTALL    = "$env:LOCALAPPDATA\UltraWater"
$EXE        = "$INSTALL\UltraWater.exe"

function Write-Banner {
  Write-Host ""
  Write-Host "┌─────────────────────────────────────┐" -ForegroundColor Cyan
  Write-Host "│   UltraWater Client Installer       │" -ForegroundColor Cyan
  Write-Host "│   github.com/$GH_USER/$GH_REPO" -ForegroundColor Cyan
  Write-Host "└─────────────────────────────────────┘" -ForegroundColor Cyan
  Write-Host ""
}

function Write-Step  { param($msg) Write-Host "→  $msg" -ForegroundColor Cyan }
function Write-OK    { param($msg) Write-Host "✓  $msg" -ForegroundColor Green }
function Write-Warn  { param($msg) Write-Host "⚠  $msg" -ForegroundColor Yellow }
function Write-Fail  { param($msg) Write-Host "✗  $msg" -ForegroundColor Red; exit 1 }

Write-Banner

# ── Try to download and run the GUI installer ────────
Write-Step "Downloading UltraWater-Setup.exe..."
$TMP = [System.IO.Path]::GetTempPath()
$SetupPath = Join-Path $TMP "UltraWater-Setup.exe"

try {
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
    $wc = New-Object System.Net.WebClient
    $wc.DownloadFile($SETUP_URL, $SetupPath)
    Write-OK "Downloaded installer"

    Write-Step "Running installer — follow the prompts..."
    Start-Process -FilePath $SetupPath -Wait
    Write-OK "Setup complete"
    Remove-Item $SetupPath -Force -ErrorAction SilentlyContinue
    exit 0
}
catch {
    Write-Warn "GUI installer failed — falling back to portable install"
}

# ── Fallback: portable ZIP install ──────────────────
Write-Step "Downloading portable ZIP..."
$ZipPath = Join-Path $TMP "UltraWater.zip"

try {
    $wc = New-Object System.Net.WebClient
    $wc.DownloadFile($ZIP_URL, $ZipPath)
    Write-OK "Download complete"
}
catch {
    Write-Fail "Download failed: $_`nCheck your internet connection and try again."
}

Write-Step "Extracting to $INSTALL..."
if (Test-Path $INSTALL) { Remove-Item $INSTALL -Recurse -Force }
New-Item -ItemType Directory -Path $INSTALL -Force | Out-Null
Expand-Archive -Path $ZipPath -DestinationPath $INSTALL -Force
Remove-Item $ZipPath -Force
Write-OK "Extracted"

# ── Find the exe ────────────────────────────────────
if (-not (Test-Path $EXE)) {
    $found = Get-ChildItem $INSTALL -Filter "UltraWater.exe" -Recurse -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($found) { $EXE = $found.FullName }
    else { Write-Fail "Could not locate UltraWater.exe in the extracted files." }
}
Write-OK "Executable: $EXE"

# ── Shortcuts ───────────────────────────────────────
$WS = New-Object -ComObject WScript.Shell

$StartMenuDir = "$env:APPDATA\Microsoft\Windows\Start Menu\Programs"
$ShortcutSM   = Join-Path $StartMenuDir "UltraWater Client.lnk"
$ShortcutDT   = Join-Path ([Environment]::GetFolderPath('Desktop')) "UltraWater Client.lnk"

foreach ($path in @($ShortcutSM, $ShortcutDT)) {
    $sc = $WS.CreateShortcut($path)
    $sc.TargetPath       = $EXE
    $sc.WorkingDirectory = Split-Path $EXE
    $sc.Description      = "UltraWater — Ultralight Minecraft Launcher"
    $sc.Save()
}
Write-OK "Desktop shortcut created"
Write-OK "Start Menu shortcut created"

# ── Done ────────────────────────────────────────────
Write-Host ""
Write-Host "Installation complete!" -ForegroundColor Green -NoNewline
Write-Host " UltraWater is ready." -ForegroundColor White
Write-Host ""
Write-Host "  Open from: Desktop or Start Menu → UltraWater Client" -ForegroundColor Cyan
Write-Host ""

$launch = Read-Host "Launch UltraWater now? [Y/n]"
if ($launch -ne 'n' -and $launch -ne 'N') {
    Write-Step "Starting UltraWater..."
    Start-Process -FilePath $EXE
    Write-OK "Running!"
}
