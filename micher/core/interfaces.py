"""
Cross-platform (Windows/Linux) discovery of local network interfaces and their
IPv4 addresses, so we know which local IP to bind a socket to in order to force
traffic out over a specific physical interface (Ethernet, WiFi #1, WiFi #2, ...).

Uses only the Python standard library — no admin/root privileges required.
"""

from __future__ import annotations

import platform
import re
import socket
import subprocess
from dataclasses import dataclass
from enum import Enum


class InterfaceType(Enum):
    ETHERNET = "ethernet"
    WIFI = "wifi"
    HOTSPOT = "hotspot"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class Interface:
    name: str          # human-readable interface name, e.g. "Ethernet", "wlan0"
    ip: str            # local IPv4 address bound to this interface
    itype: InterfaceType = InterfaceType.UNKNOWN

    @property
    def label(self) -> str:
        """Short display label like 'WiFi (192.168.1.5)'."""
        return f"{self.name} ({self.ip})"


def _guess_type(name: str) -> InterfaceType:
    """Best-effort guess of interface type from its OS name."""
    low = name.lower()
    if any(k in low for k in ("wlan", "wifi", "wi-fi", "wireless", "wlp")):
        return InterfaceType.WIFI
    if any(k in low for k in ("eth", "enp", "eno", "ethernet", "realtek", "intel")):
        return InterfaceType.ETHERNET
    if any(k in low for k in ("usb", "rndis", "tether", "ap", "hotspot")):
        return InterfaceType.HOTSPOT
    return InterfaceType.UNKNOWN


def list_interfaces() -> list[Interface]:
    """
    Return all active, non-loopback IPv4 interfaces on this machine.

    Shells out to the OS's own tool (`ipconfig` on Windows, `ip addr` on Linux)
    so this script has zero external dependencies.
    """
    system = platform.system()
    if system == "Windows":
        return _list_interfaces_windows()
    elif system == "Linux":
        return _list_interfaces_linux()
    else:
        raise RuntimeError(f"Unsupported platform: {system} (Windows/Linux only)")


def _list_interfaces_windows() -> list[Interface]:
    output = subprocess.run(
        ["ipconfig"], capture_output=True, text=True, check=True
    ).stdout

    interfaces: list[Interface] = []
    current_name = None
    for line in output.splitlines():
        line = line.rstrip()
        if line and not line.startswith(" ") and line.endswith(":"):
            current_name = line[:-1].strip()
        else:
            match = re.search(r"IPv4 Address[.\s]*:\s*([\d.]+)", line)
            if match and current_name:
                ip = match.group(1)
                if not ip.startswith("127."):
                    interfaces.append(Interface(
                        name=current_name,
                        ip=ip,
                        itype=_guess_type(current_name),
                    ))
    return interfaces


def _list_interfaces_linux() -> list[Interface]:
    try:
        output = subprocess.run(
            ["ip", "-4", "addr", "show"], capture_output=True, text=True, check=True
        ).stdout
    except FileNotFoundError:
        return _list_interfaces_fallback()

    interfaces: list[Interface] = []
    current_name = None
    for line in output.splitlines():
        header = re.match(r"^\d+:\s+([^:]+):", line)
        if header:
            current_name = header.group(1).strip()
            continue
        addr = re.search(r"inet\s+([\d.]+)/\d+", line)
        if addr and current_name and current_name != "lo":
            interfaces.append(Interface(
                name=current_name,
                ip=addr.group(1),
                itype=_guess_type(current_name),
            ))
    return interfaces


def _list_interfaces_fallback() -> list[Interface]:
    """
    Stdlib-only fallback: finds the single IP the OS would use to reach the
    internet. Does NOT enumerate multiple physical interfaces.
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("8.8.8.8", 80))
        ip = sock.getsockname()[0]
        return [Interface(name="default", ip=ip)]
    except OSError:
        return []
    finally:
        sock.close()


def is_reachable(ip: str, timeout: float = 2.0) -> bool:
    """Quick check that a bound-socket path can actually reach the outside world."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.bind((ip, 0))
        s.settimeout(timeout)
        s.connect(("8.8.8.8", 53))
        s.close()
        return True
    except OSError:
        return False


if __name__ == "__main__":
    print("Discovered interfaces:")
    for iface in list_interfaces():
        reachable = is_reachable(iface.ip)
        status = "reachable" if reachable else "NOT reachable"
        print(f"  {iface.name:20s} {iface.ip:16s} [{iface.itype.value}] [{status}]")
