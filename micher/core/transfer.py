"""
Core bonded transfer engine.

Opens one TCP connection per local interface, each bound to that interface's IP,
to stripe data across all links simultaneously. Faster links automatically get
more chunks via a shared work-stealing queue.

Supports callbacks for real-time progress monitoring.
"""

from __future__ import annotations

import os
import queue
import socket
import struct
import threading
import time
from pathlib import Path

from .stats import StatsCollector, TransferSnapshot

CHUNK_SIZE = 256 * 1024               # 256 KB per chunk
HEADER_FMT = "!QI"                     # seq (8B) + length (4B)
HEADER_SIZE = struct.calcsize(HEADER_FMT)
END_OF_STREAM = 0xFFFFFFFFFFFFFFFF     # sentinel
FILE_META_SEQ = 0xFFFFFFFFFFFFFFFE     # file metadata sentinel

# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #

def _recv_exact(sock: socket.socket, n: int) -> bytes | None:
    buf = bytearray()
    while len(buf) < n:
        piece = sock.recv(n - len(buf))
        if not piece:
            return None
        buf.extend(piece)
    return bytes(buf)


def _send_chunk(sock: socket.socket, seq: int, chunk: bytes) -> None:
    header = struct.pack(HEADER_FMT, seq, len(chunk))
    sock.sendall(header + chunk)


def _format_size(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} PB"


# --------------------------------------------------------------------------- #
# Sender
# --------------------------------------------------------------------------- #

class BondedSender:
    """
    Sends data to (host, port) simultaneously over every given local interface,
    striping chunks across links. Faster links naturally pull more work.
    """

    def __init__(
        self,
        host: str,
        port: int,
        local_ips: list[str],
        interface_names: dict[str, str] | None = None,
    ):
        if not local_ips:
            raise ValueError("Need at least one local interface IP to bond over")
        self.host = host
        self.port = port
        self.local_ips = local_ips
        self.interface_names = interface_names or {ip: ip for ip in local_ips}
        self.collector: StatsCollector | None = None
        self._cancel = threading.Event()

    def send(
        self,
        data: bytes,
        on_progress: "((TransferSnapshot) -> None) | None" = None,
    ) -> dict[str, int]:
        """
        Splits `data` into chunks and sends over all bonded links in parallel.
        Returns {interface_ip: bytes_sent_on_that_link}.
        """
        self.collector = StatsCollector(
            total_bytes=len(data),
            on_progress=on_progress,
        )
        for ip in self.local_ips:
            self.collector.register_link(self.interface_names.get(ip, ip), ip)

        chunks = [
            (seq, data[i : i + CHUNK_SIZE])
            for seq, i in enumerate(range(0, len(data), CHUNK_SIZE))
        ]
        work_queue: queue.Queue[tuple[int, bytes]] = queue.Queue()
        for item in chunks:
            work_queue.put(item)

        per_link_bytes: dict[str, int] = {ip: 0 for ip in self.local_ips}
        errors: dict[str, str] = {}
        sockets = []

        for ip in self.local_ips:
            try:
                sockets.append(self._connect(ip))
            except OSError as e:
                errors[ip] = str(e)
                sockets.append(None)

        active = [(ip, sock) for ip, sock in zip(self.local_ips, sockets) if sock]
        if not active:
            raise ConnectionError(
                f"Could not connect on any interface: {errors}"
            )

        threads = []
        try:
            for ip, sock in active:
                t = threading.Thread(
                    target=self._worker,
                    args=(ip, sock, work_queue, per_link_bytes),
                    daemon=True,
                )
                threads.append(t)
                t.start()

            for t in threads:
                t.join()

            for _, sock in active:
                _send_chunk(sock, END_OF_STREAM, b"")
        finally:
            for _, sock in active:
                if sock:
                    sock.close()

        if self.collector:
            self.collector.mark_complete()
            self.collector.snapshot()  # fire final callback

        return per_link_bytes

    def send_file(
        self,
        filepath: str | Path,
        on_progress: "((TransferSnapshot) -> None) | None" = None,
    ) -> dict[str, int]:
        """Read a file and send it over bonded links. Sends filename as metadata."""
        path = Path(filepath)
        data = path.read_bytes()

        self.collector = StatsCollector(
            total_bytes=len(data),
            on_progress=on_progress,
        )
        for ip in self.local_ips:
            self.collector.register_link(self.interface_names.get(ip, ip), ip)

        # Prepare file metadata (filename)
        filename_bytes = path.name.encode("utf-8")

        chunks = [
            (seq, data[i : i + CHUNK_SIZE])
            for seq, i in enumerate(range(0, len(data), CHUNK_SIZE))
        ]
        work_queue: queue.Queue[tuple[int, bytes]] = queue.Queue()
        for item in chunks:
            work_queue.put(item)

        per_link_bytes: dict[str, int] = {ip: 0 for ip in self.local_ips}
        sockets = []
        for ip in self.local_ips:
            try:
                sockets.append(self._connect(ip))
            except OSError:
                sockets.append(None)

        active = [(ip, sock) for ip, sock in zip(self.local_ips, sockets) if sock]
        if not active:
            raise ConnectionError("Could not connect on any interface")

        # Send file metadata on the first connection
        _send_chunk(active[0][1], FILE_META_SEQ, filename_bytes)

        threads = []
        try:
            for ip, sock in active:
                t = threading.Thread(
                    target=self._worker,
                    args=(ip, sock, work_queue, per_link_bytes),
                    daemon=True,
                )
                threads.append(t)
                t.start()

            for t in threads:
                t.join()

            for _, sock in active:
                _send_chunk(sock, END_OF_STREAM, b"")
        finally:
            for _, sock in active:
                if sock:
                    sock.close()

        if self.collector:
            self.collector.mark_complete()
            self.collector.snapshot()

        return per_link_bytes

    def cancel(self) -> None:
        self._cancel.set()

    def _connect(self, local_ip: str) -> socket.socket:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 1024 * 1024)
        sock.bind((local_ip, 0))
        sock.connect((self.host, self.port))
        return sock

    def _worker(
        self,
        ip: str,
        sock: socket.socket,
        work_queue: queue.Queue[tuple[int, bytes]],
        per_link_bytes: dict[str, int],
    ) -> None:
        while not self._cancel.is_set():
            try:
                seq, chunk = work_queue.get_nowait()
            except queue.Empty:
                return
            try:
                _send_chunk(sock, seq, chunk)
                per_link_bytes[ip] += len(chunk)
                if self.collector:
                    self.collector.record(ip, len(chunk))
            except OSError:
                # Link died mid-transfer — put chunk back for another link
                work_queue.put((seq, chunk))
                return


# --------------------------------------------------------------------------- #
# Receiver
# --------------------------------------------------------------------------- #

class BondedReceiver:
    """
    Listens on (host, port), accepts `expected_links` simultaneous connections,
    and reassembles the striped chunks into the original byte stream.
    """

    def __init__(
        self,
        host: str,
        port: int,
        expected_links: int,
        on_progress: "((TransferSnapshot) -> None) | None" = None,
    ):
        self.host = host
        self.port = port
        self.expected_links = expected_links
        self.on_progress = on_progress
        self.collector: StatsCollector | None = None
        self.received_filename: str | None = None

    def receive(self) -> bytes:
        """Block until the full payload has been received and reassembled."""
        listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        listener.bind((self.host, self.port))
        listener.listen(self.expected_links)

        conns = [listener.accept()[0] for _ in range(self.expected_links)]
        listener.close()

        self.collector = StatsCollector(on_progress=self.on_progress)
        for i, conn in enumerate(conns):
            peer = conn.getpeername()
            self.collector.register_link(f"link-{i}", peer[0])

        received_chunks: dict[int, bytes] = {}
        chunks_lock = threading.Lock()

        def read_link(idx: int, sock: socket.socket) -> None:
            peer_ip = sock.getpeername()[0]
            try:
                while True:
                    header = _recv_exact(sock, HEADER_SIZE)
                    if header is None:
                        break
                    seq, length = struct.unpack(HEADER_FMT, header)
                    if seq == END_OF_STREAM:
                        break
                    payload = _recv_exact(sock, length)
                    if payload is None:
                        break
                    if seq == FILE_META_SEQ:
                        self.received_filename = payload.decode("utf-8", errors="replace")
                        continue
                    with chunks_lock:
                        received_chunks[seq] = payload
                    if self.collector:
                        self.collector.record(peer_ip, len(payload))
            finally:
                sock.close()

        threads = [
            threading.Thread(target=read_link, args=(i, c), daemon=True)
            for i, c in enumerate(conns)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        ordered = b"".join(received_chunks[seq] for seq in sorted(received_chunks))

        if self.collector:
            self.collector.total_bytes = len(ordered)
            self.collector.mark_complete()
            self.collector.snapshot()

        return ordered

    def receive_file(self, save_dir: str | Path = ".") -> Path:
        """Receive and save to a file. Returns the saved file path."""
        data = self.receive()
        filename = self.received_filename or f"received_{int(time.time())}"
        save_path = Path(save_dir) / filename
        save_path.write_bytes(data)
        return save_path
