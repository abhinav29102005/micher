# ⚡ Micher — Multi-Link Network Bonding

**Combine Ethernet + WiFi + Hotspot for maximum transfer speed.**

Micher bonds multiple network interfaces into a single high-throughput file transfer. Your total speed approaches the **sum** of each link's bandwidth, instead of being capped at one.

> 100 Mbps WiFi + 50 Mbps Ethernet + 30 Mbps Hotspot = **~180 Mbps combined**

---

## 🚀 One-Line Install

### Linux
```bash
curl -sSL https://micher.pages.dev/install.sh | bash
```

### Windows (PowerShell)
```powershell
irm https://micher.pages.dev/install.ps1 | iex
```

### From Source
```bash
git clone https://github.com/abhinav29102005/micher.git
cd micher
pip install -e ".[gui]"
```

---

## 📦 Usage

### CLI — Terminal Dashboard
```bash
# List available network interfaces
micher interfaces

# Send a file (bonds all available interfaces)
micher send 192.168.1.100 myfile.zip

# Start receiver
micher receive --port 9191 --save-dir ./downloads
```

### GUI — Desktop Application
```bash
micher-gui
```
Or find **Micher** in your app launcher (Linux) / Start Menu (Windows).

### Docker — Server Mode
```bash
# Quick start
docker run -p 9191:9191 micher-server

# With docker-compose
docker compose up -d
```

---

## 🎯 Features

| Feature | Description |
|---------|-------------|
| ⚡ Speed Bonding | Stripes data across all NICs simultaneously |
| 📊 Live Dashboard | Real-time speed gauges, per-link graphs, ETA |
| 🔌 Zero Config | Auto-discovers Ethernet, WiFi, hotspot interfaces |
| 🐧🪟 Cross-Platform | Linux + Windows, GUI + CLI |
| 🐳 Docker Ready | One-command server deployment |
| 🆓 100% Free | No VPN, no relay service, no subscription |

---

## 🏗 How It Works

1. **Discover** all active network interfaces and their IPs
2. **Open** one TCP connection per interface, each bound to its NIC
3. **Split** the file into 256 KB chunks
4. **Stripe** chunks across connections — faster links naturally get more work (work-stealing queue)
5. **Reassemble** chunks in order on the receiving end by sequence number

No kernel MPTCP, no VPN tunnels, no root/admin needed. Pure application-level parallelism.

---

## 📁 Project Structure

```
micher/
├── micher/
│   ├── core/           # Networking engine
│   │   ├── interfaces.py   # NIC discovery
│   │   ├── transfer.py     # Bonded send/receive
│   │   └── stats.py        # Real-time stats
│   ├── gui/            # Desktop application
│   │   ├── app.py          # Main window
│   │   ├── dashboard.py    # Speed widgets
│   │   └── transfer_view.py
│   ├── cli.py          # Terminal interface
│   └── assets/         # Icons
├── site/               # Cloudflare Pages (landing + installers)
├── desktop/            # .desktop file + shortcut creator
├── Dockerfile          # Server container
└── docker-compose.yml
```

---

## 📋 Requirements

- **Python 3.9+**
- **CLI**: `rich` (auto-installed)
- **GUI**: `customtkinter`, `pystray`, `Pillow` (install with `pip install micher[gui]`)
- **Server**: Docker (optional)

---

## ⚠️ Limitations

- Bonds only transfers initiated by Micher (not your browser or other apps)
- Requires the receiver to be running on the destination
- No encryption (add TLS per-socket if needed — noted as TODO)
- Not a system-wide VPN or MPTCP replacement

---

## 📄 License

MIT
