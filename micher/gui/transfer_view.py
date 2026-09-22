"""
Transfer control panel — file picker, server host/port, interface selector,
and Start/Cancel buttons for both Send and Receive modes.
"""

from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import filedialog

import customtkinter as ctk

from ..core.interfaces import list_interfaces, is_reachable, InterfaceType, Interface
from . import theme

ITYPE_ICONS = {
    InterfaceType.ETHERNET: "🔌",
    InterfaceType.WIFI: "📶",
    InterfaceType.HOTSPOT: "📱",
    InterfaceType.UNKNOWN: "🌐",
}


def _format_size(n: int) -> str:
    v = float(n)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if v < 1024:
            return f"{v:.1f} {unit}"
        v /= 1024
    return f"{v:.1f} PB"


class InterfaceSelector(ctk.CTkFrame):
    """Checkbox list of discovered interfaces with online/offline status."""

    def __init__(self, master: ctk.CTkFrame, **kwargs):
        super().__init__(master, fg_color=theme.BG_CARD, corner_radius=theme.CORNER_RADIUS, **kwargs)

        title = ctk.CTkLabel(
            self, text="Network Interfaces",
            text_color=theme.TEXT_PRIMARY,
            font=ctk.CTkFont(size=theme.FONT_SIZE_MD, weight="bold"),
            anchor="w",
        )
        title.pack(padx=16, pady=(12, 8), anchor="w")

        self._checks: dict[str, tuple[ctk.CTkCheckBox, tk.BooleanVar, Interface]] = {}
        self._container = ctk.CTkFrame(self, fg_color="transparent")
        self._container.pack(fill="both", padx=12, pady=(0, 12))

        self.refresh_btn = ctk.CTkButton(
            self, text="🔄 Refresh", width=100, height=28,
            fg_color=theme.BORDER, hover_color=theme.BG_CARD_HOVER,
            text_color=theme.TEXT_PRIMARY,
            font=ctk.CTkFont(size=theme.FONT_SIZE_SM),
            corner_radius=8,
            command=self.refresh,
        )
        self.refresh_btn.pack(padx=16, pady=(0, 12), anchor="w")

        self.refresh()

    def refresh(self) -> None:
        for widget in self._container.winfo_children():
            widget.destroy()
        self._checks.clear()

        ifaces = list_interfaces()
        for iface in ifaces:
            var = tk.BooleanVar(value=True)
            icon = ITYPE_ICONS.get(iface.itype, "🌐")
            reachable = is_reachable(iface.ip, timeout=1.0)
            status_dot = "●" if reachable else "○"
            status_color = theme.ACCENT_GREEN if reachable else theme.ACCENT_RED

            row = ctk.CTkFrame(self._container, fg_color="transparent")
            row.pack(fill="x", pady=2)

            cb = ctk.CTkCheckBox(
                row,
                text=f"{icon} {iface.name}  ({iface.ip})",
                variable=var,
                text_color=theme.TEXT_PRIMARY,
                font=ctk.CTkFont(size=theme.FONT_SIZE_SM),
                fg_color=theme.ACCENT_CYAN,
                hover_color=theme.ACCENT_BLUE,
                corner_radius=4,
                checkbox_width=18,
                checkbox_height=18,
            )
            cb.pack(side="left", padx=(0, 8))

            status_lbl = ctk.CTkLabel(
                row, text=status_dot, text_color=status_color,
                font=ctk.CTkFont(size=14),
            )
            status_lbl.pack(side="right", padx=(0, 4))

            self._checks[iface.ip] = (cb, var, iface)

        if not ifaces:
            ctk.CTkLabel(
                self._container, text="No interfaces found",
                text_color=theme.ACCENT_RED,
                font=ctk.CTkFont(size=theme.FONT_SIZE_SM),
            ).pack(pady=8)

    def get_selected(self) -> list[Interface]:
        return [
            iface for ip, (cb, var, iface) in self._checks.items()
            if var.get()
        ]


class SendPanel(ctk.CTkFrame):
    """File-sending controls: file picker, host, port, start/cancel."""

    def __init__(
        self,
        master: ctk.CTkFrame,
        on_start=None,
        on_cancel=None,
        **kwargs,
    ):
        super().__init__(master, fg_color="transparent", **kwargs)
        self._on_start = on_start
        self._on_cancel = on_cancel
        self._filepath: str | None = None

        # ── File picker ──
        file_frame = ctk.CTkFrame(self, fg_color=theme.BG_CARD, corner_radius=theme.CORNER_RADIUS)
        file_frame.pack(fill="x", pady=(0, 8))

        ctk.CTkLabel(
            file_frame, text="File to Send",
            text_color=theme.TEXT_PRIMARY,
            font=ctk.CTkFont(size=theme.FONT_SIZE_MD, weight="bold"),
            anchor="w",
        ).pack(padx=16, pady=(12, 4), anchor="w")

        picker_row = ctk.CTkFrame(file_frame, fg_color="transparent")
        picker_row.pack(fill="x", padx=16, pady=(0, 12))

        self.file_label = ctk.CTkLabel(
            picker_row, text="No file selected",
            text_color=theme.TEXT_DIM,
            font=ctk.CTkFont(size=theme.FONT_SIZE_SM),
            anchor="w",
        )
        self.file_label.pack(side="left", fill="x", expand=True)

        self.browse_btn = ctk.CTkButton(
            picker_row, text="📁 Browse", width=100, height=30,
            fg_color=theme.ACCENT_BLUE, hover_color=theme.ACCENT_CYAN,
            text_color=theme.BG_DARK,
            font=ctk.CTkFont(size=theme.FONT_SIZE_SM, weight="bold"),
            corner_radius=8,
            command=self._browse,
        )
        self.browse_btn.pack(side="right", padx=(8, 0))

        # ── Server destination ──
        dest_frame = ctk.CTkFrame(self, fg_color=theme.BG_CARD, corner_radius=theme.CORNER_RADIUS)
        dest_frame.pack(fill="x", pady=(0, 8))

        ctk.CTkLabel(
            dest_frame, text="Destination Server",
            text_color=theme.TEXT_PRIMARY,
            font=ctk.CTkFont(size=theme.FONT_SIZE_MD, weight="bold"),
            anchor="w",
        ).pack(padx=16, pady=(12, 4), anchor="w")

        input_row = ctk.CTkFrame(dest_frame, fg_color="transparent")
        input_row.pack(fill="x", padx=16, pady=(0, 12))

        self.host_entry = ctk.CTkEntry(
            input_row, placeholder_text="hostname or IP",
            fg_color=theme.BG_INPUT, border_color=theme.BORDER,
            text_color=theme.TEXT_PRIMARY,
            font=ctk.CTkFont(size=theme.FONT_SIZE_SM),
            corner_radius=8, height=32,
        )
        self.host_entry.pack(side="left", fill="x", expand=True, padx=(0, 8))

        ctk.CTkLabel(
            input_row, text=":", text_color=theme.TEXT_DIM,
            font=ctk.CTkFont(size=theme.FONT_SIZE_MD),
        ).pack(side="left")

        self.port_entry = ctk.CTkEntry(
            input_row, placeholder_text="9191", width=70,
            fg_color=theme.BG_INPUT, border_color=theme.BORDER,
            text_color=theme.TEXT_PRIMARY,
            font=ctk.CTkFont(size=theme.FONT_SIZE_SM),
            corner_radius=8, height=32,
        )
        self.port_entry.insert(0, "9191")
        self.port_entry.pack(side="left", padx=(4, 0))

        # ── Interface selector ──
        self.iface_selector = InterfaceSelector(self)
        self.iface_selector.pack(fill="x", pady=(0, 8))

        # ── Action buttons ──
        btn_row = ctk.CTkFrame(self, fg_color="transparent")
        btn_row.pack(fill="x", pady=(0, 0))

        self.start_btn = ctk.CTkButton(
            btn_row, text="🚀 Start Transfer", height=40,
            fg_color=theme.ACCENT_CYAN, hover_color=theme.ACCENT_GREEN,
            text_color=theme.BG_DARK,
            font=ctk.CTkFont(size=theme.FONT_SIZE_MD, weight="bold"),
            corner_radius=10,
            command=self._start,
        )
        self.start_btn.pack(side="left", fill="x", expand=True, padx=(0, 4))

        self.cancel_btn = ctk.CTkButton(
            btn_row, text="✖ Cancel", height=40, width=100,
            fg_color=theme.ACCENT_RED, hover_color="#ff6b6b",
            text_color=theme.TEXT_PRIMARY,
            font=ctk.CTkFont(size=theme.FONT_SIZE_MD, weight="bold"),
            corner_radius=10,
            state="disabled",
            command=self._cancel,
        )
        self.cancel_btn.pack(side="right", padx=(4, 0))

    def _browse(self) -> None:
        path = filedialog.askopenfilename(title="Select File to Send")
        if path:
            self._filepath = path
            p = Path(path)
            size = _format_size(p.stat().st_size)
            self.file_label.configure(
                text=f"📄 {p.name}  ({size})",
                text_color=theme.TEXT_PRIMARY,
            )

    def _start(self) -> None:
        if self._on_start:
            host = self.host_entry.get().strip()
            port_str = self.port_entry.get().strip()
            port = int(port_str) if port_str.isdigit() else 9191
            selected = self.iface_selector.get_selected()
            self._on_start(host, port, self._filepath, selected)

    def _cancel(self) -> None:
        if self._on_cancel:
            self._on_cancel()

    def set_transferring(self, active: bool) -> None:
        if active:
            self.start_btn.configure(state="disabled")
            self.cancel_btn.configure(state="normal")
            self.browse_btn.configure(state="disabled")
        else:
            self.start_btn.configure(state="normal")
            self.cancel_btn.configure(state="disabled")
            self.browse_btn.configure(state="normal")


class ReceivePanel(ctk.CTkFrame):
    """Server-mode controls: port, save dir, start/stop."""

    def __init__(
        self,
        master: ctk.CTkFrame,
        on_start=None,
        on_stop=None,
        **kwargs,
    ):
        super().__init__(master, fg_color="transparent", **kwargs)
        self._on_start = on_start
        self._on_stop = on_stop
        self._save_dir = str(Path.home() / "Downloads")

        # ── Config ──
        config_frame = ctk.CTkFrame(self, fg_color=theme.BG_CARD, corner_radius=theme.CORNER_RADIUS)
        config_frame.pack(fill="x", pady=(0, 8))

        ctk.CTkLabel(
            config_frame, text="Receiver Settings",
            text_color=theme.TEXT_PRIMARY,
            font=ctk.CTkFont(size=theme.FONT_SIZE_MD, weight="bold"),
            anchor="w",
        ).pack(padx=16, pady=(12, 8), anchor="w")

        port_row = ctk.CTkFrame(config_frame, fg_color="transparent")
        port_row.pack(fill="x", padx=16, pady=(0, 8))

        ctk.CTkLabel(
            port_row, text="Listen Port", text_color=theme.TEXT_SECONDARY,
            font=ctk.CTkFont(size=theme.FONT_SIZE_SM), anchor="w",
        ).pack(side="left", padx=(0, 8))

        self.port_entry = ctk.CTkEntry(
            port_row, placeholder_text="9191", width=80,
            fg_color=theme.BG_INPUT, border_color=theme.BORDER,
            text_color=theme.TEXT_PRIMARY,
            font=ctk.CTkFont(size=theme.FONT_SIZE_SM),
            corner_radius=8, height=32,
        )
        self.port_entry.insert(0, "9191")
        self.port_entry.pack(side="left")

        save_row = ctk.CTkFrame(config_frame, fg_color="transparent")
        save_row.pack(fill="x", padx=16, pady=(0, 12))

        ctk.CTkLabel(
            save_row, text="Save to", text_color=theme.TEXT_SECONDARY,
            font=ctk.CTkFont(size=theme.FONT_SIZE_SM), anchor="w",
        ).pack(side="left", padx=(0, 8))

        self.dir_label = ctk.CTkLabel(
            save_row, text=self._save_dir, text_color=theme.TEXT_DIM,
            font=ctk.CTkFont(size=theme.FONT_SIZE_SM), anchor="w",
        )
        self.dir_label.pack(side="left", fill="x", expand=True)

        ctk.CTkButton(
            save_row, text="📁", width=32, height=28,
            fg_color=theme.BORDER, hover_color=theme.BG_CARD_HOVER,
            text_color=theme.TEXT_PRIMARY,
            corner_radius=6,
            command=self._pick_dir,
        ).pack(side="right")

        # ── Interface info ──
        self.iface_info = InterfaceSelector(self)
        self.iface_info.pack(fill="x", pady=(0, 8))

        # ── Action ──
        btn_row = ctk.CTkFrame(self, fg_color="transparent")
        btn_row.pack(fill="x", pady=(0, 0))

        self.start_btn = ctk.CTkButton(
            btn_row, text="📥 Start Listening", height=40,
            fg_color=theme.ACCENT_GREEN, hover_color=theme.ACCENT_CYAN,
            text_color=theme.BG_DARK,
            font=ctk.CTkFont(size=theme.FONT_SIZE_MD, weight="bold"),
            corner_radius=10,
            command=self._start,
        )
        self.start_btn.pack(side="left", fill="x", expand=True, padx=(0, 4))

        self.stop_btn = ctk.CTkButton(
            btn_row, text="⏹ Stop", height=40, width=100,
            fg_color=theme.ACCENT_RED, hover_color="#ff6b6b",
            text_color=theme.TEXT_PRIMARY,
            font=ctk.CTkFont(size=theme.FONT_SIZE_MD, weight="bold"),
            corner_radius=10,
            state="disabled",
            command=self._stop,
        )
        self.stop_btn.pack(side="right", padx=(4, 0))

    def _pick_dir(self) -> None:
        d = filedialog.askdirectory(title="Save received files to...")
        if d:
            self._save_dir = d
            self.dir_label.configure(text=d)

    def _start(self) -> None:
        if self._on_start:
            port_str = self.port_entry.get().strip()
            port = int(port_str) if port_str.isdigit() else 9191
            selected = self.iface_info.get_selected()
            self._on_start(port, self._save_dir, selected)

    def _stop(self) -> None:
        if self._on_stop:
            self._on_stop()

    def set_listening(self, active: bool) -> None:
        if active:
            self.start_btn.configure(state="disabled", text="📥 Listening...")
            self.stop_btn.configure(state="normal")
        else:
            self.start_btn.configure(state="normal", text="📥 Start Listening")
            self.stop_btn.configure(state="disabled")
