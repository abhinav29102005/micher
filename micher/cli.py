"""
Micher CLI — beautiful terminal interface with real-time speed dashboard.

Usage:
    micher interfaces          List discovered network interfaces
    micher send <host> <file>  Send a file over bonded links
    micher receive [--port N]  Start server and receive
    micher gui                 Launch the desktop GUI
"""

from __future__ import annotations

import argparse
import sys
import threading
import time
from pathlib import Path

from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.progress import BarColumn, DownloadColumn, Progress, SpinnerColumn, TextColumn, TimeRemainingColumn, TransferSpeedColumn
from rich.table import Table
from rich.text import Text
from rich import box

from .core.interfaces import list_interfaces, is_reachable, InterfaceType
from .core.transfer import BondedSender, BondedReceiver
from .core.stats import TransferSnapshot

console = Console()

ITYPE_COLORS = {
    InterfaceType.ETHERNET: "bold blue",
    InterfaceType.WIFI: "bold green",
    InterfaceType.HOTSPOT: "bold yellow",
    InterfaceType.UNKNOWN: "bold white",
}

ITYPE_ICONS = {
    InterfaceType.ETHERNET: "🔌",
    InterfaceType.WIFI: "📶",
    InterfaceType.HOTSPOT: "📱",
    InterfaceType.UNKNOWN: "🌐",
}


def _format_speed(mbps: float) -> str:
    if mbps >= 1000:
        return f"{mbps / 1000:.2f} Gbps"
    if mbps >= 1:
        return f"{mbps:.1f} Mbps"
    return f"{mbps * 1000:.0f} Kbps"


def _format_size(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} PB"


def _format_eta(seconds: float) -> str:
    if seconds <= 0 or seconds > 86400:
        return "--:--"
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


def cmd_interfaces() -> None:
    """List all discovered network interfaces."""
    ifaces = list_interfaces()
    if not ifaces:
        console.print("[red]No active network interfaces found.[/red]")
        return

    table = Table(
        title="🌐 Discovered Network Interfaces",
        box=box.ROUNDED,
        title_style="bold cyan",
        border_style="dim",
    )
    table.add_column("#", style="dim", width=3)
    table.add_column("Name", style="bold")
    table.add_column("IP Address", style="cyan")
    table.add_column("Type", style="green")
    table.add_column("Status", justify="center")

    for i, iface in enumerate(ifaces, 1):
        icon = ITYPE_ICONS.get(iface.itype, "🌐")
        color = ITYPE_COLORS.get(iface.itype, "white")
        reachable = is_reachable(iface.ip, timeout=1.5)
        status = "[green]● Online[/green]" if reachable else "[red]● Offline[/red]"
        table.add_row(
            str(i),
            f"{icon} [{color}]{iface.name}[/{color}]",
            iface.ip,
            iface.itype.value.title(),
            status,
        )

    console.print()
    console.print(table)
    console.print(f"\n  [dim]{len(ifaces)} interface(s) available for bonding[/dim]\n")


def _build_dashboard(snap: TransferSnapshot | None) -> Table:
    """Build a rich table dashboard from a transfer snapshot."""
    grid = Table.grid(padding=(0, 2))
    grid.add_column(ratio=1)

    if snap is None:
        grid.add_row("[dim]Waiting for transfer data...[/dim]")
        return grid

    # Speed header
    speed_text = Text()
    speed_text.append("⚡ ", style="yellow")
    speed_text.append(_format_speed(snap.combined_mbps), style="bold cyan")
    speed_text.append("  combined", style="dim")
    grid.add_row(speed_text)
    grid.add_row("")

    # Per-link table
    link_table = Table(
        box=box.SIMPLE_HEAD,
        border_style="dim",
        show_edge=False,
        pad_edge=False,
    )
    link_table.add_column("Interface", style="bold", min_width=18)
    link_table.add_column("Speed", justify="right", style="cyan", min_width=12)
    link_table.add_column("Sent", justify="right", style="green", min_width=10)
    link_table.add_column("Share", justify="right", style="yellow", min_width=8)
    link_table.add_column("Bar", min_width=20)

    max_bps = max((ls.current_bps for ls in snap.links), default=1) or 1
    for ls in snap.links:
        bar_width = int(20 * ls.current_bps / max_bps) if max_bps > 0 else 0
        bar = "█" * bar_width + "░" * (20 - bar_width)
        link_table.add_row(
            ls.name,
            _format_speed(ls.current_mbps),
            _format_size(ls.bytes_transferred),
            f"{ls.contribution_pct:.0f}%",
            f"[cyan]{bar}[/cyan]",
        )

    grid.add_row(link_table)
    grid.add_row("")

    # Progress
    pct = snap.progress * 100
    filled = int(40 * snap.progress)
    prog_bar = f"[cyan]{'━' * filled}[/cyan][dim]{'─' * (40 - filled)}[/dim]"
    progress_line = Text()
    progress_line.append(f"  {prog_bar}  {pct:.1f}%")
    grid.add_row(progress_line)

    info_line = Text()
    info_line.append(f"  {_format_size(snap.transferred_bytes)}", style="green")
    info_line.append(f" / {_format_size(snap.total_bytes)}", style="dim")
    info_line.append(f"   ETA: {_format_eta(snap.eta_seconds)}", style="yellow")
    info_line.append(f"   Elapsed: {_format_eta(snap.elapsed_seconds)}", style="dim")
    grid.add_row(info_line)

    return grid


def cmd_send(host: str, filepath: str, port: int = 9191) -> None:
    """Send a file over bonded links with real-time dashboard."""
    path = Path(filepath)
    if not path.exists():
        console.print(f"[red]File not found:[/red] {filepath}")
        sys.exit(1)

    ifaces = list_interfaces()
    reachable = [i for i in ifaces if is_reachable(i.ip, timeout=1.5)]
    if not reachable:
        console.print("[red]No reachable interfaces found![/red]")
        sys.exit(1)

    local_ips = [i.ip for i in reachable]
    names = {i.ip: f"{ITYPE_ICONS.get(i.itype, '🌐')} {i.name}" for i in reachable}

    file_size = path.stat().st_size
    console.print()
    console.print(Panel(
        f"[bold]Sending[/bold] [cyan]{path.name}[/cyan] ({_format_size(file_size)})\n"
        f"[bold]To[/bold]      [cyan]{host}:{port}[/cyan]\n"
        f"[bold]Links[/bold]   {len(reachable)} bonded interface(s)",
        title="🚀 [bold cyan]Micher Transfer[/bold cyan]",
        border_style="cyan",
        padding=(1, 2),
    ))
    console.print()

    latest_snap: list[TransferSnapshot | None] = [None]

    def on_progress(snap: TransferSnapshot) -> None:
        latest_snap[0] = snap

    sender = BondedSender(host, port, local_ips, interface_names=names)

    # Run transfer in background thread
    result: dict[str, int] = {}
    error: list[Exception] = []

    def do_send() -> None:
        nonlocal result
        try:
            result = sender.send_file(filepath, on_progress=on_progress)
        except Exception as e:
            error.append(e)

    t = threading.Thread(target=do_send, daemon=True)
    t.start()

    with Live(
        Panel(
            _build_dashboard(None),
            title="📊 [bold]Live Transfer Dashboard[/bold]",
            border_style="blue",
            padding=(1, 2),
        ),
        console=console,
        refresh_per_second=5,
    ) as live:
        while t.is_alive():
            live.update(Panel(
                _build_dashboard(latest_snap[0]),
                title="📊 [bold]Live Transfer Dashboard[/bold]",
                border_style="blue",
                padding=(1, 2),
            ))
            time.sleep(0.2)

        # Final update
        live.update(Panel(
            _build_dashboard(latest_snap[0]),
            title="✅ [bold green]Transfer Complete[/bold green]",
            border_style="green",
            padding=(1, 2),
        ))

    if error:
        console.print(f"\n[red]Transfer failed:[/red] {error[0]}")
        sys.exit(1)

    snap = latest_snap[0]
    if snap:
        avg_mbps = (snap.total_bytes * 8 / 1_000_000) / snap.elapsed_seconds if snap.elapsed_seconds > 0 else 0
        console.print(f"\n  [green]✓[/green] Sent [cyan]{_format_size(snap.total_bytes)}[/cyan] in [yellow]{_format_eta(snap.elapsed_seconds)}[/yellow]  (avg [cyan]{_format_speed(avg_mbps)}[/cyan])")
    console.print()


def cmd_receive(port: int = 9191, save_dir: str = ".") -> None:
    """Start receiver server with real-time dashboard."""
    ifaces = list_interfaces()
    n_links = max(len(ifaces), 1)

    console.print()
    console.print(Panel(
        f"[bold]Listening on[/bold]  [cyan]0.0.0.0:{port}[/cyan]\n"
        f"[bold]Expecting[/bold]    [cyan]{n_links}[/cyan] bonded connection(s)\n"
        f"[bold]Save to[/bold]      [cyan]{Path(save_dir).resolve()}[/cyan]",
        title="📥 [bold cyan]Micher Receiver[/bold cyan]",
        border_style="cyan",
        padding=(1, 2),
    ))
    console.print("[dim]  Waiting for sender to connect...[/dim]\n")

    latest_snap: list[TransferSnapshot | None] = [None]

    def on_progress(snap: TransferSnapshot) -> None:
        latest_snap[0] = snap

    receiver = BondedReceiver("0.0.0.0", port, expected_links=n_links, on_progress=on_progress)

    saved_path: list[Path] = []
    error: list[Exception] = []

    def do_receive() -> None:
        try:
            p = receiver.receive_file(save_dir)
            saved_path.append(p)
        except Exception as e:
            error.append(e)

    t = threading.Thread(target=do_receive, daemon=True)
    t.start()

    with Live(
        Panel("[dim]Awaiting data...[/dim]", title="📊 [bold]Receive Dashboard[/bold]", border_style="blue", padding=(1, 2)),
        console=console,
        refresh_per_second=5,
    ) as live:
        while t.is_alive():
            live.update(Panel(
                _build_dashboard(latest_snap[0]),
                title="📊 [bold]Receive Dashboard[/bold]",
                border_style="blue",
                padding=(1, 2),
            ))
            time.sleep(0.2)

        live.update(Panel(
            _build_dashboard(latest_snap[0]),
            title="✅ [bold green]Receive Complete[/bold green]",
            border_style="green",
            padding=(1, 2),
        ))

    if error:
        console.print(f"\n[red]Receive failed:[/red] {error[0]}")
        sys.exit(1)

    if saved_path:
        console.print(f"\n  [green]✓[/green] Saved to [cyan]{saved_path[0]}[/cyan]")
    console.print()


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
        description="⚡ Micher — Multi-link network bonding for maximum transfer speed",
    )
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("interfaces", help="List discovered network interfaces")
    sub.add_parser("gui", help="Launch the desktop GUI")

    send_p = sub.add_parser("send", help="Send a file over bonded links")
    send_p.add_argument("host", help="Server hostname or IP")
    send_p.add_argument("file", help="File to send")
    send_p.add_argument("--port", type=int, default=9191, help="Server port (default: 9191)")

    recv_p = sub.add_parser("receive", help="Start receiver server")
    recv_p.add_argument("--port", type=int, default=9191, help="Listen port (default: 9191)")
    recv_p.add_argument("--save-dir", default=".", help="Directory to save received files")

    args = parser.parse_args()

    if args.command is None:
        # Default: show banner + interfaces
        console.print()
        console.print(Panel(
            "[bold cyan]⚡ Micher[/bold cyan] — Multi-link network bonding\n\n"
            "[dim]Combine Ethernet + WiFi + Hotspot for maximum transfer speed[/dim]",
            border_style="cyan",
            padding=(1, 3),
        ))
        cmd_interfaces()
        console.print("[dim]  Run [bold]micher --help[/bold] for all commands[/dim]\n")
        return

    if args.command == "interfaces":
        cmd_interfaces()
    elif args.command == "send":
        cmd_send(args.host, args.file, args.port)
    elif args.command == "receive":
        cmd_receive(args.port, args.save_dir)
    elif args.command == "gui":
        cmd_gui()


if __name__ == "__main__":
    main()
