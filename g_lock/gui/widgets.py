from __future__ import annotations

import math
import random
import tkinter as tk
import tkinter.font as tkfont
from typing import Any, Callable, Optional

from gui import theme


def draw_button_shape(
    canvas: tk.Canvas,
    x: float,
    y: float,
    w: float,
    h: float,
    text: str,
    font: tuple[Any, ...],
    accent: str,
    state: str,
    hovered: bool,
    pressed: bool,
    status_color: Optional[str],
    tag: str,
) -> None:
    """
    Shared visual for the rounded, dark "glass" button with a thin neon
    outline — used by both NeonButton (a standalone Canvas widget, for
    dialogs) and CanvasButton (items drawn directly onto a shared canvas, for
    the main window — see CanvasButton's docstring for why that distinction
    matters for the "glass" fill to actually look translucent).
    """
    canvas.delete(tag)

    if state == "disabled":
        fill, border, text_color = theme.PANEL, theme.TEXT_DISABLED, theme.TEXT_DISABLED
    elif pressed:
        fill, border, text_color = theme.PANEL_PRESSED, accent, theme.TEXT
    elif hovered:
        fill, border, text_color = theme.PANEL_HOVER, accent, theme.TEXT
    else:
        fill, border, text_color = theme.PANEL, theme.NEON_CYAN_DIM, theme.TEXT

    points = theme.rounded_rect_points(
        x + 1.5, y + 1.5, x + w - 1.5, y + h - 1.5, radius=9
    )
    # stipple dithers the fill (never the outline) against whatever sits
    # behind it on the SAME canvas — this only looks translucent when the
    # button is drawn on the same pixel grid as whatever's meant to show
    # through (see CanvasButton); a separate opaque widget has nothing
    # interesting behind it to dither against.
    canvas.create_polygon(
        points,
        smooth=False,
        fill=fill,
        outline=border,
        width=1.6,
        stipple="gray50",
        tags=tag,
    )

    btn_scale = h / 34.0
    text_x = x + w / 2
    if status_color is not None:
        dot_cx = x + 22.0 * btn_scale
        r = 5.0 * btn_scale
        cy = y + h / 2
        canvas.create_oval(
            dot_cx - r,
            cy - r,
            dot_cx + r,
            cy + r,
            fill=status_color,
            outline="",
            tags=tag,
        )
        text_x = (dot_cx + r + 8.0 * btn_scale + x + w) / 2

    canvas.create_text(
        text_x, y + h / 2, text=text, fill=text_color, font=font, tags=tag
    )


class NeonButton(tk.Canvas):
    """
    A rounded, dark "glass" button with a thin neon outline, as its own
    standalone Canvas widget — behaves like a normal button otherwise:
    pack/grid/place it, pass `command=`, toggle enabled/disabled via
    `.set_state("disabled"/"normal")`. Used in dialogs/the list editor, where
    there's no interesting artwork behind it to show through anyway.

    For buttons that need to sit over the main window's geometric background
    and genuinely look translucent, use CanvasButton instead — a separate
    widget's own background is always opaque against whatever's behind it
    (tkinter doesn't composite transparency across sibling widgets), so this
    class's stipple dither only ever blends against its own flat fill color.
    """

    def __init__(
        self,
        parent: tk.Misc,
        text: str,
        command: Optional[Callable[[], None]] = None,
        width: Optional[int] = None,
        height: int = 34,
        accent: str = theme.NEON_CYAN,
        font: tuple[Any, ...] = theme.FONT_UI,
        parent_bg: str = theme.BG,
        show_status_dot: bool = False,
    ):
        self._font_obj = tkfont.Font(font=font)
        text_width = self._font_obj.measure(text) + 32
        if show_status_dot:
            text_width += 22
        self._width = max(width or 0, text_width)
        self._height = height

        super().__init__(
            parent,
            width=self._width,
            height=self._height,
            bg=parent_bg,
            highlightthickness=0,
        )

        self._text = text
        self._command = command
        self._accent = accent
        self._font = font
        self._state = "normal"
        self._hovered = False
        self._pressed = False
        self._show_status_dot = show_status_dot
        self._status_color = theme.TEXT_DISABLED

        self._draw()

        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<ButtonPress-1>", self._on_press)
        self.bind("<ButtonRelease-1>", self._on_release)
        # pack(fill="x")/grid(sticky="ew") can stretch this widget wider than
        # the size it was constructed with — without redrawing on resize, the
        # rounded-rect (sized to the OLD width) would end up smaller than the
        # actual canvas, leaving a ragged unfilled strip past its right edge.
        self.bind("<Configure>", self._on_configure)

    def _on_configure(self, event: "tk.Event[tk.Misc]") -> None:
        if event.width > 1 and event.height > 1:
            self._width = event.width
            self._height = event.height
            self._draw()

    def _draw(self) -> None:
        status_color = self._status_color if self._show_status_dot else None
        draw_button_shape(
            self,
            0,
            0,
            self._width,
            self._height,
            self._text,
            self._font,
            self._accent,
            self._state,
            self._hovered,
            self._pressed,
            status_color,
            "btn",
        )

    def _on_enter(self, _event: object) -> None:
        if self._state != "disabled":
            self._hovered = True
            self._draw()

    def _on_leave(self, _event: object) -> None:
        self._hovered = False
        self._pressed = False
        self._draw()

    def _on_press(self, _event: object) -> None:
        if self._state != "disabled":
            self._pressed = True
            self._draw()

    def _on_release(self, _event: object) -> None:
        was_pressed = self._pressed
        self._pressed = False
        self._draw()
        if was_pressed and self._state != "disabled" and self._command is not None:
            self._command()

    def set_state(self, state: str) -> None:
        if state != self._state:
            self._state = state
            self._draw()

    def set_text(self, text: str) -> None:
        if text != self._text:
            self._text = text
            self._draw()

    def set_status_color(self, color: str) -> None:
        if color != self._status_color:
            self._status_color = color
            self._draw()


class CanvasButton:
    """
    Same visual as NeonButton, but drawn as tagged items directly on a
    caller-provided canvas at a fixed position, instead of owning its own
    separate Canvas widget. This is what actually lets the stipple dither
    reveal the real background artwork behind it: a standalone widget is
    always an opaque rectangle against whatever's behind it (tkinter doesn't
    composite transparency across sibling widgets), whereas items sharing one
    canvas occupy the same pixel grid, so the dither gaps genuinely show
    whatever else was drawn underneath (e.g. the main window's geometric
    background shapes).

    Hit-testing/hover/click work via `canvas.tag_bind` on this button's own
    unique tag. IMPORTANT: unlike NeonButton, this class creates its items
    ONCE and only ever recolors them via `itemconfigure` afterwards — it must
    never delete+recreate items in response to <Enter>/<Leave>. Canvas
    tag-bindings are re-evaluated against whatever item is currently under
    the pointer; deleting the hovered item and creating a new one in the same
    spot makes Tk see that as "entering" a brand new item, which fires
    <Enter> again, which would redraw again, which fires <Enter> again —
    a synchronous infinite loop that never returns to the Tk event loop
    (observed as the whole window going "Not Responding"). Recoloring
    existing, stable item ids sidesteps this entirely.
    """

    def __init__(
        self,
        canvas: tk.Canvas,
        x: float,
        y: float,
        width: float,
        height: float,
        text: str,
        command: Optional[Callable[[], None]] = None,
        accent: str = theme.NEON_CYAN,
        font: tuple[Any, ...] = theme.FONT_UI,
        show_status_dot: bool = False,
    ):
        self.canvas = canvas
        self.x, self.y, self.width, self.height = x, y, width, height
        self._text = text
        self._command = command
        self._accent = accent
        self._font = font
        self._state = "normal"
        self._hovered = False
        self._pressed = False
        self._status_color = theme.TEXT_DISABLED
        self._tag = f"canvasbtn{id(self)}"

        points = theme.rounded_rect_points(
            x + 1.5, y + 1.5, x + width - 1.5, y + height - 1.5, radius=9
        )
        self._polygon_id = canvas.create_polygon(
            points,
            smooth=False,
            fill=theme.PANEL,
            outline=theme.NEON_CYAN_DIM,
            width=1.6,
            stipple="gray50",
            tags=self._tag,
        )

        btn_scale = height / 34.0
        text_x = x + width / 2
        self._dot_id: Optional[int] = None
        if show_status_dot:
            dot_cx = x + 22.0 * btn_scale
            r = 5.0 * btn_scale
            cy = y + height / 2
            self._dot_id = canvas.create_oval(
                dot_cx - r,
                cy - r,
                dot_cx + r,
                cy + r,
                fill=self._status_color,
                outline="",
                tags=self._tag,
            )
            text_x = (dot_cx + r + 8.0 * btn_scale + x + width) / 2

        self._text_id = canvas.create_text(
            text_x,
            y + height / 2,
            text=text,
            fill=theme.TEXT,
            font=font,
            tags=self._tag,
        )

        self._refresh_colors()

        canvas.tag_bind(self._tag, "<Enter>", self._on_enter)
        canvas.tag_bind(self._tag, "<Leave>", self._on_leave)
        canvas.tag_bind(self._tag, "<ButtonPress-1>", self._on_press)
        canvas.tag_bind(self._tag, "<ButtonRelease-1>", self._on_release)

    def _refresh_colors(self) -> None:
        if self._state == "disabled":
            fill, border, text_color = (
                theme.PANEL,
                theme.TEXT_DISABLED,
                theme.TEXT_DISABLED,
            )
        elif self._pressed:
            fill, border, text_color = theme.PANEL_PRESSED, self._accent, theme.TEXT
        elif self._hovered:
            fill, border, text_color = theme.PANEL_HOVER, self._accent, theme.TEXT
        else:
            fill, border, text_color = theme.PANEL, theme.NEON_CYAN_DIM, theme.TEXT

        self.canvas.itemconfigure(self._polygon_id, fill=fill, outline=border)
        self.canvas.itemconfigure(self._text_id, fill=text_color)
        if self._dot_id is not None:
            self.canvas.itemconfigure(self._dot_id, fill=self._status_color)

    def _on_enter(self, _event: object) -> None:
        if self._state != "disabled":
            self._hovered = True
            self._refresh_colors()
            self.canvas.configure(cursor="hand2")

    def _on_leave(self, _event: object) -> None:
        self._hovered = False
        self._pressed = False
        self._refresh_colors()
        self.canvas.configure(cursor="")

    def _on_press(self, _event: object) -> None:
        if self._state != "disabled":
            self._pressed = True
            self._refresh_colors()

    def _on_release(self, _event: object) -> None:
        was_pressed = self._pressed
        self._pressed = False
        self._refresh_colors()
        if was_pressed and self._state != "disabled" and self._command is not None:
            self._command()

    def set_state(self, state: str) -> None:
        if state != self._state:
            self._state = state
            self._refresh_colors()

    def set_status_color(self, color: str) -> None:
        if color != self._status_color:
            self._status_color = color
            self._refresh_colors()

    def set_text(self, text: str) -> None:
        if text != self._text:
            self._text = text
            self.canvas.itemconfigure(self._text_id, text=text)

    def set_accent(self, accent: str) -> None:
        if accent != self._accent:
            self._accent = accent
            self._refresh_colors()


def draw_geometric_background(canvas: tk.Canvas, width: int, height: int) -> None:
    """
    Scatters a handful of thin, low-key geometric shapes (hexagon outlines,
    diagonal lines, rings) across a canvas as a subtle backdrop — deliberately
    faint (dark, close to the base background color) so it reads as texture
    rather than competing with the actual controls drawn on top.
    """
    canvas.delete("bg_shape")
    rng = random.Random(1337)  # fixed seed: same pattern every launch

    def hexagon(cx: float, cy: float, r: float, color: str) -> None:
        pts = []
        for i in range(6):
            angle = i * 60
            pts.append(cx + r * math.cos(math.radians(angle)))
            pts.append(cy + r * math.sin(math.radians(angle)))
        canvas.create_polygon(pts, outline=color, fill="", width=1, tags="bg_shape")

    # Scattered hexagon outlines across the whole canvas, not just edges —
    # there's now a wide enough margin around the content for these to read
    # as texture without clashing with the buttons.
    for _ in range(16):
        cx = rng.uniform(-10, width + 10)
        cy = rng.uniform(-10, height + 10)
        radius = rng.uniform(12, 50)
        color = rng.choice([theme.BORDER_DIM, theme.BORDER_DIM_2])
        hexagon(cx, cy, radius, color)

    # A handful of long, faint diagonal lines for a "circuit board" feel.
    for _ in range(6):
        x1 = rng.uniform(-40, width * 0.6)
        y1 = rng.uniform(0, height)
        length = rng.uniform(80, 220)
        x2 = x1 + length
        y2 = y1 - length * rng.choice([-1, 1]) * 0.5
        canvas.create_line(
            x1, y1, x2, y2, fill=theme.BORDER_DIM, width=1, tags="bg_shape"
        )

    # A couple of faint neon-tinted rings tucked into corners as accents.
    used_corners: set[str] = set()
    for _ in range(2):
        remaining = [c for c in ("tl", "tr", "bl", "br") if c not in used_corners]
        ring_corner = rng.choice(remaining)
        used_corners.add(ring_corner)
        ring_r = rng.uniform(16, 30)
        margin = ring_r + 10
        corner_positions = {
            "tl": (margin, margin),
            "tr": (width - margin, margin),
            "bl": (margin, height - margin),
            "br": (width - margin, height - margin),
        }
        cx, cy = corner_positions[ring_corner]
        canvas.create_oval(
            cx - ring_r,
            cy - ring_r,
            cx + ring_r,
            cy + ring_r,
            outline=theme.NEON_CYAN_DIM,
            width=1,
            tags="bg_shape",
        )

    canvas.tag_lower("bg_shape")
