"""
System tray integration using pystray.

Shows Micher in the system tray with a right-click menu:
  - Open Window
  - Start Server
  - Quit

On minimize, the window hides to tray instead of closing.
"""

from __future__ import annotations

import platform
import threading
from pathlib import Path
from typing import Callable

try:
    import pystray
    from PIL import Image
    HAS_TRAY = True
except ImportError:
    HAS_TRAY = False


def _load_icon() -> "Image.Image":
    """Load the app icon for the tray. Falls back to a generated icon."""
    icon_path = Path(__file__).parent.parent / "assets" / "icon.png"
    if icon_path.exists():
        return Image.open(icon_path).resize((64, 64))

    # Generate a simple icon if file is missing
    img = Image.new("RGBA", (64, 64), (13, 17, 23, 255))
    # Draw a simple cyan arrow
    from PIL import ImageDraw
    draw = ImageDraw.Draw(img)
    # Arrow shape
    draw.polygon(
        [(15, 20), (40, 32), (15, 44)],
        fill=(0, 212, 255, 255),
    )
    draw.rectangle(
        [(38, 26), (52, 38)],
        fill=(0, 212, 255, 255),
    )
    return img


class TrayIcon:
    """Manages the system tray icon and its menu."""

    def __init__(
        self,
        on_open: Callable[[], None] | None = None,
        on_quit: Callable[[], None] | None = None,
    ):
        self.on_open = on_open
        self.on_quit = on_quit
        self._icon: "pystray.Icon | None" = None
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if not HAS_TRAY:
            return

        menu = pystray.Menu(
            pystray.MenuItem("Open Micher", self._handle_open, default=True),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Quit", self._handle_quit),
        )

        self._icon = pystray.Icon(
            name="micher",
            icon=_load_icon(),
            title="Micher — Network Bonding",
            menu=menu,
        )

        self._thread = threading.Thread(target=self._icon.run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        if self._icon:
            self._icon.stop()

    def update_tooltip(self, text: str) -> None:
        if self._icon:
            self._icon.title = text

    def _handle_open(self, icon=None, item=None) -> None:
        if self.on_open:
            self.on_open()

    def _handle_quit(self, icon=None, item=None) -> None:
        if self.on_quit:
            self.on_quit()
