# G-Lock Project Roadmap

This document outlines the planned improvements and future features for the G-Lock firewall utility.

---

## Phase 1: Automated Whitelist Sync (Web-to-Client)

**Goal:** Automate IP collection for friends, crew members, and stream sponsors (Twitch / Boosty) to eliminate the need for manual IP whitelisting.

### 1. Web Portal (Authorization Server)
- **Tech Stack:** FastAPI / Node.js backend with a simple OAuth frontend hosted on a VPS/Vercel.
- **Integrations:**
  - **Twitch OAuth:** Authenticate users and check if they follow/subscribe to the host's channel.
  - **Boosty / Patreon API:** Validate active subscription status.
- **IP Detection:**
  - The server automatically captures the client's public IP address from the HTTP request headers (`X-Forwarded-For` or `X-Real-IP`).
- **Temporary Storage:**
  - Whitelisted IPs are stored in a database (e.g., Redis) with a Time-To-Live (TTL) of 12-24 hours to handle dynamic residential IPs.

### 2. G-Lock Client Sync (Local App)
- **Secure Sync:**
  - G-Lock client requests whitelisted IPs from the web portal's API using a secure, private API key (`/api/whitelist?key=TOKEN`).
- **Dynamic Reloading:**
  - G-Lock polls the server every 1-2 minutes and dynamically updates `whitelist_ips` in-memory. No filter restarts required.

---

## Phase 2: Dynamic Lobby Auto-Locking

**Goal:** Further reduce user interaction during game sessions.

- **Auto-Lock:**
  - Automatically transition the lobby from "Open" to "Locked" status X minutes after starting a session or once a target number of whitelisted players (e.g., 3-5 friends) has successfully connected.
- **Status Overlay:**
  - Visual overlay or simple sound notification confirming the lobby lock status.

---

## Phase 3: Connection Logging & UI Refinements

**Goal:** Simplify manual blacklisting / whitelisting from the G-Lock interface.

- **Log Interaction:**
  - Allow users to right-click IP addresses in the diagnostic connection log window to instantly "Add to Blacklist" or "Add to Whitelist".
- **Reverse Geo-lookup:**
  - Integrate a lightweight offline database (e.g., MaxMind GeoLite2) to show approximate player countries in the connection logs to identify suspicious connection origins.

---

## Phase 4: Advanced Crash & Flood Protection (IPS Enhancements)

**Goal:** Secure G-Lock from advanced distributed P2P attacks and Rockstar relay tunneling.

### 1. Surgical IPS for Rockstar/Azure Relays (Experiment)
- **Objective:** Prevent attackers from tunneling flood attacks through Rockstar/Azure relays while keeping legitimate cloud connection intact.
- **Mechanism:**
  - Allow Rockstar/Azure relay IPs to bypass rate-limiting *only* for legitimate service sizes (`HEARTBEAT_SIZES` and `MATCHMAKING_SIZES`).
  - Rate-limit all other traffic from relay subnets with an isolated, higher threshold (`ips_pps_threshold_rstar`, default 300 PPS).
  - Toggled via `surgical_rstar_ips` in `data.json` to allow diagnostic checks.

### 2. Adaptive PPS Threshold
- **Objective:** Eliminate the need to manually tune the fixed `ips_pps_threshold` for different networks.
- **Mechanism:**
  - Measure the baseline incoming PPS over a quiet 30-60 second window after the application starts.
  - Set the active PPS threshold dynamically as a multiplier of the baseline (e.g., `ips_threshold_multiplier = 5`).
  - Fall back to the configured fixed threshold if a reliable baseline cannot be established.

### 3. Global PPS Ceiling (Anti-Spoofing & Distributed Flood Protection)
- **Objective:** Defend against distributed floods or IP-spoofing where packets arrive from random/changing IPs.
- **Mechanism:**
  - Track the cumulative incoming PPS from all non-whitelisted sources.
  - If the aggregate stream exceeds a global limit (`global_pps_ceiling`), write an anomaly entry to the incident log and trigger an automatic lock transition.
