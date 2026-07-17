# G-Lock

G-Lock is a Windows firewall utility for protecting GTA Online sessions. It filters
IPv4 UDP traffic through WinDivert without injecting code, reading game memory, or
modifying game files.

## Features

- Global `F9` lock/unlock hotkey and `Ctrl+F9` panic unlock.
- A single, explicit Open/Locked session state.
- Advanced IPv4/CIDR blocking for verified peer addresses.
- Adaptive per-IP flood protection and a bounded global PPS ceiling.
- Real-time packet decision log with copyable IP addresses.
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
3. Press `F9` or use the status-card button. Known peers remain connected; unknown non-service
   traffic is blocked.
4. Press `F9` again, `Ctrl+F9`, or use the same button before joining another public lobby.

Heartbeat packets required by Rockstar services are passed unless the peer address
is explicitly blacklisted. Rockstar/Azure relay ranges are loaded from the bundled
database and refreshed from RIPE in the background. Relay traffic is excluded from
IPS rate bans.

Solo and Whitelist admission modes are intentionally not exposed. Rockstar-mediated
signaling reveals the useful direct peer IP too late for those modes to provide a
reliable pre-admission guarantee. Verified IPv4/CIDR block rules remain available
under Advanced Settings and apply after the peer address becomes visible.

## Security notes

G-Lock runs elevated because WinDivert requires administrator rights. It does not add
Windows Defender exclusions. If security software blocks the signed WinDivert files,
review the alert and configure the narrowest possible exception manually.

Connection logs and `data.json` are stored next to the executable. Do not publish
them without reviewing contained IP addresses.

G-Lock filters IPv4 UDP P2P traffic on GTA's port 6672. It is not an anti-cheat,
does not identify players by nickname, and does not inspect every Windows network
connection. IPS reduces suspicious captured floods but cannot guarantee protection
of the entire internet connection from every volumetric DDoS attack.

## Development checks

```powershell
npm run check
cargo fmt --all --manifest-path src-tauri/Cargo.toml -- --check
cargo clippy --manifest-path src-tauri/Cargo.toml --all-targets -- -D warnings
cargo test --manifest-path src-tauri/Cargo.toml
```

## Credits and license

G-Lock was developed using Guardian 3.5.0 by TheMythologist, originally created by
Speyedr. Guardian and this derivative work are distributed under GNU LGPL v3; see
[LICENSE](LICENSE) and the accompanying [GNU GPL v3 text](GPL-3.0.txt). Upstream
notices are preserved in [NOTICE](NOTICE), third-party components are documented in
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md), and source references are preserved
in [SOURCE](SOURCE):
[Guardian](https://gitlab.com/digitalarc/guardian) and
[guardian-fastload-fix](https://gitlab.com/Speyedr/guardian-fastload-fix). G-Lock
bundles WinDivert 2.2.2 and uses the `windivert` Rust crate under LGPL v3 or later.

G-Lock is not affiliated with Rockstar Games or Take-Two Interactive. Use it at your
own risk and follow the applicable game and platform rules.

Security issues should be reported according to [SECURITY.md](SECURITY.md).
