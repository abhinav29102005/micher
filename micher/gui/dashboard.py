"""
Real-time speed monitoring dashboard widget.

Renders:
  - Per-interface speed bars with colors + live Mbps
  - Combined speed arc gauge
  - Rolling 30-second throughput graph (Canvas-drawn, no matplotlib)
  - Transfer progress bar with ETA
  - Per-link contribution percentages
"""

from __future__ import annotations

import math
import time
import tkinter as tk
from collections import deque
from typing import TYPE_CHECKING

import customtkinter as ctk

from . import theme

if TYPE_CHECKING:
    from ..core.stats import TransferSnapshot


def _format_speed(mbps: float) -> str:
    if mbps >= 1000:
        return f"{mbps / 1000:.2f} Gbps"
    if mbps >= 1:
        return f"{mbps:.1f} Mbps"
    return f"{mbps * 1000:.0f} Kbps"


def _format_size(n: int) -> str:
    v = float(n)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if v < 1024:
            return f"{v:.1f} {unit}"
        v /= 1024
    return f"{v:.1f} PB"


def _format_eta(seconds: float) -> str:
    if seconds <= 0 or seconds > 86400:
        return "--:--"
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


class SpeedGauge(ctk.CTkCanvas):
    """
    Circular arc gauge showing the combined transfer speed.
    Draws an arc from 0 to current speed, with glowing accent color.
    """

    def __init__(self, master: ctk.CTkFrame, size: int = 180, **kwargs):
        super().__init__(
            master, width=size, height=size,
            bg=theme.BG_CARD, highlightthickness=0, **kwargs,
        )
        self.size = size
        self._mbps = 0.0
        self._max_mbps = 100.0  # auto-scales
        self._draw()

    def update_speed(self, mbps: float) -> None:
        self._mbps = mbps
        if mbps > self._max_mbps * 0.9:
            self._max_mbps = mbps * 1.3
        self._draw()

    def _draw(self) -> None:
        self.delete("all")
        cx, cy = self.size // 2, self.size // 2
        r = self.size // 2 - 15
        pad = 15

        # Background arc (track)
        self.create_arc(
            pad, pad, self.size - pad, self.size - pad,
            start=225, extent=-270, style="arc",
            outline=theme.BORDER, width=10,
        )

        # Value arc
        ratio = min(self._mbps / self._max_mbps, 1.0) if self._max_mbps > 0 else 0
        extent = -270 * ratio
        color = theme.ACCENT_CYAN if ratio < 0.8 else theme.ACCENT_GREEN
        if extent != 0:
            self.create_arc(
                pad, pad, self.size - pad, self.size - pad,
                start=225, extent=extent, style="arc",
                outline=color, width=10,
            )

        # Center text
        self.create_text(
            cx, cy - 8,
            text=_format_speed(self._mbps),
            fill=theme.TEXT_PRIMARY,
            font=("Segoe UI", 16, "bold"),
        )
        self.create_text(
            cx, cy + 16,
            text="combined",
            fill=theme.TEXT_SECONDARY,
            font=("Segoe UI", 10),
        )


class ThroughputGraph(ctk.CTkCanvas):
    """
    Rolling 30-second line chart showing per-link throughput over time.
    Drawn on a Canvas — no matplotlib dependency.
    """

    def __init__(self, master: ctk.CTkFrame, width: int = 400, height: int = 140, **kwargs):
        super().__init__(
            master, width=width, height=height,
            bg=theme.BG_CARD, highlightthickness=0, **kwargs,
        )
        self.w = width
        self.h = height
        self._history: dict[str, deque[float]] = {}   # ip -> deque of mbps
        self._colors: dict[str, str] = {}
        self._max_points = 150  # 30 seconds at 5 Hz
        self._color_idx = 0

    def record(self, ip: str, mbps: float) -> None:
        if ip not in self._history:
            self._history[ip] = deque(maxlen=self._max_points)
            self._colors[ip] = theme.GRAPH_COLORS[self._color_idx % len(theme.GRAPH_COLORS)]
            self._color_idx += 1
        self._history[ip].append(mbps)
        self._draw()

    def _draw(self) -> None:
        self.delete("all")
        pad_l, pad_r, pad_t, pad_b = 5, 5, 5, 5
        gw = self.w - pad_l - pad_r
        gh = self.h - pad_t - pad_b

        # Grid lines
        for i in range(5):
            y = pad_t + int(gh * i / 4)
            self.create_line(pad_l, y, pad_l + gw, y, fill=theme.TEXT_DIM, dash=(2, 4))

        # Find global max for scaling
        all_vals = [v for q in self._history.values() for v in q]
        max_val = max(all_vals) if all_vals else 1.0
        max_val = max(max_val, 1.0) * 1.1

        # Draw each link's line
        for ip, history in self._history.items():
            if len(history) < 2:
                continue
            color = self._colors[ip]
            points = []
            for i, val in enumerate(history):
                x = pad_l + int(gw * i / (self._max_points - 1))
                y = pad_t + gh - int(gh * val / max_val)
                points.append((x, y))

            # Smooth line
            flat = [coord for pt in points for coord in pt]
            if len(flat) >= 4:
                self.create_line(*flat, fill=color, width=2, smooth=True)


class LinkBars(ctk.CTkFrame):
    """Per-interface speed bars with live Mbps labels."""

    def __init__(self, master: ctk.CTkFrame, **kwargs):
        super().__init__(master, fg_color=theme.BG_CARD, corner_radius=theme.CORNER_RADIUS, **kwargs)
        self._bars: dict[str, dict] = {}  # ip -> {name_lbl, speed_lbl, bar, pct_lbl}

    def update_links(self, links: list) -> None:
        max_bps = max((ls.current_bps for ls in links), default=1) or 1

        for ls in links:
            key = ls.ip
            if key not in self._bars:
                self._create_bar(key, ls.name)

            widgets = self._bars[key]
            widgets["speed_lbl"].configure(text=_format_speed(ls.current_mbps))
            ratio = min(ls.current_bps / max_bps, 1.0) if max_bps > 0 else 0
            widgets["bar"].set(ratio)
            widgets["pct_lbl"].configure(text=f"{ls.contribution_pct:.0f}%")
            widgets["sent_lbl"].configure(text=_format_size(ls.bytes_transferred))

    def _create_bar(self, ip: str, name: str) -> None:
        row = len(self._bars)
        color = theme.GRAPH_COLORS[row % len(theme.GRAPH_COLORS)]

        name_lbl = ctk.CTkLabel(
            self, text=name, text_color=color,
            font=ctk.CTkFont(size=theme.FONT_SIZE_SM, weight="bold"),
            anchor="w",
        )
        name_lbl.grid(row=row, column=0, padx=(12, 8), pady=6, sticky="w")

        bar = ctk.CTkProgressBar(
            self, width=200, height=14,
            progress_color=color,
            fg_color=theme.BORDER,
            corner_radius=7,
        )
        bar.set(0)
        bar.grid(row=row, column=1, padx=4, pady=6)

        speed_lbl = ctk.CTkLabel(
            self, text="0 Kbps", text_color=theme.TEXT_PRIMARY,
            font=ctk.CTkFont(size=theme.FONT_SIZE_SM),
            width=90, anchor="e",
        )
        speed_lbl.grid(row=row, column=2, padx=4, pady=6)

        sent_lbl = ctk.CTkLabel(
            self, text="0 B", text_color=theme.TEXT_SECONDARY,
            font=ctk.CTkFont(size=theme.FONT_SIZE_XS),
            width=70, anchor="e",
        )
        sent_lbl.grid(row=row, column=3, padx=4, pady=6)

        pct_lbl = ctk.CTkLabel(
            self, text="0%", text_color=theme.ACCENT_YELLOW,
            font=ctk.CTkFont(size=theme.FONT_SIZE_SM, weight="bold"),
            width=40, anchor="e",
        )
        pct_lbl.grid(row=row, column=4, padx=(4, 12), pady=6)

        self._bars[ip] = {
            "name_lbl": name_lbl,
            "speed_lbl": speed_lbl,
            "bar": bar,
            "pct_lbl": pct_lbl,
            "sent_lbl": sent_lbl,
        }


class DashboardPanel(ctk.CTkFrame):
    """
    Complete real-time dashboard panel combining all monitoring widgets.
    Call `update(snapshot)` at 5 Hz from the main app.
    """

    def __init__(self, master: ctk.CTkFrame, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)

        # ── Header ──
        header = ctk.CTkFrame(self, fg_color=theme.BG_CARD, corner_radius=theme.CORNER_RADIUS)
        header.pack(fill="x", padx=0, pady=(0, 8))

        self.status_label = ctk.CTkLabel(
            header, text="⚡ Idle", text_color=theme.TEXT_SECONDARY,
            font=ctk.CTkFont(size=theme.FONT_SIZE_LG, weight="bold"),
            anchor="w",
        )
        self.status_label.pack(side="left", padx=16, pady=12)

        self.file_label = ctk.CTkLabel(
            header, text="", text_color=theme.TEXT_DIM,
            font=ctk.CTkFont(size=theme.FONT_SIZE_SM),
            anchor="e",
        )
        self.file_label.pack(side="right", padx=16, pady=12)

        # ── Middle row: gauge + graph ──
        mid = ctk.CTkFrame(self, fg_color="transparent")
        mid.pack(fill="x", padx=0, pady=(0, 8))

        gauge_frame = ctk.CTkFrame(mid, fg_color=theme.BG_CARD, corner_radius=theme.CORNER_RADIUS)
        gauge_frame.pack(side="left", padx=(0, 4), pady=0, fill="y")

        self.gauge = SpeedGauge(gauge_frame, size=180)
        self.gauge.pack(padx=16, pady=16)

        graph_frame = ctk.CTkFrame(mid, fg_color=theme.BG_CARD, corner_radius=theme.CORNER_RADIUS)
        graph_frame.pack(side="left", padx=(4, 0), pady=0, fill="both", expand=True)

        graph_title = ctk.CTkLabel(
            graph_frame, text="Throughput (30s)", text_color=theme.TEXT_SECONDARY,
            font=ctk.CTkFont(size=theme.FONT_SIZE_XS),
            anchor="w",
        )
        graph_title.pack(padx=12, pady=(8, 0), anchor="w")

        self.graph = ThroughputGraph(graph_frame, width=450, height=140)
        self.graph.pack(padx=12, pady=(4, 12), fill="both", expand=True)

        # ── Link bars ──
        self.link_bars = LinkBars(self)
        self.link_bars.pack(fill="x", padx=0, pady=(0, 8))

        # ── Progress bar ──
        prog_frame = ctk.CTkFrame(self, fg_color=theme.BG_CARD, corner_radius=theme.CORNER_RADIUS)
        prog_frame.pack(fill="x", padx=0, pady=(0, 0))

        self.progress_bar = ctk.CTkProgressBar(
            prog_frame, height=18,
            progress_color=theme.ACCENT_CYAN,
            fg_color=theme.BORDER,
            corner_radius=9,
        )
        self.progress_bar.set(0)
        self.progress_bar.pack(fill="x", padx=16, pady=(12, 4))

        info_row = ctk.CTkFrame(prog_frame, fg_color="transparent")
        info_row.pack(fill="x", padx=16, pady=(0, 12))

        self.transferred_lbl = ctk.CTkLabel(
            info_row, text="0 B / 0 B", text_color=theme.TEXT_SECONDARY,
            font=ctk.CTkFont(size=theme.FONT_SIZE_SM), anchor="w",
        )
        self.transferred_lbl.pack(side="left")

        self.eta_lbl = ctk.CTkLabel(
            info_row, text="ETA: --:--", text_color=theme.ACCENT_YELLOW,
            font=ctk.CTkFont(size=theme.FONT_SIZE_SM), anchor="e",
        )
        self.eta_lbl.pack(side="right")

        self.elapsed_lbl = ctk.CTkLabel(
            info_row, text="", text_color=theme.TEXT_DIM,
            font=ctk.CTkFont(size=theme.FONT_SIZE_SM), anchor="e",
        )
        self.elapsed_lbl.pack(side="right", padx=(0, 16))

    def update(self, snap: TransferSnapshot) -> None:
        """Update all widgets from a stats snapshot. Call from main thread."""
        # Status
        if snap.is_complete:
            self.status_label.configure(text="✅ Transfer Complete", text_color=theme.ACCENT_GREEN)
        elif snap.combined_mbps > 0:
            self.status_label.configure(
                text=f"⚡ {_format_speed(snap.combined_mbps)}",
                text_color=theme.ACCENT_CYAN,
            )

        # Gauge
        self.gauge.update_speed(snap.combined_mbps)

        # Graph
        for ls in snap.links:
            self.graph.record(ls.ip, ls.current_mbps)

        # Link bars
        self.link_bars.update_links(snap.links)

        # Progress
        self.progress_bar.set(snap.progress)
        self.transferred_lbl.configure(
            text=f"{_format_size(snap.transferred_bytes)} / {_format_size(snap.total_bytes)}"
        )
        self.eta_lbl.configure(text=f"ETA: {_format_eta(snap.eta_seconds)}")
        self.elapsed_lbl.configure(text=f"Elapsed: {_format_eta(snap.elapsed_seconds)}")

    def set_idle(self) -> None:
        self.status_label.configure(text="⚡ Idle", text_color=theme.TEXT_SECONDARY)
        self.gauge.update_speed(0)
        self.progress_bar.set(0)
        self.transferred_lbl.configure(text="0 B / 0 B")
        self.eta_lbl.configure(text="ETA: --:--")
        self.elapsed_lbl.configure(text="")
