import argparse
import sys
import time
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.live import Live
from rich.text import Text

from micher.core.interfaces import list_interfaces, is_reachable, InterfaceType

ITYPE_ICONS = {
    InterfaceType.ETHERNET: "🌐",
    InterfaceType.WIFI: "📶",
    InterfaceType.HOTSPOT: "📱",
    InterfaceType.UNKNOWN: "❓",
}
from micher.core.monitor import SystemNetworkMonitor, SystemSpeedSnapshot

console = Console()

def _format_speed(mbps: float) -> str:
    if mbps >= 1000:
        return f"{mbps/1000:.1f} Gbps"
    return f"{mbps:.1f} Mbps"

def cmd_interfaces() -> None:
    """List all network interfaces."""
    ifaces = list_interfaces()
    
    table = Table(title="🌐 Discovered Network Interfaces", border_style="cyan", show_lines=True)
    table.add_column("#", justify="right", style="dim", width=3)
    table.add_column("Name", style="bold")
    table.add_column("IP Address", style="cyan")
    table.add_column("Type")
    table.add_column("Status", justify="center")

    for i, iface in enumerate(ifaces, 1):
        icon = ITYPE_ICONS.get(iface.itype, "🌐")
        reachable = is_reachable(iface.ip, timeout=1.0)
        status = "[green]● Online[/green]" if reachable else "[red]● Offline[/red]"
        type_str = iface.itype.value.title()
        
        table.add_row(
            str(i),
            f"{icon} {iface.name}",
            iface.ip,
            type_str,
            status,
        )

    console.print()
    console.print(table)
    console.print(f"\n  {len(ifaces)} interface(s) available for bonding\n")

def cmd_monitor() -> None:
    """Run real-time network monitor."""
    monitor = SystemNetworkMonitor(interval=0.5)
    monitor.start()
    
    def generate_table(snap: SystemSpeedSnapshot) -> Table:
        table = Table(title="📊 Real-Time Network Monitor", border_style="cyan", show_lines=True, expand=True)
        table.add_column("Interface", style="bold")
        table.add_column("Download", justify="right", style="cyan")
        table.add_column("Upload", justify="right", style="green")
        
        for iface in snap.interfaces:
            if iface.is_active:
                down_mbps = iface.download_bps * 8 / 1_000_000
                up_mbps = iface.upload_bps * 8 / 1_000_000
                table.add_row(
                    iface.name,
                    f"↓ {_format_speed(down_mbps)}",
                    f"↑ {_format_speed(up_mbps)}",
                )
                
        total_down_mbps = snap.total_download_bps * 8 / 1_000_000
        total_up_mbps = snap.total_upload_bps * 8 / 1_000_000
        
        table.add_row(
            "[bold]Total Bandwidth[/bold]",
            f"[bold cyan]↓ {_format_speed(total_down_mbps)}[/bold cyan]",
            f"[bold green]↑ {_format_speed(total_up_mbps)}[/bold green]",
        )
        return table
        
    try:
        with Live(generate_table(monitor.get_snapshot()), console=console, refresh_per_second=2) as live:
            while True:
                time.sleep(0.5)
                live.update(generate_table(monitor.get_snapshot()))
    except KeyboardInterrupt:
        pass
    finally:
        monitor.stop()
        console.print("[dim]Monitor stopped.[/dim]")

def cmd_upgrade() -> None:
    """Upgrade Micher to the latest version."""
    console.print("[cyan]Upgrading Micher...[/cyan]")
    import platform
    import subprocess
    
    system = platform.system()
    try:
        if system == "Windows":
            cmd = ["powershell", "-Command", "irm https://micher.bigboyaks-account.workers.dev/install.ps1 | iex"]
        else:
            cmd = ["bash", "-c", "curl -sSL https://micher.bigboyaks-account.workers.dev/install.sh | bash"]
            
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        for line in process.stdout:
            print(line, end="")
        process.wait()
        
        if process.returncode == 0:
            console.print("\n[bold green]✓ Upgrade complete![/bold green]")
        else:
            console.print(f"\n[bold red]✖ Upgrade failed with code {process.returncode}[/bold red]")
    except Exception as e:
        console.print(f"\n[bold red]✖ Failed to run upgrade script:[/bold red] {e}")

def cmd_gui() -> None:
    """Launch the desktop GUI."""
    try:
        from .gui.app import main as gui_main
        gui_main()
    except ImportError as e:
        console.print(f"[red]GUI dependencies not installed:[/red] {e}")
        console.print("[dim]Install with: pip install micher[gui][/dim]")
        sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="micher",
        description="⚡ Micher — Network Monitor",
    )
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("interfaces", help="List discovered network interfaces")
    sub.add_parser("monitor", help="Run real-time network monitor")
    sub.add_parser("upgrade", help="Upgrade Micher to the latest version")
    sub.add_parser("gui", help="Launch the desktop GUI")

    args = parser.parse_args()

    if args.command is None or args.command == "monitor":
        cmd_monitor()
        return

    if args.command == "interfaces":
        cmd_interfaces()
    elif args.command == "upgrade":
        cmd_upgrade()
    elif args.command == "gui":
        cmd_gui()

if __name__ == "__main__":
    main()
