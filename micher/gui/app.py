
import os
import queue
import threading
from pathlib import Path

import customtkinter as ctk

from . import theme
from .monitor_view import MonitorDashboard
from .tray import HAS_TRAY, TrayIcon
from micher.core.proxy import BondingSocks5Proxy

class MicherApp(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()

        self.title("Micher")
        self.geometry("900x600")
        self.configure(fg_color=theme.BG_DARK)

        icon_path = Path(__file__).parent.parent / "assets" / "icon.png"
        if icon_path.exists() and os.name == "nt":
            self.iconbitmap(str(icon_path).replace(".png", ".ico"))

        # Setup tray
        self._tray = TrayIcon(
            on_open=self._show_window,
            on_quit=self._quit_app,
        )

        # Handle window close
        self.protocol("WM_DELETE_WINDOW", self._minimize_to_tray if HAS_TRAY else self._quit_app)

        # Main Monitor Dashboard
        self.dashboard = MonitorDashboard(self)
        self.dashboard.pack(fill="both", expand=True)
        
        # Start Proxy
        self.proxy = BondingSocks5Proxy(port=1080)
        self.proxy.start()
        
        # Start tray in background
        self._tray.start()

    def _minimize_to_tray(self) -> None:
        self.withdraw()

    def _show_window(self) -> None:
        self.deiconify()
        self.lift()
        self.focus_force()

    def _quit_app(self) -> None:
        self.proxy.stop()
        self.dashboard.destroy()
        self._tray.stop()
        self.destroy()

def main() -> None:
    app = MicherApp()
    app.mainloop()

if __name__ == "__main__":
    main()
