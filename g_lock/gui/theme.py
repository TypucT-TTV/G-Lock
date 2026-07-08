"""
Shared dark/neon visual language for the whole GUI: color palette + a
rounded-rectangle point helper (tkinter Canvas has no native rounded-rect
primitive; a 12-point smooth polygon is the standard trick for one).
"""

from __future__ import annotations

from tkinter import ttk

# Base surfaces
BG = "#0b0e14"  # window background — near-black, slight navy tint
PANEL = "#12161f"  # button/card resting fill
PANEL_HOVER = "#182030"  # button/card fill on hover
PANEL_PRESSED = "#0d1119"  # button fill while pressed
BORDER_DIM = "#1c2130"  # subtle background geometry line color
BORDER_DIM_2 = "#141824"  # even more subtle, for secondary shapes

# Neon accents
NEON_CYAN = "#39f2ec"
NEON_CYAN_DIM = "#1c6b6b"
NEON_MAGENTA = "#ff3df0"

# Status colors (session lock indicator)
SUCCESS = "#2ecc71"
DANGER = "#ff3b5c"

# Text
TEXT = "#e8f2ff"
TEXT_DIM = "#7c8aa5"
TEXT_DISABLED = "#454d5e"

FONT_UI = ("Segoe UI", 10)
FONT_UI_BOLD = ("Segoe UI", 10, "bold")
FONT_HEADING = ("Segoe UI", 12, "bold")


def rounded_rect_points(
    x1: float, y1: float, x2: float, y2: float, radius: float
) -> list[float]:
    """
    Generates a dense list of points tracing a mathematically correct rounded
    rectangle. This is meant to be drawn with smooth=False (the default),
    which produces a perfectly crisp, anti-aliased shape without the
    asymmetrical distortions caused by Tkinter's internal spline smoothing.
    """
    import math

    radius = min(radius, (x2 - x1) / 2, (y2 - y1) / 2)
    if radius <= 0:
        return [x1, y1, x2, y1, x2, y2, x1, y2]

    points: list[float] = []
    steps = 8  # 8 segments per corner is more than enough for smoothness

    # 1. Top-right corner (from -90 to 0 degrees)
    cx, cy = x2 - radius, y1 + radius
    for i in range(steps + 1):
        angle = math.radians(-90 + (i * 90 / steps))
        points.append(cx + radius * math.cos(angle))
        points.append(cy + radius * math.sin(angle))

    # 2. Bottom-right corner (from 0 to 90 degrees)
    cx, cy = x2 - radius, y2 - radius
    for i in range(steps + 1):
        angle = math.radians(i * 90 / steps)
        points.append(cx + radius * math.cos(angle))
        points.append(cy + radius * math.sin(angle))

    # 3. Bottom-left corner (from 90 to 180 degrees)
    cx, cy = x1 + radius, y2 - radius
    for i in range(steps + 1):
        angle = math.radians(90 + (i * 90 / steps))
        points.append(cx + radius * math.cos(angle))
        points.append(cy + radius * math.sin(angle))

    # 4. Top-left corner (from 180 to 270 degrees)
    cx, cy = x1 + radius, y1 + radius
    for i in range(steps + 1):
        angle = math.radians(180 + (i * 90 / steps))
        points.append(cx + radius * math.cos(angle))
        points.append(cy + radius * math.sin(angle))

    return points


def apply_ttk_style() -> None:
    """
    Dark-themes the handful of ttk widgets NeonButton doesn't replace
    (Progressbar, Scrollbar, Treeview) — ttk widgets ignore plain bg/fg
    options and only take color from a Style, and the default Windows
    themes ('vista'/'winnative') ignore custom colors entirely, so this
    switches to 'clam' first (the one built-in theme that honours them).
    Call once, before any of these widgets are created.
    """
    style = ttk.Style()
    style.theme_use("clam")

    style.configure("TNotebook", background=BG, bordercolor=BORDER_DIM, tabmargins=0)
    style.configure(
        "TNotebook.Tab",
        background=BG,
        foreground=TEXT_DIM,
        padding=(14, 6),
        bordercolor=BORDER_DIM,
    )
    style.map(
        "TNotebook.Tab",
        background=[("selected", PANEL)],
        foreground=[("selected", TEXT)],
    )

    style.configure(
        "TProgressbar",
        background=NEON_CYAN,
        troughcolor=PANEL,
        bordercolor=BORDER_DIM,
        lightcolor=NEON_CYAN,
        darkcolor=NEON_CYAN,
    )

    style.configure(
        "Vertical.TScrollbar",
        background=PANEL,
        troughcolor=BG,
        bordercolor=BORDER_DIM,
        arrowcolor=TEXT_DIM,
        relief="flat",
    )
    style.map("Vertical.TScrollbar", background=[("active", PANEL_HOVER)])

    style.configure(
        "Treeview",
        background=PANEL,
        fieldbackground=PANEL,
        foreground=TEXT,
        bordercolor=BORDER_DIM,
        borderwidth=0,
        rowheight=26,
    )
    style.map(
        "Treeview",
        background=[("selected", NEON_CYAN_DIM)],
        foreground=[("selected", TEXT)],
    )
    style.configure(
        "Treeview.Heading",
        background=BG,
        foreground=TEXT_DIM,
        relief="raised",
        bordercolor=BORDER_DIM,
        lightcolor=BG,
        darkcolor=BG,
        borderwidth=1,
    )
    style.map("Treeview.Heading", background=[("active", PANEL_HOVER)])
