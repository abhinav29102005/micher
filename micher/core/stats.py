"""
Real-time transfer statistics engine.

Provides thread-safe stat collection with snapshot-based reads so the GUI/CLI
can poll without blocking the transfer threads.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Callable


@dataclass
class LinkSnapshot:
    """Immutable snapshot of one link's stats at a point in time."""
    name: str
    ip: str
    bytes_transferred: int = 0
    current_bps: float = 0.0         # bytes/sec
    current_mbps: float = 0.0        # megabits/sec
    contribution_pct: float = 0.0    # % of total data this link carried


@dataclass
class TransferSnapshot:
    """Immutable snapshot of the entire transfer's stats."""
    links: list[LinkSnapshot] = field(default_factory=list)
    total_bytes: int = 0               # total payload size
    transferred_bytes: int = 0         # bytes moved so far
    combined_bps: float = 0.0          # aggregate bytes/sec
    combined_mbps: float = 0.0         # aggregate megabits/sec
    progress: float = 0.0             # 0.0 – 1.0
    eta_seconds: float = 0.0          # estimated time remaining
    elapsed_seconds: float = 0.0
    is_complete: bool = False


@dataclass
class _LinkAccumulator:
    """Mutable, per-link bookkeeping (internal use only)."""
    name: str
    ip: str
    total_bytes: int = 0
    window_bytes: int = 0
    window_start: float = field(default_factory=time.monotonic)
    measured_bps: float = 0.0
    lock: threading.Lock = field(default_factory=threading.Lock)

    def record(self, nbytes: int) -> None:
        with self.lock:
            now = time.monotonic()
            self.total_bytes += nbytes
            self.window_bytes += nbytes
            elapsed = now - self.window_start
            if elapsed >= 0.3:
                self.measured_bps = self.window_bytes / elapsed
                self.window_bytes = 0
                self.window_start = now

    def snapshot(self) -> LinkSnapshot:
        with self.lock:
            return LinkSnapshot(
                name=self.name,
                ip=self.ip,
                bytes_transferred=self.total_bytes,
                current_bps=self.measured_bps,
                current_mbps=(self.measured_bps * 8) / 1_000_000,
            )


# Callback type: called on every snapshot update
OnProgress = Callable[[TransferSnapshot], None]


class StatsCollector:
    """
    Thread-safe statistics collector for a bonded transfer.

    Usage:
        collector = StatsCollector(total_bytes=file_size)
        collector.register_link("eth0", "192.168.1.2")
        collector.register_link("wlan0", "192.168.1.3")

        # In transfer worker threads:
        collector.record("192.168.1.2", chunk_size)

        # In UI thread (poll at ~5 Hz):
        snap = collector.snapshot()
    """

    def __init__(
        self,
        total_bytes: int = 0,
        on_progress: OnProgress | None = None,
    ):
        self.total_bytes = total_bytes
        self.on_progress = on_progress
        self._links: dict[str, _LinkAccumulator] = {}
        self._start_time = time.monotonic()
        self._complete = False
        self._lock = threading.Lock()

    def register_link(self, name: str, ip: str) -> None:
        self._links[ip] = _LinkAccumulator(name=name, ip=ip)

    def record(self, ip: str, nbytes: int) -> None:
        """Record bytes sent/received on a specific link. Thread-safe."""
        acc = self._links.get(ip)
        if acc:
            acc.record(nbytes)

    def mark_complete(self) -> None:
        self._complete = True

    def snapshot(self) -> TransferSnapshot:
        """Take a consistent snapshot of all stats. Safe to call from any thread."""
        link_snaps = [acc.snapshot() for acc in self._links.values()]
        transferred = sum(ls.bytes_transferred for ls in link_snaps)
        combined_bps = sum(ls.current_bps for ls in link_snaps)
        combined_mbps = sum(ls.current_mbps for ls in link_snaps)
        elapsed = time.monotonic() - self._start_time

        progress = 0.0
        eta = 0.0
        if self.total_bytes > 0:
            progress = min(transferred / self.total_bytes, 1.0)
            if combined_bps > 0:
                remaining = self.total_bytes - transferred
                eta = remaining / combined_bps

        # Compute contribution percentages
        if transferred > 0:
            for ls in link_snaps:
                ls.contribution_pct = (ls.bytes_transferred / transferred) * 100

        snap = TransferSnapshot(
            links=link_snaps,
            total_bytes=self.total_bytes,
            transferred_bytes=transferred,
            combined_bps=combined_bps,
            combined_mbps=combined_mbps,
            progress=progress,
            eta_seconds=eta,
            elapsed_seconds=elapsed,
            is_complete=self._complete,
        )

        if self.on_progress:
            try:
                self.on_progress(snap)
            except Exception:
                pass  # never let callback errors kill a transfer

        return snap
