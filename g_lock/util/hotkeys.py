from __future__ import annotations

import ctypes
import logging
import math
import struct
import threading
import time
import winsound
from ctypes import wintypes
from typing import TYPE_CHECKING

from network.sessions import LockedSession
from util.crash import crash_report

if TYPE_CHECKING:
    from menu.menu import Menu

debug_logger = logging.getLogger("debugger")

VK_F9 = 0x78
_POLL_INTERVAL_SECONDS = 0.05

_lock = threading.Lock()
_last_toggle = 0.0
_DEBOUNCE_SECONDS = 0.5


def play_beep(frequency: int, duration_ms: int, volume_percent: int) -> None:
    """
    Play a clean sine-wave tone at a specific volume using winsound.PlaySound.
    Falls back to winsound.Beep if play fails.
    """
    try:
        sample_rate = 44100
        num_samples = int(sample_rate * (duration_ms / 1000.0))
        amplitude = int(32767 * (volume_percent / 100.0))

        pcm_data = bytearray()
        for i in range(num_samples):
            t = i / sample_rate
            sample = int(amplitude * math.sin(2 * math.pi * frequency * t))
            pcm_data.extend(struct.pack("<h", sample))

        data_size = len(pcm_data)
        header = struct.pack(
            "<4sI4s4sIHHIIHH4sI",
            b"RIFF",
            36 + data_size,
            b"WAVE",
            b"fmt ",
            16,
            1,  # PCM
            1,  # Mono
            sample_rate,
            sample_rate * 2,
            2,
            16,
            b"data",
            data_size
        )

        winsound.PlaySound(
            bytes(header + pcm_data),
            winsound.SND_MEMORY | winsound.SND_ASYNC
        )
    except Exception as e:
        debug_logger.debug("Failed to play custom beep: %s", e)
        try:
            winsound.Beep(frequency, duration_ms)
        except Exception:
            pass


def _foreground_process_name() -> str:
    """Best-effort lookup of which process owned the focused window when the
    hotkey fired. Only used for diagnostics, so any failure just yields
    "unknown" instead of taking down the hotkey callback."""
    try:
        hwnd = ctypes.windll.user32.GetForegroundWindow()
        pid = wintypes.DWORD()
        ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        handle = ctypes.windll.kernel32.OpenProcess(
            PROCESS_QUERY_LIMITED_INFORMATION, False, pid.value
        )
        if not handle:
            return "unknown"
        try:
            buf = ctypes.create_unicode_buffer(260)
            ctypes.windll.psapi.GetModuleBaseNameW(handle, None, buf, 260)
            return buf.value or "unknown"
        finally:
            ctypes.windll.kernel32.CloseHandle(handle)
    except OSError:
        return "unknown"


def _toggle_lock(menu: type[Menu]) -> None:
    global _last_toggle

    debug_logger.debug(
        "Hotkey fired, foreground process: %s", _foreground_process_name()
    )

    # Non-blocking acquire: if a toggle is already in flight, drop this press
    # instead of queueing it up (queueing would cause an unwanted double-toggle
    # if the hotkey fires twice in quick succession).
    if not _lock.acquire(blocking=False):
        debug_logger.debug("Hotkey press dropped: toggle already in flight")
        return
    try:
        now = time.monotonic()
        if now - _last_toggle < _DEBOUNCE_SECONDS:
            debug_logger.debug("Hotkey press dropped: within debounce window")
            return
        _last_toggle = now

        config = menu.config
        sound_enabled = config.get("sound_enabled", True)

        context = menu.context
        if context.is_locked():
            context.kill_latest_filter()  # открыть сессию
            if sound_enabled:
                freq = config.get("sound_unlock_freq", 400)
                dur = config.get("sound_unlock_dur", 200)
                vol = config.get("sound_unlock_vol", 80)
                play_beep(freq, dur, vol)  # низкий бип = открыто
            print("[HOTKEY] Session UNLOCKED — друзья могут заходить")
        else:
            session = LockedSession(
                priority=context.priority, connection=menu.child_conn
            )
            context.add_filter(session)
            context.start_latest_filter()  # запереть (убивает прежний фильтр)
            if sound_enabled:
                freq = config.get("sound_lock_freq", 900)
                dur = config.get("sound_lock_dur", 200)
                vol = config.get("sound_lock_vol", 80)
                play_beep(freq, dur, vol)  # высокий бип = заперто
            print("[HOTKEY] Session LOCKED — новых не пускает")
    except Exception as e:
        crash_report(e, "G-Lock hotkey callback crashed")
        raise
    finally:
        _lock.release()


def _poll_hotkey(menu: type[Menu]) -> None:
    """
    Polls physical key state via GetAsyncKeyState instead of installing a
    global WH_KEYBOARD_LL hook. Some games (observed with GTA5 in exclusive
    fullscreen) silently invalidate low-level keyboard hooks on the whole
    system once they switch display mode, and the hook never recovers even
    after alt-tabbing back. GetAsyncKeyState reads the OS key-state table
    directly and isn't affected by that.
    """
    was_pressed = False
    while True:
        try:
            vk_code = menu.config.get("hotkey_vk", VK_F9)
            pressed = bool(ctypes.windll.user32.GetAsyncKeyState(vk_code) & 0x8000)
            if pressed and not was_pressed:
                _toggle_lock(menu)
            was_pressed = pressed
        except Exception:
            # _toggle_lock already persisted a crash report for its own
            # failures; catch broadly here so a single bad iteration can't
            # kill hotkey detection for the rest of the session.
            pass
        time.sleep(_POLL_INTERVAL_SECONDS)


def register_hotkeys(menu: type[Menu]) -> None:
    thread = threading.Thread(target=_poll_hotkey, args=(menu,), daemon=True)
    thread.start()
    hotkey_name = menu.config.get("hotkey_name", "F9")
    print(
        f"[HOTKEY] {hotkey_name} — переключение Lock "
        "(высокий бип=заперто, низкий=открыто)"
    )

