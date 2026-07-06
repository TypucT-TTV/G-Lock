from __future__ import annotations

import queue
import threading
import tkinter as tk
from typing import Callable

from gui import dpi, i18n, icons, list_editor, theme, widgets, settings_editor
from gui.adapter import TkUIAdapter
from gui.i18n import t
from menu.menu import Menu, Prompts

_QUEUE_POLL_MS = 100

# Layout constants below are all in "96 DPI" pixels — MainWindow multiplies
# them by the system's actual DPI scale factor at runtime (see gui/dpi.py).
# Once the process declares itself DPI-aware, Windows stops silently
# bitmap-stretching the whole window to compensate for display scaling
# (which is what was causing blurry/jagged "staircase" edges on rounded
# corners and diagonal lines) — but that also means nothing scales these
# raw pixel values up automatically any more, so without this the window
# would render sharp but noticeably smaller on a scaled display than it used
# to appear.
_BUTTON_WIDTH_BASE = 260
_BUTTON_HEIGHT_BASE = 34
_MARGIN_BASE = 40  # outer border of visible background around all content
_CONTENT_PAD_BASE = 20  # inner padding between the margin and the button column
_SECTION_GAP_BASE = 14  # vertical gap between distinct sections (header/stop/etc.)
_BUTTON_GAP_BASE = 8  # vertical gap between consecutive session buttons
_HEADER_HEIGHT_BASE = 26

# Maps a session-launching button's stable id (Prompts.MAIN_MENU's "id", not
# its display text, which changes with the selected language) to the
# AbstractPacketFilter subclass name it results in. Context only tracks
# "which filter class is active", not "which menu item started it" — Solo
# Session and Empty Session both launch a plain SoloSession, so their
# indicators light up together; same for Whitelisted / Auto Whitelisted
# Session both being a WhitelistSession. That's an accurate reflection of the
# underlying filter, not a bug.
_SESSION_BUTTON_FILTER_CLASS = {
    "solo_session": "SoloSession",
    "whitelisted_session": "WhitelistSession",
    "blacklisted_session": "BlacklistSession",
    "auto_whitelisted_session": "WhitelistSession",
    "locked_session": "LockedSession",
    "empty_session": "SoloSession",
}


class MainWindow:
    def __init__(self, menu: type[Menu], version: str = ""):
        self.menu = menu
        self.title_prefix = f"G-Lock {version}".strip()
        i18n.load_saved_language()

        scale = dpi.get_scale_factor()
        self._button_width = round(_BUTTON_WIDTH_BASE * scale)
        self._button_height = round(_BUTTON_HEIGHT_BASE * scale)
        self._margin = round(_MARGIN_BASE * scale)
        self._content_pad = round(_CONTENT_PAD_BASE * scale)
        self._section_gap = round(_SECTION_GAP_BASE * scale)
        self._button_gap = round(_BUTTON_GAP_BASE * scale)
        self._header_height = round(_HEADER_HEIGHT_BASE * scale)
        self._top_bottom_inset = round(20 * scale)
        self._dot_radius = round(9 * scale)

        self.root = tk.Tk()
        self.root.title(self.title_prefix)
        self.root.configure(bg=theme.BG)
        self.root.resizable(False, False)
        theme.apply_ttk_style()

        self.main_queue: "queue.Queue[Callable[[], None]]" = queue.Queue()
        menu.ui = TkUIAdapter(self.root, self.main_queue)
        menu.context.on_change = self._request_state_refresh

        self._status_dot_id: int = -1
        self._status_text_id: int = -1
        self._session_buttons: dict[str, widgets.CanvasButton] = {}
        self.stop_button: widgets.CanvasButton
        self.canvas: tk.Canvas
        self._build_widgets()
        self._apply_state()
        self.root.protocol("WM_DELETE_WINDOW", self._on_quit)
        self._pump_queue()

    def _build_widgets(self) -> None:
        content_x = self._margin + self._content_pad

        # Every button/label below is drawn as items directly on this ONE
        # canvas, sharing it with the geometric background — that's what
        # lets a button's dithered "glass" fill genuinely show the
        # background artwork through it, rather than being an opaque widget
        # with nothing but its own flat color behind it (see
        # gui/widgets.py's CanvasButton docstring for the full reasoning).
        y = float(self._margin)
        y += self._top_bottom_inset  # top inset before the header

        header_y = y
        y += self._header_height
        y += self._section_gap

        stop_button_y = y
        y += self._button_height
        y += self._section_gap

        button_positions: list[tuple[dict[str, str | Callable[[], None]], float]] = []
        for i, entry in enumerate(Prompts.MAIN_MENU):
            button_positions.append((entry, y))
            y += self._button_height
            if i != len(Prompts.MAIN_MENU) - 1:
                y += self._button_gap
        y += self._section_gap

        language_row_y = y
        y += self._button_height
        y += self._top_bottom_inset  # bottom inset

        window_width = 2 * self._margin + 2 * self._content_pad + self._button_width
        window_height = int(y) + self._margin

        # Restore window position if saved and valid, otherwise center on screen
        saved_x = self.menu.config.get("window_x")
        saved_y = self.menu.config.get("window_y")
        is_position_valid = False
        if saved_x is not None and saved_y is not None:
            try:
                import ctypes
                from ctypes import wintypes
                point = wintypes.POINT(int(saved_x), int(saved_y))
                # MONITOR_DEFAULTTONULL = 0
                hmonitor = ctypes.windll.user32.MonitorFromPoint(point, 0)
                if hmonitor:
                    is_position_valid = True
            except Exception:
                pass

        if is_position_valid:
            self.root.geometry(f"{window_width}x{window_height}+{saved_x}+{saved_y}")
        else:
            # Default: center on primary screen
            screen_width = self.root.winfo_screenwidth()
            screen_height = self.root.winfo_screenheight()
            x = (screen_width - window_width) // 2
            y = (screen_height - window_height) // 2
            self.root.geometry(f"{window_width}x{window_height}+{x}+{y}")

        self.canvas = tk.Canvas(self.root, bg=theme.BG, highlightthickness=0)
        self.canvas.place(x=0, y=0, relwidth=1, relheight=1)
        widgets.draw_geometric_background(self.canvas, window_width, window_height)

        # Header: status dot + text.
        dot_r = float(self._dot_radius)
        dot_cy = header_y + self._header_height / 2
        self._status_dot_id = self.canvas.create_oval(
            content_x, dot_cy - dot_r, content_x + 2 * dot_r, dot_cy + dot_r,
            outline="",
        )
        self._status_text_id = self.canvas.create_text(
            content_x + 2 * dot_r + 10, dot_cy,
            text="", fill=theme.TEXT, font=theme.FONT_HEADING, anchor="w",
        )

        self.stop_button = widgets.CanvasButton(
            self.canvas, content_x, stop_button_y, self._button_width, self._button_height,
            t("btn_stop_session"), command=self._on_stop_session,
            accent=theme.NEON_MAGENTA,
        )

        self._session_buttons.clear()
        for entry, button_y in button_positions:
            entry_id = str(entry["id"])
            has_dot = entry_id in _SESSION_BUTTON_FILTER_CLASS
            button = widgets.CanvasButton(
                self.canvas, content_x, button_y, self._button_width, self._button_height,
                t(f"menu_{entry_id}"),
                command=self._make_handler(entry["value"]),
                show_status_dot=has_dot,
            )
            if has_dot:
                self._session_buttons[entry_id] = button

        half_width = (self._button_width - 8) / 2
        current_language = i18n.get_language()

        self.ru_button = widgets.CanvasButton(
            self.canvas, content_x, language_row_y, half_width, self._button_height, "RU",
            command=lambda: self._on_set_language(i18n.LANG_RU),
        )
        if current_language == i18n.LANG_RU:
            self.ru_button.set_state("disabled")

        self.en_button = widgets.CanvasButton(
            self.canvas, content_x + half_width + 8, language_row_y, half_width,
            self._button_height, "EN", command=lambda: self._on_set_language(i18n.LANG_EN),
        )
        if current_language == i18n.LANG_EN:
            self.en_button.set_state("disabled")

    def _on_set_language(self, language: str) -> None:
        i18n.set_language(language)
        self._rebuild()

    def _rebuild(self) -> None:
        self.canvas.destroy()
        self._build_widgets()
        self._apply_state()

    def _on_stop_session(self) -> None:
        threading.Thread(target=self.menu.stop_session, daemon=True).start()

    def _make_handler(self, value: object) -> Callable[[], None]:
        if value == Prompts.QUIT:
            return self._on_quit
        if value == Prompts.EDIT_LISTS:
            return lambda: list_editor.open_list_editor(self.root)
        if value == Prompts.EDIT_SETTINGS:
            return lambda: settings_editor.open_settings_editor(self.root)

        assert callable(value)
        fn = value

        def _dispatch() -> None:
            threading.Thread(target=fn, daemon=True).start()

        return _dispatch

    def _on_quit(self) -> None:
        try:
            if self.root.state() == "normal":
                geom = self.root.geometry()
                parts = geom.split("+")
                if len(parts) == 3:
                    x = int(parts[1])
                    y = int(parts[2])
                    self.menu.config.set("window_x", x)
                    self.menu.config.set("window_y", y)
                    self.menu.config.save()
        except Exception:
            pass
        self.root.destroy()

    def _request_state_refresh(self) -> None:
        # May be called from ANY thread (the F9 hotkey poll thread, or one of
        # the background worker threads a button dispatches to) — never
        # touch Tk here directly, just hand off to the main thread's pump.
        self.main_queue.put(self._apply_state)

    def _apply_state(self) -> None:
        locked = self.menu.context.is_locked()
        session_name = self.menu.context.active_session_name()

        if locked:
            text = t("status_locked")
        elif session_name:
            name_key = i18n.FILTER_CLASS_NAME_KEY.get(session_name)
            text = t("status_active", name=t(name_key) if name_key else session_name)
        else:
            text = t("status_open")

        self.canvas.itemconfig(
            self._status_dot_id, fill=theme.DANGER if locked else theme.SUCCESS
        )
        self.canvas.itemconfig(self._status_text_id, text=text)
        self.root.title(f"{self.title_prefix} - {text}")

        self.stop_button.set_state(
            "normal" if self.menu.context.is_filter_running() else "disabled"
        )
        for entry_id, button in self._session_buttons.items():
            is_active = session_name == _SESSION_BUTTON_FILTER_CLASS[entry_id]
            button.set_status_color(theme.SUCCESS if is_active else theme.TEXT_DISABLED)

        ico_path = icons.get_icon_path(locked)
        self.root.iconbitmap(default=ico_path)
        try:
            icons.force_set_window_icon(self.root.winfo_id(), ico_path)
        except OSError:
            pass

    def _pump_queue(self) -> None:
        try:
            while True:
                task = self.main_queue.get_nowait()
                task()
        except queue.Empty:
            pass
        self.root.after(_QUEUE_POLL_MS, self._pump_queue)

    def run(self) -> None:
        self.root.mainloop()
