"""
Windows shortcut creator for Micher.

Creates:
  - Desktop shortcut
  - Start Menu shortcut

Run:  python create_shortcut.py
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path


def _find_exe() -> Path:
    """Find the micher-gui executable."""
    # Check if installed as a script
    for d in os.environ.get("PATH", "").split(os.pathsep):
        candidate = Path(d) / "micher-gui.exe"
        if candidate.exists():
            return candidate
        candidate = Path(d) / "micher-gui"
        if candidate.exists():
            return candidate

    # Fallback: use pythonw -m micher.gui.app
    return Path(sys.executable).parent / "pythonw.exe"


def create_shortcut_windows() -> None:
    """Create Windows shortcuts using PowerShell."""
    exe = _find_exe()
    icon_path = Path(__file__).parent.parent / "micher" / "assets" / "icon.ico"

    desktop = Path.home() / "Desktop"
    start_menu = Path(os.environ.get("APPDATA", "")) / "Microsoft" / "Windows" / "Start Menu" / "Programs"

    for target_dir, name in [(desktop, "Micher"), (start_menu, "Micher")]:
        if not target_dir.exists():
            continue
        shortcut_path = target_dir / f"{name}.lnk"

        # Use PowerShell to create .lnk
        ps_script = f'''
$ws = New-Object -ComObject WScript.Shell
$s = $ws.CreateShortcut("{shortcut_path}")
$s.TargetPath = "{exe}"
$s.Arguments = "-m micher.gui.app"
$s.WorkingDirectory = "{Path.home()}"
$s.Description = "Micher - Multi-link network bonding"
if (Test-Path "{icon_path}") {{ $s.IconLocation = "{icon_path}" }}
$s.Save()
'''
        subprocess.run(
            ["powershell", "-Command", ps_script],
            capture_output=True,
        )
        print(f"  Created shortcut: {shortcut_path}")


def create_shortcut_linux() -> None:
    """Install .desktop file on Linux."""
    desktop_file = Path(__file__).parent / "micher.desktop"
    target = Path.home() / ".local" / "share" / "applications" / "micher.desktop"
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(desktop_file, target)
    print(f"  Installed desktop entry: {target}")

    # Copy icon
    icon_src = Path(__file__).parent.parent / "micher" / "assets" / "icon.png"
    if icon_src.exists():
        icon_dir = Path.home() / ".local" / "share" / "icons" / "hicolor" / "256x256" / "apps"
        icon_dir.mkdir(parents=True, exist_ok=True)
        icon_dst = icon_dir / "micher.png"
        shutil.copy2(icon_src, icon_dst)
        print(f"  Installed icon: {icon_dst}")


if __name__ == "__main__":
    import platform

    system = platform.system()
    print("Creating Micher shortcuts...")

    if system == "Windows":
        create_shortcut_windows()
    elif system == "Linux":
        create_shortcut_linux()
    else:
        print(f"  Unsupported platform: {system}")
        sys.exit(1)

    print("Done!")
