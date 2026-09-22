# Multi-Link Network Bonding — Build Spec

## Goal
Build a system that uses multiple network interfaces on a PC (Ethernet + WiFi #1 +
WiFi #2, or any mix) **at the same time** for a single task (e.g. a large file
transfer), so total throughput approaches the sum of each interface's bandwidth,
instead of being capped at one interface's speed.

## Constraints
- Must run on Windows and Linux (no macOS).
- Must be free — no paid relay/VPN service (e.g. no Speedify).
- Must work across heterogeneous networks (different ISPs/gateways — Ethernet ISP,
  home WiFi, phone hotspot, etc.), not just multiple cables into one switch.
- Runs as an application on a normal PC, not router firmware.

## Why a relay is required
A single TCP connection is bound to one path. To combine *different* internet
connections (different gateways/public IPs) for one logical transfer, something
must terminate a connection on every interface and re-present a single unified
stream to the destination. That "something" is either:
  (a) the OS kernel (Linux MPTCP, native, free, Linux-only), or
  (b) a relay server you control (a VPS) that every interface tunnels to, which
      reassembles and forwards traffic as one connection — needed for Windows,
      and for true "any network source" bonding regardless of OS.

## Two-tier plan

### Tier 1 (best, Linux only): kernel MPTCP
- Linux 5.6+ has native Multipath TCP support.
- Client opens MPTCP subflows over each interface directly to a VPS running an
  MPTCP-capable kernel + proxy.
- No application code needed — this is `ip mptcp` kernel configuration.

### Tier 2 (cross-platform, this repo): application-level striping
For tasks you control end-to-end (your own file transfer, your own client/server),
skip kernel/VPS complexity and stripe the transfer directly in application code:
- Enumerate available network interfaces and their local IPs.
- Open one TCP connection per interface, each explicitly bound to that interface's
  local IP (forces OS to route that socket's traffic over that specific NIC).
- Split the file/data into chunks.
- Assign chunks to connections using weighted round-robin, weighted by each link's
  measured throughput, so the faster link gets proportionally more data.
- Reassemble chunks in order on the receiving end.
- Track real-time throughput per link and rebalance weights adaptively.

This does NOT bond arbitrary traffic (browsing, unrelated apps) — only transfers
your own client/server code initiates. It requires no VPS, no kernel changes, no
admin/root privileges beyond normal socket binding, and works identically on
Windows and Linux.

## Deliverable in this spec
A reference implementation (Python, stdlib only) of Tier 2:
- `interface_utils.py` — discovers local interface IPs (cross-platform).
- `bonded_transfer.py` — client and server classes implementing weighted chunk
  striping across multiple bound sockets, with adaptive rebalancing based on
  measured per-link throughput.
- Runnable demo: server accepts bonded connections; client sends a file split
  across N interfaces simultaneously and reports effective combined throughput.

## Explicit non-goals of this deliverable
- Not a system-wide VPN/bonding driver.
- Not MPTCP — no kernel dependency, so it will not automatically speed up your
  browser or other apps.
- Not encrypted (add TLS per-socket if needed — noted as a TODO in code).
