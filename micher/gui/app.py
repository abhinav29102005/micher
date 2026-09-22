"""
Micher Desktop Application — main window.

Dark-themed CustomTkinter application with tabbed interface:
  - Send tab: file picker + transfer controls + dashboard
  - Receive tab: server controls + dashboard
  - Interfaces tab: NIC discovery & health
"""

from __future__ import annotations

import queue
import threading
import tkinter as tk
from pathlib import Path

import customtkinter as ctk

from ..core.interfaces import list_interfaces, is_reachable, InterfaceType
from ..core.transfer import BondedSender, BondedReceiver
from ..core.stats import TransferSnapshot
from .dashboard import DashboardPanel
from .transfer_view import SendPanel, ReceivePanel
from .tray import TrayIcon, HAS_TRAY
from . import theme

ITYPE_ICONS = {
    InterfaceType.ETHERNET: "🔌",
    InterfaceType.WIFI: "📶",
    InterfaceType.HOTSPOT: "📱",
    InterfaceType.UNKNOWN: "🌐",
}


class MicherApp(ctk.CTk):
    """Main application window."""

    def __init__(self):
        super().__init__()

        # ── Window setup ──
        self.title("⚡ Micher — Network Bonding")
        self.geometry(f"{theme.WINDOW_MIN_W}x{theme.WINDOW_MIN_H}")
        self.minsize(theme.WINDOW_MIN_W, theme.WINDOW_MIN_H)
        self.configure(fg_color=theme.BG_DARK)

        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        # Load icon if available
        icon_path = Path(__file__).parent.parent / "assets" / "icon.png"
        if icon_path.exists():
            try:
                self.iconphoto(True, tk.PhotoImage(file=str(icon_path)))
            except Exception:
                pass

        # ── Stats queue (thread-safe communication) ──
        self._stats_queue: queue.Queue[TransferSnapshot] = queue.Queue()
        self._sender: BondedSender | None = None
        self._receiver: BondedReceiver | None = None

        # ── System tray ──
        self._tray = TrayIcon(on_open=self._show_window, on_quit=self._quit_app)
        if HAS_TRAY:
            self._tray.start()
            self.protocol("WM_DELETE_WINDOW", self._minimize_to_tray)
        else:
            self.protocol("WM_DELETE_WINDOW", self._quit_app)

        # ── Build UI ──
        self._build_ui()

        # ── Start polling stats queue ──
        self._poll_stats()

    def _build_ui(self) -> None:
        # Header bar
        header = ctk.CTkFrame(self, fg_color=theme.BG_CARD, height=56, corner_radius=0)
        header.pack(fill="x", padx=0, pady=0)
        header.pack_propagate(False)

        ctk.CTkLabel(
            header, text="⚡ Micher",
            text_color=theme.ACCENT_CYAN,
            font=ctk.CTkFont(size=theme.FONT_SIZE_XL, weight="bold"),
            anchor="w",
        ).pack(side="left", padx=20, pady=8)

        ctk.CTkLabel(
            header, text="Multi-Link Network Bonding",
            text_color=theme.TEXT_DIM,
            font=ctk.CTkFont(size=theme.FONT_SIZE_SM),
            anchor="w",
        ).pack(side="left", padx=(0, 20), pady=8)

        # Main content area
        content = ctk.CTkFrame(self, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=12, pady=12)

        # Tab view
        self.tabview = ctk.CTkTabview(
            content,
            fg_color=theme.BG_DARK,
            segmented_button_fg_color=theme.BG_CARD,
            segmented_button_selected_color=theme.ACCENT_CYAN,
            segmented_button_selected_hover_color=theme.ACCENT_BLUE,
            segmented_button_unselected_color=theme.BG_CARD,
            segmented_button_unselected_hover_color=theme.BG_CARD_HOVER,
            text_color=theme.BG_DARK,
            text_color_disabled=theme.TEXT_DIM,
            corner_radius=theme.CORNER_RADIUS,
        )
        self.tabview.pack(fill="both", expand=True)

        # ── Send tab ──
        send_tab = self.tabview.add("  🚀 Send  ")
        send_content = ctk.CTkFrame(send_tab, fg_color="transparent")
        send_content.pack(fill="both", expand=True)

        # Left: controls, Right: dashboard
        send_left = ctk.CTkFrame(send_content, fg_color="transparent", width=320)
        send_left.pack(side="left", fill="y", padx=(0, 8))
        send_left.pack_propagate(False)

        send_right = ctk.CTkFrame(send_content, fg_color="transparent")
        send_right.pack(side="left", fill="both", expand=True)

        self.send_panel = SendPanel(
            send_left,
            on_start=self._start_send,
            on_cancel=self._cancel_send,
        )
        self.send_panel.pack(fill="both", expand=True)

        self.send_dashboard = DashboardPanel(send_right)
        self.send_dashboard.pack(fill="both", expand=True)

        # ── Receive tab ──
        recv_tab = self.tabview.add("  📥 Receive  ")
        recv_content = ctk.CTkFrame(recv_tab, fg_color="transparent")
        recv_content.pack(fill="both", expand=True)

        recv_left = ctk.CTkFrame(recv_content, fg_color="transparent", width=320)
        recv_left.pack(side="left", fill="y", padx=(0, 8))
        recv_left.pack_propagate(False)

        recv_right = ctk.CTkFrame(recv_content, fg_color="transparent")
        recv_right.pack(side="left", fill="both", expand=True)

        self.recv_panel = ReceivePanel(
            recv_left,
            on_start=self._start_receive,
            on_stop=self._stop_receive,
        )
        self.recv_panel.pack(fill="both", expand=True)

        self.recv_dashboard = DashboardPanel(recv_right)
        self.recv_dashboard.pack(fill="both", expand=True)

        # ── Interfaces tab ──
        iface_tab = self.tabview.add("  🌐 Interfaces  ")
        self._build_interfaces_tab(iface_tab)

    def _build_interfaces_tab(self, parent: ctk.CTkFrame) -> None:
        scroll = ctk.CTkScrollableFrame(
            parent, fg_color="transparent",
            scrollbar_button_color=theme.BORDER,
        )
        scroll.pack(fill="both", expand=True, padx=4, pady=4)

        title = ctk.CTkLabel(
            scroll, text="Discovered Network Interfaces",
            text_color=theme.TEXT_PRIMARY,
            font=ctk.CTkFont(size=theme.FONT_SIZE_LG, weight="bold"),
            anchor="w",
        )
        title.pack(padx=8, pady=(8, 16), anchor="w")

        ifaces = list_interfaces()
        for iface in ifaces:
            card = ctk.CTkFrame(scroll, fg_color=theme.BG_CARD, corner_radius=theme.CORNER_RADIUS)
            card.pack(fill="x", padx=4, pady=4)

            icon = ITYPE_ICONS.get(iface.itype, "🌐")
            color = theme.IFACE_COLORS.get(iface.itype.value, theme.TEXT_PRIMARY)
            reachable = is_reachable(iface.ip, timeout=1.0)

            row = ctk.CTkFrame(card, fg_color="transparent")
            row.pack(fill="x", padx=16, pady=12)

            ctk.CTkLabel(
                row, text=f"{icon} {iface.name}",
                text_color=color,
                font=ctk.CTkFont(size=theme.FONT_SIZE_MD, weight="bold"),
                anchor="w",
            ).pack(side="left")

            ctk.CTkLabel(
                row, text=iface.ip,
                text_color=theme.ACCENT_CYAN,
                font=ctk.CTkFont(size=theme.FONT_SIZE_MD),
                anchor="w",
            ).pack(side="left", padx=(16, 0))

            ctk.CTkLabel(
                row, text=iface.itype.value.title(),
                text_color=theme.TEXT_DIM,
                font=ctk.CTkFont(size=theme.FONT_SIZE_SM),
                anchor="w",
            ).pack(side="left", padx=(16, 0))

            status_color = theme.ACCENT_GREEN if reachable else theme.ACCENT_RED
            status_text = "● Online" if reachable else "● Offline"
            ctk.CTkLabel(
                row, text=status_text,
                text_color=status_color,
                font=ctk.CTkFont(size=theme.FONT_SIZE_SM, weight="bold"),
            ).pack(side="right")

        if not ifaces:
            ctk.CTkLabel(
                scroll, text="No active network interfaces found.",
                text_color=theme.ACCENT_RED,
                font=ctk.CTkFont(size=theme.FONT_SIZE_MD),
            ).pack(pady=32)

    # ── Transfer logic ────────────────────────────────────────────────── #

    def _on_progress(self, snap: TransferSnapshot) -> None:
        """Callback from transfer threads — enqueues snapshot for UI thread."""
        self._stats_queue.put(snap)

    def _poll_stats(self) -> None:
        """Drain stats queue and update active dashboard. Runs on UI thread."""
        try:
            while True:
                snap = self._stats_queue.get_nowait()
                # Update whichever dashboard is active
                current_tab = self.tabview.get()
                if "Send" in current_tab:
                    self.send_dashboard.update(snap)
                else:
                    self.recv_dashboard.update(snap)

                # Update tray tooltip
                if HAS_TRAY:
                    self._tray.update_tooltip(
                        f"Micher — {snap.combined_mbps:.1f} Mbps"
                    )
        except queue.Empty:
            pass
        self.after(200, self._poll_stats)  # 5 Hz

    def _start_send(self, host: str, port: int, filepath: str | None, interfaces) -> None:
        if not filepath:
            self._show_error("No file selected")
            return
        if not host:
            self._show_error("No server host specified")
            return
        if not interfaces:
            self._show_error("No interfaces selected")
            return

        local_ips = [i.ip for i in interfaces]
        names = {i.ip: f"{ITYPE_ICONS.get(i.itype, '🌐')} {i.name}" for i in interfaces}

        self._sender = BondedSender(host, port, local_ips, interface_names=names)
        self.send_panel.set_transferring(True)
        self.send_dashboard.status_label.configure(
            text="⚡ Connecting...", text_color=theme.ACCENT_YELLOW
        )
        self.send_dashboard.file_label.configure(text=Path(filepath).name)

        def do_send():
            try:
                self._sender.send_file(filepath, on_progress=self._on_progress)
            except Exception as e:
                self._stats_queue.put(None)  # signal error
                self.after(0, lambda: self._show_error(str(e)))
            finally:
                self.after(0, lambda: self.send_panel.set_transferring(False))

        threading.Thread(target=do_send, daemon=True).start()

    def _cancel_send(self) -> None:
        if self._sender:
            self._sender.cancel()
        self.send_panel.set_transferring(False)
        self.send_dashboard.set_idle()

    def _start_receive(self, port: int, save_dir: str, interfaces) -> None:
        n_links = max(len(interfaces), 1)
        self._receiver = BondedReceiver(
            "0.0.0.0", port, expected_links=n_links,
            on_progress=self._on_progress,
        )
        self.recv_panel.set_listening(True)
        self.recv_dashboard.status_label.configure(
            text="📥 Waiting for sender...", text_color=theme.ACCENT_YELLOW
        )

        def do_recv():
            try:
                saved = self._receiver.receive_file(save_dir)
                self.after(0, lambda: self.recv_dashboard.file_label.configure(
                    text=f"Saved: {saved.name}"
                ))
            except Exception as e:
                self.after(0, lambda: self._show_error(str(e)))
            finally:
                self.after(0, lambda: self.recv_panel.set_listening(False))

        threading.Thread(target=do_recv, daemon=True).start()

    def _stop_receive(self) -> None:
        # Receiving can't be cleanly cancelled mid-stream easily, but we
        # reset the UI. A future improvement could use a cancel event.
        self.recv_panel.set_listening(False)
        self.recv_dashboard.set_idle()

    def _show_error(self, msg: str) -> None:
        dialog = ctk.CTkToplevel(self)
        dialog.title("Error")
        dialog.geometry("400x150")
        dialog.configure(fg_color=theme.BG_DARK)
        dialog.transient(self)
        dialog.grab_set()

        ctk.CTkLabel(
            dialog, text="❌ Error",
            text_color=theme.ACCENT_RED,
            font=ctk.CTkFont(size=theme.FONT_SIZE_LG, weight="bold"),
        ).pack(pady=(20, 8))

        ctk.CTkLabel(
            dialog, text=msg,
            text_color=theme.TEXT_PRIMARY,
            font=ctk.CTkFont(size=theme.FONT_SIZE_SM),
            wraplength=360,
        ).pack(pady=(0, 16))

        ctk.CTkButton(
            dialog, text="OK", width=80, height=32,
            fg_color=theme.ACCENT_BLUE,
            command=dialog.destroy,
        ).pack()

    # ── Window management ─────────────────────────────────────────────── #

    def _minimize_to_tray(self) -> None:
        self.withdraw()

    def _show_window(self) -> None:
        self.deiconify()
        self.lift()
        self.focus_force()

    def _quit_app(self) -> None:
        self._tray.stop()
        self.destroy()


def main() -> None:
    app = MicherApp()
    app.mainloop()


if __name__ == "__main__":
    main()
