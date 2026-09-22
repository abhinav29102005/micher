
import logging
import select
import socket
import struct
import threading
from typing import Callable

from .interfaces import list_interfaces, is_reachable

# Basic SOCKS5 constants
SOCKS_VERSION = 5
RSV = 0
ATYP_IPV4 = 1
ATYP_DOMAINNAME = 3
ATYP_IPV6 = 4
CMD_CONNECT = 1

logger = logging.getLogger(__name__)

class BondingSocks5Proxy:
    def __init__(self, host: str = "127.0.0.1", port: int = 1080):
        self.host = host
        self.port = port
        self.running = False
        self.server_socket: socket.socket | None = None
        self._thread: threading.Thread | None = None
        
        self._interface_index = 0
        self._interface_lock = threading.Lock()

    def start(self) -> None:
        self.running = True
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind((self.host, self.port))
        self.server_socket.listen(100)
        
        self._thread = threading.Thread(target=self._accept_loop, daemon=True)
        self._thread.start()
        logger.info(f"SOCKS5 Proxy started on {self.host}:{self.port}")

    def stop(self) -> None:
        self.running = False
        if self.server_socket:
            self.server_socket.close()

    def _get_next_local_ip(self) -> str | None:
        ifaces = list_interfaces()
        # Filter for reachable ones
        # For a fast proxy, doing is_reachable per connection is slow. 
        # But let's just pick one that is not loopback. 
        active_ips = [i.ip for i in ifaces if i.ip != "127.0.0.1"]
        if not active_ips:
            return None
            
        with self._interface_lock:
            self._interface_index = (self._interface_index + 1) % len(active_ips)
            return active_ips[self._interface_index]

    def _accept_loop(self) -> None:
        while self.running:
            try:
                client, addr = self.server_socket.accept()
                threading.Thread(target=self._handle_client, args=(client,), daemon=True).start()
            except Exception as e:
                if self.running:
                    logger.error(f"Accept error: {e}")

    def _handle_client(self, client: socket.socket) -> None:
        try:
            # 1. Greeting
            version, nmethods = struct.unpack("!BB", client.recv(2))
            methods = client.recv(nmethods)
            
            # Send NO AUTHENTICATION REQUIRED
            client.sendall(struct.pack("!BB", SOCKS_VERSION, 0))
            
            # 2. Request
            version, cmd, _, address_type = struct.unpack("!BBBB", client.recv(4))
            
            if cmd != CMD_CONNECT:
                client.close()
                return

            if address_type == ATYP_IPV4:
                address = socket.inet_ntoa(client.recv(4))
            elif address_type == ATYP_DOMAINNAME:
                domain_length = client.recv(1)[0]
                address = client.recv(domain_length).decode()
            elif address_type == ATYP_IPV6:
                address = socket.inet_ntop(socket.AF_INET6, client.recv(16))
            else:
                client.close()
                return
                
            port = struct.unpack("!H", client.recv(2))[0]
            
            # Connect to target via bonded IP
            target = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            
            local_ip = self._get_next_local_ip()
            if local_ip:
                try:
                    target.bind((local_ip, 0))
                except OSError as e:
                    logger.warning(f"Could not bind to {local_ip}: {e}")
            
            try:
                target.connect((address, port))
                # Success response
                bind_addr = target.getsockname()
                bind_ip_packed = socket.inet_aton(bind_addr[0])
                reply = struct.pack("!BBBBIH", SOCKS_VERSION, 0, 0, ATYP_IPV4, struct.unpack("!I", bind_ip_packed)[0], bind_addr[1])
                client.sendall(reply)
            except Exception as e:
                # Connection refused / host unreachable
                reply = struct.pack("!BBBBIH", SOCKS_VERSION, 5, 0, ATYP_IPV4, 0, 0)
                client.sendall(reply)
                client.close()
                target.close()
                return

            # Exchange data
            self._exchange_data(client, target)
            
        except Exception as e:
            logger.debug(f"Proxy error: {e}")
        finally:
            try:
                client.close()
            except:
                pass

    def _exchange_data(self, client: socket.socket, target: socket.socket) -> None:
        sockets = [client, target]
        while self.running:
            try:
                r, w, x = select.select(sockets, [], sockets, 10)
                if x:
                    break
                for s in r:
                    data = s.recv(65536)
                    if not data:
                        return
                    if s is client:
                        target.sendall(data)
                    else:
                        client.sendall(data)
            except Exception:
                break
