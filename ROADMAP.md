# G-Lock Project Roadmap

This document outlines the planned improvements and future features for the G-Lock firewall utility.

---

## Phase 1: Protocol Research Before Identity-Based Admission

**Status:** Experimental Solo/Whitelist admission is removed from the supported UI.

**Goal:** Determine whether GTA/Rockstar traffic exposes a stable, protocol-level signal
that can distinguish service signaling from the actual peer before lobby admission.

- Capture and compare complete real connection sequences instead of relying only on UDP payload size.
- Do not treat a Rockstar/Azure relay IP as a player identity.
- Do not restore Solo/Whitelist controls until repeatable integration tests demonstrate reliable behavior.
- Any future account or community authorization must avoid assuming that one public IP equals one player.

---

## Phase 2: Dynamic Lobby Auto-Locking

**Goal:** Further reduce user interaction during game sessions.

- **Auto-Lock:**
  - Automatically transition the lobby from "Open" to "Locked" status X minutes after starting a session.
- **Status Overlay:**
  - Visual overlay or simple sound notification confirming the lobby lock status.

---

## Phase 3: Connection Logging & UI Refinements (Partially completed)

**Goal:** Keep packet diagnostics understandable without unsafe one-click actions.

- **Log Interaction — completed:**
  - Click-to-copy remains available for diagnostic IP addresses.
  - Quick Whitelist/Blacklist buttons were removed to reduce accidental blocking of relays or shared NAT/CGNAT addresses.
- **Advanced IP blocking — completed:**
  - Verified IPv4/CIDR rules are managed under Advanced Settings with explicit limitations.
- **Reverse Geo-lookup:**
  - Integrate a lightweight offline database (e.g., MaxMind GeoLite2) to show approximate player countries in the connection logs to identify suspicious connection origins.

---

## Phase 4: Advanced Crash & Flood Protection (IPS Enhancements, partially completed)

**Goal:** Secure G-Lock from advanced distributed P2P attacks and Rockstar relay tunneling.

### 1. Surgical IPS for Rockstar/Azure Relays (Experiment)
- **Objective:** Prevent attackers from tunneling flood attacks through Rockstar/Azure relays while keeping legitimate cloud connection intact.
- **Mechanism:**
  - Allow Rockstar/Azure relay IPs to bypass rate-limiting *only* for legitimate service sizes (`HEARTBEAT_SIZES` and `MATCHMAKING_SIZES`).
  - Rate-limit all other traffic from relay subnets with an isolated, higher threshold (`ips_pps_threshold_rstar`, default 300 PPS).
  - Toggled via `surgical_rstar_ips` in `data.json` to allow diagnostic checks.

### 2. Adaptive PPS Threshold — completed
- **Objective:** Eliminate the need to manually tune the fixed `ips_pps_threshold` for different networks.
- **Mechanism:**
  - Measure the baseline incoming PPS over a quiet 30-60 second window after the application starts.
  - Set the active PPS threshold dynamically as a multiplier of the baseline (e.g., `ips_threshold_multiplier = 5`).
  - Fall back to the configured fixed threshold if a reliable baseline cannot be established.

### 3. Global PPS Ceiling (Anti-Spoofing & Distributed Flood Protection) — completed
- **Objective:** Defend against distributed floods or IP-spoofing where packets arrive from random/changing IPs.
- **Mechanism:**
  - Track the cumulative incoming PPS from unknown, non-LAN, non-relay sources.
  - If the aggregate stream exceeds `ips_global_pps_ceiling`, write an anomaly entry and optionally trigger Auto-Lock.
  - Keep all per-IP tracking maps bounded and expire inactive entries by TTL.
