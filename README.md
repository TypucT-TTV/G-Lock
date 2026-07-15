# G-Lock

G-Lock is a Windows firewall utility for protecting GTA Online sessions. It filters
IPv4 UDP traffic through WinDivert without injecting code, reading game memory, or
modifying game files.

## Features

- Global `F9` lock/unlock hotkey and `Ctrl+F9` panic unlock.
- Open, Locked, Solo, and Whitelist session modes.
- IPv4/CIDR whitelist and blacklist with immediate rule updates.
- Adaptive per-IP flood protection and a bounded global PPS ceiling.
- Real-time connection log with quick whitelist/blacklist actions.
- Russian and English interface, custom alert sounds, and UI zoom.

## Requirements

- Windows 10 or 11, x64.
- Administrator privileges for the WinDivert network driver.
- For development: Node.js LTS, Rust stable with the MSVC toolchain, and npm.

## Run from source

Open an Administrator terminal in the repository:

```powershell
npm ci
npm run tauri dev
```

The production installers are built with:

```powershell
npm run tauri build
```

Build outputs are written under `src-tauri/target/release/bundle/`.

## Basic usage

1. Start G-Lock before joining GTA Online.
2. Leave the session Open while your group joins. G-Lock learns the active peer IPs.
3. Press `F9` or select Lock. Known peers remain connected; unknown non-service
   traffic is blocked.
4. Press `F9` again, `Ctrl+F9`, or select Open before joining another public lobby.

Heartbeat packets required by Rockstar services are passed unless the peer address
is explicitly blacklisted. Rockstar/Azure relay ranges are loaded from the bundled
database and refreshed from RIPE in the background. Relay traffic is excluded from
IPS rate bans.

Whitelist mode has its own Open/Locked state. While Open, Rockstar signaling is
allowed and direct P2P traffic is accepted only from whitelist addresses. While
Locked, already-known peers remain connected and no new peer is admitted, including
a newly seen whitelisted address. The blacklist always takes priority in every mode.

## Security notes

G-Lock runs elevated because WinDivert requires administrator rights. It does not add
Windows Defender exclusions. If security software blocks the signed WinDivert files,
review the alert and configure the narrowest possible exception manually.

Connection logs and `data.json` are stored next to the executable. Do not publish
them without reviewing contained IP addresses.

## Development checks

```powershell
npm run check
cargo fmt --all --manifest-path src-tauri/Cargo.toml -- --check
cargo clippy --manifest-path src-tauri/Cargo.toml --all-targets -- -D warnings
cargo test --manifest-path src-tauri/Cargo.toml
```

## Credits and license

Based on Guardian by TheMythologist, originally created by Speyedr. G-Lock is
licensed under GNU LGPL-3.0-only; see [LICENSE](LICENSE).

G-Lock is not affiliated with Rockstar Games or Take-Two Interactive. Use it at your
own risk and follow the applicable game and platform rules.
