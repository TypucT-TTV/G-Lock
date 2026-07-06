from __future__ import annotations

import queue
import threading
import tkinter as tk
from typing import Callable, Optional

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
_MARGIN_BASE = 16  # outer border of visible background around all content
_CONTENT_PAD_BASE = 8  # inner padding between the margin and the button column
_SECTION_GAP_BASE = 12  # vertical gap between distinct sections (header/stop/etc.)
_BUTTON_GAP_BASE = 6  # vertical gap between consecutive session buttons
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

        # Initialize zoom factor
        self._zoom_factor = self.menu.config.get("zoom_factor", 1.0)
        self._reset_to_default_size = False

        scale = dpi.get_scale_factor() * self._zoom_factor
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
        self.root.resizable(True, True)
        theme.apply_ttk_style()

        self._last_width = 0
        self._last_height = 0
        self._save_timer_id: Optional[str] = None
        self._rebuild_timer_id: Optional[str] = None

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

        # Keyboard shortcuts for zoom
        self.root.bind("<Control-equal>", lambda e: self._change_zoom(0.1))
        self.root.bind("<Control-minus>", lambda e: self._change_zoom(-0.1))
        self.root.bind("<Control-KP_Add>", lambda e: self._change_zoom(0.1))
        self.root.bind("<Control-KP_Subtract>", lambda e: self._change_zoom(-0.1))
        self.root.bind("<Control-plus>", lambda e: self._change_zoom(0.1))
        self.root.bind("<Configure>", self._on_resize)

    def _build_widgets(self) -> None:
        scale = dpi.get_scale_factor() * self._zoom_factor

        # Calculate default dimensions
        base_button_width = round(_BUTTON_WIDTH_BASE * scale)
        base_button_height = round(_BUTTON_HEIGHT_BASE * scale)
        margin = round(_MARGIN_BASE * scale)
        content_pad = round(_CONTENT_PAD_BASE * scale)
        section_gap = round(_SECTION_GAP_BASE * scale)
        button_gap = round(_BUTTON_GAP_BASE * scale)
        header_height = round(_HEADER_HEIGHT_BASE * scale)
        top_bottom_inset = round(20 * scale)

        # Calculate dynamic font sizes
        font_ui_size = max(6, round(10 * scale))
        font_ui_bold_size = max(6, round(10 * scale))
        font_heading_size = max(8, round(12 * scale))

        font_ui = ("Segoe UI", font_ui_size)
        font_ui_bold = ("Segoe UI", font_ui_bold_size, "bold")
        font_heading = ("Segoe UI", font_heading_size, "bold")

        # Calculate total static height required
        y_default = float(margin) + top_bottom_inset + header_height + section_gap
        y_default += base_button_height + section_gap
        for i in range(len(Prompts.MAIN_MENU)):
            y_default += base_button_height
            if i != len(Prompts.MAIN_MENU) - 1:
                y_default += button_gap
        y_default += section_gap + base_button_height + top_bottom_inset

        default_width = 2 * margin + 2 * content_pad + base_button_width
        default_height = int(y_default) + margin

        # Apply minimum size constraint
        self.root.minsize(default_width, default_height)

        # Determine actual window dimensions
        w_width = self.root.winfo_width()
        w_height = self.root.winfo_height()

        if w_width <= 1 or w_height <= 1 or self._reset_to_default_size:
            is_zoom_reset = self._reset_to_default_size
            self._reset_to_default_size = False
            saved_x = self.menu.config.get("window_x")
            saved_y = self.menu.config.get("window_y")

            if is_zoom_reset:
                w_width = default_width
                w_height = default_height
            else:
                saved_w = self.menu.config.get("window_w")
                saved_h = self.menu.config.get("window_h")
                w_width = saved_w if saved_w is not None else default_width
                w_height = saved_h if saved_h is not None else default_height

            is_position_valid = False
            if saved_x is not None and saved_y is not None:
                try:
                    import ctypes
                    from ctypes import wintypes
                    point = wintypes.POINT(int(saved_x), int(saved_y))
                    hmonitor = ctypes.windll.user32.MonitorFromPoint(point, 0)
                    if hmonitor:
                        is_position_valid = True
                except Exception:
                    pass

            if is_position_valid:
                self.root.geometry(f"{w_width}x{w_height}+{saved_x}+{saved_y}")
            else:
                screen_width = self.root.winfo_screenwidth()
                screen_height = self.root.winfo_screenheight()
                x = (screen_width - w_width) // 2
                y = (screen_height - w_height) // 2
                self.root.geometry(f"{w_width}x{w_height}+{x}+{y}")

            self.root.update_idletasks()
            w_width = self.root.winfo_width()
            w_height = self.root.winfo_height()

        # Calculate responsive layout coordinates
        button_width = w_width - 2 * margin - 2 * content_pad
        content_x = margin + content_pad

        # Calculate actual drawn content height (excluding outer margins)
        content_height = top_bottom_inset + header_height + section_gap
        content_height += base_button_height + section_gap
        for i in range(len(Prompts.MAIN_MENU)):
            content_height += base_button_height
            if i != len(Prompts.MAIN_MENU) - 1:
                content_height += button_gap
        content_height += section_gap + base_button_height + top_bottom_inset

        # Symmetrically center content within the window height
        vertical_padding = (w_height - content_height) / 2.0
        if vertical_padding < 0.0:
            vertical_padding = 0.0

        pos_y = vertical_padding + top_bottom_inset
        header_y = pos_y
        pos_y += header_height
        pos_y += section_gap

        stop_button_y = pos_y
        pos_y += base_button_height
        pos_y += section_gap

        button_positions: list[tuple[dict[str, str | Callable[[], None]], float]] = []
        for i, entry in enumerate(Prompts.MAIN_MENU):
            button_positions.append((entry, pos_y))
            pos_y += base_button_height
            if i != len(Prompts.MAIN_MENU) - 1:
                pos_y += button_gap
        pos_y += section_gap

        language_row_y = pos_y
        pos_y += base_button_height

        self.canvas = tk.Canvas(self.root, bg=theme.BG, highlightthickness=0)
        self.canvas.place(x=0, y=0, relwidth=1, relheight=1)
        widgets.draw_geometric_background(self.canvas, w_width, w_height)

        # Header: status dot + text
        dot_r = float(round(9 * scale))
        dot_cy = header_y + header_height / 2
        self._status_dot_id = self.canvas.create_oval(
            content_x, dot_cy - dot_r, content_x + 2 * dot_r, dot_cy + dot_r,
            outline="",
        )
        self._status_text_id = self.canvas.create_text(
            content_x + 2 * dot_r + 10, dot_cy,
            text="", fill=theme.TEXT, font=font_heading, anchor="w",
        )

        self.stop_button = widgets.CanvasButton(
            self.canvas, content_x, stop_button_y, button_width, base_button_height,
            t("btn_stop_session"), command=self._on_stop_session,
            accent=theme.NEON_MAGENTA, font=font_ui_bold,
        )

        self._session_buttons.clear()
        for entry, button_y in button_positions:
            entry_id = str(entry["id"])
            has_dot = entry_id in _SESSION_BUTTON_FILTER_CLASS
            button = widgets.CanvasButton(
                self.canvas, content_x, button_y, button_width, base_button_height,
                t(f"menu_{entry_id}"),
                command=self._make_handler(entry["value"]),
                show_status_dot=has_dot, font=font_ui,
            )
            if has_dot:
                self._session_buttons[entry_id] = button

        half_width = (button_width - 8) / 2
        current_language = i18n.get_language()

        self.ru_button = widgets.CanvasButton(
            self.canvas, content_x, language_row_y, half_width, base_button_height, "RU",
            command=lambda: self._on_set_language(i18n.LANG_RU), font=font_ui,
        )
        if current_language == i18n.LANG_RU:
            self.ru_button.set_state("disabled")

        self.en_button = widgets.CanvasButton(
            self.canvas, content_x + half_width + 8, language_row_y, half_width,
            base_button_height, "EN", command=lambda: self._on_set_language(i18n.LANG_EN), font=font_ui,
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
                    size_parts = parts[0].split("x")
                    if len(size_parts) == 2:
                        w = int(size_parts[0])
                        h = int(size_parts[1])
                        self.menu.config.set("window_x", x)
                        self.menu.config.set("window_y", y)
                        self.menu.config.set("window_w", w)
                        self.menu.config.set("window_h", h)
                        self.menu.config.save()
        except Exception:
            pass
        self.root.destroy()

    def _on_resize(self, event: tk.Event[tk.Misc]) -> None:
        if event.widget != self.root:
            return

        # Update in-memory coordinates immediately
        try:
            if self.root.state() == "normal":
                geom = self.root.geometry()
                parts = geom.split("+")
                if len(parts) == 3:
                    x = int(parts[1])
                    y = int(parts[2])
                    size_parts = parts[0].split("x")
                    if len(size_parts) == 2:
                        w = int(size_parts[0])
                        h = int(size_parts[1])
                        self.menu.config.set("window_x", x)
                        self.menu.config.set("window_y", y)
                        self.menu.config.set("window_w", w)
                        self.menu.config.set("window_h", h)
        except Exception:
            pass

        # Debounce disk saving (500ms)
        if self._save_timer_id is not None:
            self.root.after_cancel(self._save_timer_id)
        self._save_timer_id = self.root.after(500, self._save_config_to_disk)

        curr_w = self.root.winfo_width()
        curr_h = self.root.winfo_height()

        if curr_w != self._last_width or curr_h != self._last_height:
            self._last_width = curr_w
            self._last_height = curr_h
            if self._rebuild_timer_id is not None:
                self.root.after_cancel(self._rebuild_timer_id)
            self._rebuild_timer_id = self.root.after(50, self._rebuild)

    def _change_zoom(self, delta: float) -> None:
        # Save current position to config memory before zooming
        try:
            if self.root.state() == "normal":
                geom = self.root.geometry()
                parts = geom.split("+")
                if len(parts) == 3:
                    x = int(parts[1])
                    y = int(parts[2])
                    self.menu.config.set("window_x", x)
                    self.menu.config.set("window_y", y)
        except Exception:
            pass

        new_zoom = round(self._zoom_factor + delta, 1)
        if 0.5 <= new_zoom <= 2.0:
            self._zoom_factor = new_zoom
            self.menu.config.set("zoom_factor", new_zoom)
            self.menu.config.save()
            self._reset_to_default_size = True

            scale = dpi.get_scale_factor() * self._zoom_factor
            self._button_width = round(_BUTTON_WIDTH_BASE * scale)
            self._button_height = round(_BUTTON_HEIGHT_BASE * scale)
            self._margin = round(_MARGIN_BASE * scale)
            self._content_pad = round(_CONTENT_PAD_BASE * scale)
            self._section_gap = round(_SECTION_GAP_BASE * scale)
            self._button_gap = round(_BUTTON_GAP_BASE * scale)
            self._header_height = round(_HEADER_HEIGHT_BASE * scale)
            self._top_bottom_inset = round(20 * scale)
            self._dot_radius = round(9 * scale)

            self._rebuild()

    def _save_config_to_disk(self) -> None:
        try:
            self.menu.config.save()
        except Exception:
            pass

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
