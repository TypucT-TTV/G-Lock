# G-Lock

Firewall-based session protection for **GTA Online**. G-Lock keeps modders and
griefers out of your lobby by filtering connections at the network level — with a
clean custom UI and a one-key session lock (F9).

## What it is (and what it isn't)

G-Lock is **not** a mod menu and **not** a cheat. It never touches the game process,
never reads or writes game memory, and never modifies any game files. It only filters
network traffic through the Windows firewall, so it runs safely alongside BattlEye.

- ✅ Blocks unwanted players from connecting to your session
- ✅ Lets you assemble your crew, then lock the lobby
- ❌ No code injection
- ❌ No cheats or gameplay advantages

## Features

- **One-key session lock (F9):** instantly lock or open your lobby, even while
  in-game. Audio feedback tells you the state (high beep = locked, low beep = open).
- **Custom UI** on top of the proven Guardian filtering engine.
- **Solo / Locked sessions:** play completely alone, or keep your crew in and
  everyone else out.

## Requirements

- Windows 10 / 11 (64-bit)
- Administrator rights (required for the network driver)
- Python 3.10–3.11 (the app runs from source)

## Installation & Run

1. Download or clone this repository.
2. Install [Poetry](https://python-poetry.org/): `pip install poetry`
3. Install dependencies: `poetry install`
4. Run **as administrator** via `Run Guardian.bat` (or the provided shortcut).

## Usage

**Play alone:** start the app, choose **Solo Session**. You're now alone in your lobby.

**Play with your crew (collect-then-lock):**
1. Start a fresh session as host.
2. Press **F9** to open the lobby (low beep).
3. Invite your friends and wait for everyone to load in.
4. Press **F9** again to lock (high beep). No new players can join; your crew stays.

> Close the app when you're done, otherwise you won't be able to join normal
> public lobbies while it's running.

## Credits

Built on [Guardian](https://github.com/TheMythologist/guardian) by TheMythologist,
originally created by Speyedr. Licensed under LGPL-3.0.

## License

GNU Lesser General Public License v3.0 (LGPL-3.0). See [LICENSE](LICENSE).

## Disclaimer

Provided as-is, for protective use only. Not affiliated with Rockstar Games or
Take-Two Interactive. Use at your own risk.