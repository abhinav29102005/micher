# ── Micher Installer for Windows ─────────────────────────────────────────── #
# Install: irm https://micher.pages.dev/install.ps1 | iex
# ─────────────────────────────────────────────────────────────────────────── #

$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "⚡ Micher Installer" -ForegroundColor Cyan
Write-Host "Multi-link network bonding" -ForegroundColor DarkGray
Write-Host ""

# ── Check Python ──
$python = $null
foreach ($cmd in @("python", "python3", "py")) {
    try {
        $ver = & $cmd --version 2>&1
        if ($ver -match "Python 3") {
            $python = $cmd
            break
        }
    } catch { }
}

if (-not $python) {
    Write-Host "  ✖ Python 3 is required but not found." -ForegroundColor Red
    Write-Host ""
    $install = Read-Host "  Install Python via winget? (y/n)"
    if ($install -eq "y") {
        Write-Host "  Installing Python..." -ForegroundColor Yellow
        winget install Python.Python.3.12 --accept-source-agreements --accept-package-agreements
        $python = "python"
        # Refresh PATH
        $env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path", "User")
    } else {
        Write-Host "  Download Python from https://python.org/downloads" -ForegroundColor DarkGray
        exit 1
    }
}

$pyVer = & $python --version 2>&1
Write-Host "  ✓ $pyVer found" -ForegroundColor Green

# ── Install micher ──
Write-Host ""
Write-Host "Installing micher..." -ForegroundColor Cyan

try {
    & $python -m pip install --upgrade "micher[gui]" 2>$null
} catch {
    try {
        & $python -m pip install --upgrade "git+https://github.com/abhinav29102005/micher.git#egg=micher[gui]"
    } catch {
        Write-Host "  ✖ Installation failed." -ForegroundColor Red
        Write-Host "  Clone the repo and run:" -ForegroundColor DarkGray
        Write-Host "    git clone https://github.com/abhinav29102005/micher.git"
        Write-Host '    cd micher; pip install -e ".[gui]"'
        exit 1
    }
}

Write-Host "  ✓ micher installed" -ForegroundColor Green

# ── Create shortcuts ──
Write-Host ""
Write-Host "Creating shortcuts..." -ForegroundColor Cyan

$scriptsDir = & $python -c "import sysconfig; print(sysconfig.get_path('scripts'))" 2>$null
$micherGui = Join-Path $scriptsDir "micher-gui.exe"

if (-not (Test-Path $micherGui)) {
    # Fallback: use pythonw
    $pythonw = (Get-Command pythonw -ErrorAction SilentlyContinue).Source
    if (-not $pythonw) { $pythonw = $python }
    $micherGui = $pythonw
    $micherArgs = "-m micher.gui.app"
} else {
    $micherArgs = ""
}

# Desktop shortcut
$desktopPath = [Environment]::GetFolderPath("Desktop")
$ws = New-Object -ComObject WScript.Shell
$shortcut = $ws.CreateShortcut("$desktopPath\Micher.lnk")
$shortcut.TargetPath = $micherGui
if ($micherArgs) { $shortcut.Arguments = $micherArgs }
$shortcut.WorkingDirectory = $env:USERPROFILE
$shortcut.Description = "Micher - Multi-link network bonding"
$shortcut.Save()
Write-Host "  ✓ Desktop shortcut created" -ForegroundColor Green

# Start Menu shortcut
$startMenu = "$env:APPDATA\Microsoft\Windows\Start Menu\Programs"
$shortcut2 = $ws.CreateShortcut("$startMenu\Micher.lnk")
$shortcut2.TargetPath = $micherGui
if ($micherArgs) { $shortcut2.Arguments = $micherArgs }
$shortcut2.WorkingDirectory = $env:USERPROFILE
$shortcut2.Description = "Micher - Multi-link network bonding"
$shortcut2.Save()
Write-Host "  ✓ Start Menu shortcut created" -ForegroundColor Green

# ── Done ──
Write-Host ""
Write-Host "✅ Micher installed successfully!" -ForegroundColor Green
Write-Host ""
Write-Host "  CLI:  micher interfaces" -ForegroundColor White
Write-Host "        micher send <host> <file>"
Write-Host "        micher receive"
Write-Host ""
Write-Host "  GUI:  micher-gui   (or find 'Micher' in Start Menu)" -ForegroundColor White
Write-Host ""
Write-Host "  Docker server:" -ForegroundColor White
Write-Host "        docker run -p 9191:9191 micher-server"
Write-Host ""
