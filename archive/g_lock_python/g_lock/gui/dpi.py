"""
Windows renders a process that hasn't declared itself "DPI-aware" at its
design baseline (96 DPI) and then bitmap-stretches the finished window to
match the monitor's actual scale (125%/150%/etc.) — that stretch is exactly
what makes curved edges (rounded button corners, background hexagons) look
blurry/jagged ("staircase") on screen, even though Tk itself draws them
cleanly at its own internal resolution. Declaring the process DPI-aware
makes Windows skip that stretch and let Tk render directly at the monitor's
true pixel resolution instead.
"""

from __future__ import annotations

import ctypes


def make_process_dpi_aware() -> None:
    """Call once, as early as possible in the process — before any Tk window
    (including error-dialog fallbacks) is created. Tries the most capable
    API first, falling back for older Windows versions."""
    try:
        # DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2 — Windows 10 1703+.
        ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
        return
    except (AttributeError, OSError):
        pass
    try:
        # PROCESS_PER_MONITOR_DPI_AWARE — Windows 8.1+.
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
        return
    except (AttributeError, OSError):
        pass
    try:
        # System-DPI-aware only, but works back to Windows Vista.
        ctypes.windll.user32.SetProcessDPIAware()
    except (AttributeError, OSError):
        pass


def get_scale_factor() -> float:
    """
    Ratio of the system's actual DPI to the Windows design baseline of 96 —
    e.g. 1.5 at a 150% display-scaling setting. Used to scale up hardcoded
    pixel layout constants so the window keeps roughly the physical size it
    always appeared to have, now that Windows isn't silently stretching a
    smaller rendering up to fill that size for us any more.
    """
    try:
        hdc = ctypes.windll.user32.GetDC(0)
        if hdc:
            try:
                LOGPIXELSX = 88
                dpi = int(ctypes.windll.gdi32.GetDeviceCaps(hdc, LOGPIXELSX))
                if dpi:
                    return dpi / 96.0
            finally:
                ctypes.windll.user32.ReleaseDC(0, hdc)
    except (AttributeError, OSError):
        pass
    return 1.0
