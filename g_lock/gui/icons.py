"""
Generates the tiny green/red "session lock status" icons entirely from
stdlib (struct + zlib), rather than shipping binary .ico assets or adding a
Pillow dependency. A PNG-compressed ICO (supported natively by Windows since
Vista) is far simpler to hand-write than classic BMP/DIB icon frames, since
it just needs a minimal PNG encoder (IHDR/IDAT/IEND) plus an ICO container.

Icons are cheap to (re)build (a few milliseconds), so they're generated once
per process into temp files rather than cached to disk permanently — this
also means g_lock/build.py needs no extra --add-data for icon assets.
"""

from __future__ import annotations

import ctypes
import struct
import tempfile
import zlib

_GREEN = (46, 204, 113)
_RED = (231, 76, 60)
_SIZES = (16, 32, 48, 256)

_generated_paths: dict[bool, str] = {}

WM_SETICON = 0x0080
ICON_SMALL = 0
ICON_BIG = 1
_IMAGE_ICON = 1
_LR_LOADFROMFILE = 0x0010
_LR_DEFAULTSIZE = 0x0040
_GA_ROOT = 2


def _png_chunk(chunk_type: bytes, data: bytes) -> bytes:
    crc = zlib.crc32(chunk_type + data) & 0xFFFFFFFF
    return struct.pack(">I", len(data)) + chunk_type + data + struct.pack(">I", crc)


def _make_circle_png(size: int, rgb: tuple[int, int, int]) -> bytes:
    r, g, b = rgb
    radius = size / 2
    center = size / 2 - 0.5
    rows = bytearray()
    for y in range(size):
        rows.append(0)  # per-scanline filter type: None
        for x in range(size):
            dx, dy = x - center, y - center
            if dx * dx + dy * dy <= radius * radius:
                rows.extend((r, g, b, 255))
            else:
                rows.extend((0, 0, 0, 0))

    ihdr = struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0)
    idat = zlib.compress(bytes(rows), 9)
    return (
        b"\x89PNG\r\n\x1a\n"
        + _png_chunk(b"IHDR", ihdr)
        + _png_chunk(b"IDAT", idat)
        + _png_chunk(b"IEND", b"")
    )


def _write_ico(pngs: list[tuple[int, int, bytes]]) -> bytes:
    count = len(pngs)
    header = struct.pack("<HHH", 0, 1, count)
    entries = bytearray()
    data = bytearray()
    offset = 6 + 16 * count
    for width, height, png_bytes in pngs:
        entries += struct.pack(
            "<BBBBHHII",
            width if width < 256 else 0,
            height if height < 256 else 0,
            0,
            0,
            1,
            32,
            len(png_bytes),
            offset,
        )
        data += png_bytes
        offset += len(png_bytes)
    return header + bytes(entries) + bytes(data)


def _build_icon_bytes(rgb: tuple[int, int, int]) -> bytes:
    pngs = [(size, size, _make_circle_png(size, rgb)) for size in _SIZES]
    return _write_ico(pngs)


def get_icon_path(locked: bool) -> str:
    """Returns a filesystem path to a generated .ico for the given lock
    state, generating (and caching for the rest of the process) it on first
    use."""
    if locked not in _generated_paths:
        ico_bytes = _build_icon_bytes(_RED if locked else _GREEN)
        fd, path = tempfile.mkstemp(suffix=".ico", prefix="g_lock_lock_")
        with open(fd, "wb") as handle:
            handle.write(ico_bytes)
        _generated_paths[locked] = path
    return _generated_paths[locked]


def force_set_window_icon(hwnd: int, ico_path: str) -> None:
    """
    Belt-and-suspenders alongside Tk's own `root.iconbitmap()`: sends
    WM_SETICON directly via ctypes so the taskbar button icon updates even if
    Tk's built-in icon handling doesn't propagate to it in some Tk/Windows
    version combination. Uses GetAncestor(..., GA_ROOT) rather than trusting
    the given hwnd directly, since `winfo_id()` can return a child-window
    handle rather than the true top-level frame on some Tk builds.
    """
    root_hwnd = ctypes.windll.user32.GetAncestor(hwnd, _GA_ROOT) or hwnd
    hicon = ctypes.windll.user32.LoadImageW(
        None, ico_path, _IMAGE_ICON, 0, 0, _LR_LOADFROMFILE | _LR_DEFAULTSIZE
    )
    if not hicon:
        return
    ctypes.windll.user32.SendMessageW(root_hwnd, WM_SETICON, ICON_SMALL, hicon)
    ctypes.windll.user32.SendMessageW(root_hwnd, WM_SETICON, ICON_BIG, hicon)
