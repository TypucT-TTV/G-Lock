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
