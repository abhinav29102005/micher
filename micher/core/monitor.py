
import time
import threading
import psutil
from typing import Dict, List, Optional
from dataclasses import dataclass
from .interfaces import list_interfaces

@dataclass
class InterfaceSpeed:
    name: str
    download_bps: float
    upload_bps: float
    is_active: bool

@dataclass
class SystemSpeedSnapshot:
    total_download_bps: float
    total_upload_bps: float
    interfaces: List[InterfaceSpeed]

class SystemNetworkMonitor:
    def __init__(self, interval: float = 0.5):
        self.interval = interval
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        self._last_snapshot: Optional[SystemSpeedSnapshot] = None
        self._last_io_counters: Dict[str, tuple] = {}
        self._last_time = time.monotonic()

    def start(self):
        if self._running:
            return
        self._running = True
        
        io_counters = psutil.net_io_counters(pernic=True)
        for name, stats in io_counters.items():
            self._last_io_counters[name] = (stats.bytes_recv, stats.bytes_sent)
        self._last_time = time.monotonic()
        
        self._thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=2.0)

    def _monitor_loop(self):
        while self._running:
            time.sleep(self.interval)
            
            now = time.monotonic()
            elapsed = now - self._last_time
            if elapsed <= 0:
                continue
                
            io_counters = psutil.net_io_counters(pernic=True)
            active_interfaces = list_interfaces()
            
            total_down = 0.0
            total_up = 0.0
            interface_speeds = []
            
            for iface in active_interfaces:
                name = iface.name
                if name in io_counters:
                    stats = io_counters[name]
                    curr_recv = stats.bytes_recv
                    curr_sent = stats.bytes_sent
                    
                    if name in self._last_io_counters:
                        prev_recv, prev_sent = self._last_io_counters[name]
                        down_bps = max(0, curr_recv - prev_recv) / elapsed
                        up_bps = max(0, curr_sent - prev_sent) / elapsed
                    else:
                        down_bps = 0.0
                        up_bps = 0.0
                        
                    total_down += down_bps
                    total_up += up_bps
                    
                    is_active = (down_bps > 1024) or (up_bps > 1024)
                    
                    interface_speeds.append(InterfaceSpeed(
                        name=name,
                        download_bps=down_bps,
                        upload_bps=up_bps,
                        is_active=is_active
                    ))
                    
                    self._last_io_counters[name] = (curr_recv, curr_sent)
            
            self._last_time = now
            
            snapshot = SystemSpeedSnapshot(
                total_download_bps=total_down,
                total_upload_bps=total_up,
                interfaces=interface_speeds
            )
            
            with self._lock:
                self._last_snapshot = snapshot

    def get_snapshot(self) -> SystemSpeedSnapshot:
        with self._lock:
            if self._last_snapshot:
                return self._last_snapshot
            return SystemSpeedSnapshot(0.0, 0.0, [])
