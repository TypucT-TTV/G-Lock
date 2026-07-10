from __future__ import annotations

import queue
import threading
import tkinter as tk
from tkinter import ttk
from typing import Optional

from gui import theme, widgets
from gui.i18n import t


def center_toplevel(top: tk.Toplevel, parent: tk.Tk | tk.Toplevel) -> None:
    """Center a Toplevel window relative to its parent window."""
    top.update_idletasks()
    p_w = parent.winfo_width()
    p_h = parent.winfo_height()
    p_x = parent.winfo_x()
    p_y = parent.winfo_y()

    t_w = top.winfo_width()
    t_h = top.winfo_height()

    x = p_x + (p_w - t_w) // 2
    y = p_y + (p_h - t_h) // 2
    top.geometry(f"{t_w}x{t_h}+{x}+{y}")


def _style_toplevel(top: tk.Toplevel, root: tk.Tk, title: str) -> None:
    top.title(title)
    top.configure(bg=theme.BG)
    top.transient(root)
    top.resizable(False, False)


def show_confirm(root: tk.Tk, title: str, message: str) -> bool:
    """
    Blocks the calling thread (expected to be the Tk main thread, invoked via
    MainWindow's queued-task pump — never call this directly from a
    background/worker thread) until the user answers Yes/No.
    """
    top = tk.Toplevel(root)
    _style_toplevel(top, root, title)

    result = {"value": False}

    body = tk.Message(
        top,
        text=message,
        width=420,
        bg=theme.BG,
        fg=theme.TEXT,
        justify="left",
        font=theme.FONT_UI,
    )
    body.pack(padx=20, pady=20)

    button_row = tk.Frame(top, bg=theme.BG)
    button_row.pack(pady=(0, 16))

    def _answer(value: bool) -> None:
        result["value"] = value
        top.destroy()

    widgets.NeonButton(
        button_row, t("btn_yes_start"), command=lambda: _answer(True)
    ).pack(side="left", padx=6)
    widgets.NeonButton(
        button_row,
        t("btn_no_back"),
        command=lambda: _answer(False),
        accent=theme.NEON_MAGENTA,
    ).pack(side="left", padx=6)

    center_toplevel(top, root)
    top.protocol("WM_DELETE_WINDOW", lambda: _answer(False))
    top.grab_set()
    top.wait_window(top)
    return result["value"]


def show_multiselect(
    root: tk.Tk, title: str, message: str, choices: list[str]
) -> list[str]:
    """
    Same threading contract as show_confirm: only ever call this from the Tk
    main thread (via MainWindow's task pump).
    """
    top = tk.Toplevel(root)
    _style_toplevel(top, root, title)

    result: dict[str, list[str]] = {"value": []}

    body = tk.Message(
        top,
        text=message,
        width=480,
        bg=theme.BG,
        fg=theme.TEXT,
        justify="left",
        font=theme.FONT_UI,
    )
    body.pack(padx=20, pady=(20, 10))

    list_frame = tk.Frame(top, bg=theme.BG)
    list_frame.pack(padx=20, fill="both", expand=True)

    canvas = tk.Canvas(
        list_frame,
        bg=theme.PANEL,
        highlightthickness=1,
        highlightbackground=theme.BORDER_DIM,
        height=min(300, 24 * max(len(choices), 1)),
    )
    scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=canvas.yview)
    inner = tk.Frame(canvas, bg=theme.PANEL)
    inner.bind(
        "<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
    )
    canvas.create_window((0, 0), window=inner, anchor="nw")
    canvas.configure(yscrollcommand=scrollbar.set)
    canvas.pack(side="left", fill="both", expand=True)
    scrollbar.pack(side="right", fill="y")

    vars_by_choice: dict[str, tk.BooleanVar] = {}
    for choice in choices:
        var = tk.BooleanVar(value=False)
        vars_by_choice[choice] = var
        tk.Checkbutton(
            inner,
            text=choice,
            variable=var,
            bg=theme.PANEL,
            fg=theme.TEXT,
            selectcolor=theme.PANEL,
            activebackground=theme.PANEL,
            activeforeground=theme.TEXT,
            highlightthickness=0,
            anchor="w",
        ).pack(fill="x", anchor="w")

    button_row = tk.Frame(top, bg=theme.BG)
    button_row.pack(pady=16)

    def _submit(cancelled: bool) -> None:
        if not cancelled:
            result["value"] = [c for c, v in vars_by_choice.items() if v.get()]
        top.destroy()

    widgets.NeonButton(button_row, t("btn_ok"), command=lambda: _submit(False)).pack(
        side="left", padx=6
    )
    widgets.NeonButton(
        button_row,
        t("btn_cancel"),
        command=lambda: _submit(True),
        accent=theme.NEON_MAGENTA,
    ).pack(side="left", padx=6)

    center_toplevel(top, root)
    top.protocol("WM_DELETE_WINDOW", lambda: _submit(True))
    top.grab_set()
    top.wait_window(top)
    return result["value"]


class ProgressDialog:
    """
    Self-contained progress window with a Cancel button. Unlike show_confirm
    / show_multiselect, this stays open while a background worker thread does
    the actual work, so it polls its OWN queue independently instead of
    relying on MainWindow's task pump (which must stay free to keep servicing
    other requests while this dialog is up).

    Thread-safety contract: __init__ must run on the Tk main thread. Once
    constructed, `report(done)` and `close()` are safe to call from ANY
    thread (they just push onto a queue.Queue).
    """

    def __init__(
        self, root: tk.Tk, title: str, total: int, cancel_event: threading.Event
    ):
        self.total = total
        self.cancel_event = cancel_event
        self._queue: "queue.Queue[tuple[str, Optional[int]]]" = queue.Queue()
        self._closed = False

        self.top = tk.Toplevel(root)
        _style_toplevel(self.top, root, title)
        self.top.protocol("WM_DELETE_WINDOW", self.cancel_event.set)

        self.status_label = tk.Label(
            self.top,
            text=f"0 / {total}",
            bg=theme.BG,
            fg=theme.TEXT,
            font=theme.FONT_UI,
        )
        self.status_label.pack(padx=24, pady=(20, 6))

        self.bar = ttk.Progressbar(
            self.top, orient="horizontal", length=320, mode="determinate", maximum=total
        )
        self.bar.pack(padx=24, pady=6)

        widgets.NeonButton(
            self.top,
            t("btn_cancel"),
            command=self.cancel_event.set,
            accent=theme.NEON_MAGENTA,
        ).pack(pady=(6, 20))

        center_toplevel(self.top, root)
        self.top.grab_set()
        self._poll()

    def report(self, done: int) -> None:
        self._queue.put(("tick", done))

    def close(self) -> None:
        self._queue.put(("close", None))

    def _poll(self) -> None:
        try:
            while True:
                kind, value = self._queue.get_nowait()
                if kind == "tick" and value is not None and not self._closed:
                    self.bar["value"] = value
                    self.status_label.configure(text=f"{value} / {self.total}")
                elif kind == "close":
                    self._closed = True
                    self.top.destroy()
                    return
        except queue.Empty:
            pass
        if not self._closed:
            self.top.after(50, self._poll)
