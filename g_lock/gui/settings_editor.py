from __future__ import annotations

import threading
import tkinter as tk
from tkinter import ttk
import winsound
from typing import Any, Literal

from config.configdata import ConfigData
from gui import theme, widgets
from gui.i18n import t

# Normalize keysyms for user-friendly display
_KEY_DISPLAY_NAMES = {
    "space": "Space",
    "Return": "Enter",
    "BackSpace": "Backspace",
    "Delete": "Delete",
    "Insert": "Insert",
    "Prior": "PageUp",
    "Next": "PageDown",
    "Home": "Home",
    "End": "End",
    "Escape": "Esc",
    "Tab": "Tab",
}


def open_settings_editor(root: tk.Tk) -> None:
    """
    Open G-Lock Settings editor form (Toplevel dialog).
    """
    top = tk.Toplevel(root)
    top.title(t("settings_title"))
    top.configure(bg=theme.BG)
    top.transient(root)
    top.geometry("450x480")
    top.resizable(False, False)
    top.grab_set()

    config = ConfigData()

    # Load current values from config
    sound_enabled_var = tk.BooleanVar(value=config.get("sound_enabled", True))
    hotkey_vk: int = config.get("hotkey_vk", 0x78)
    hotkey_name: str = config.get("hotkey_name", "F9")

    # State variables for new values
    new_vk = [hotkey_vk]
    new_name = [hotkey_name]
    is_capturing = [False]

    # Helper function to play sound in thread
    def test_beep(freq: int, dur: int) -> None:
        threading.Thread(
            target=lambda: winsound.Beep(freq, dur),
            daemon=True,
        ).start()

    # Layout: Hotkey section
    hotkey_frame = tk.LabelFrame(
        top,
        text=t("settings_hotkey_sec"),
        bg=theme.BG,
        fg=theme.NEON_CYAN,
        font=theme.FONT_HEADING,
        padx=15,
        pady=10,
        bd=1,
        relief="solid",
        highlightbackground=theme.BORDER_DIM,
    )
    hotkey_frame.pack(fill="x", padx=15, pady=(15, 10))

    key_label = tk.Label(
        hotkey_frame,
        text=t("settings_current_key", hotkey=new_name[0]),
        bg=theme.BG,
        fg=theme.TEXT,
        font=theme.FONT_UI,
    )
    key_label.pack(side="left", pady=5)

    def on_key_press(event: tk.Event[tk.Misc]) -> None:
        if not is_capturing[0]:
            return
        
        vk = event.keycode
        name = event.keysym
        
        # Format key name
        if name in _KEY_DISPLAY_NAMES:
            name = _KEY_DISPLAY_NAMES[name]
        elif len(name) == 1:
            name = name.upper()
        
        new_vk[0] = vk
        new_name[0] = name
        
        key_label.config(text=t("settings_current_key", hotkey=name))
        is_capturing[0] = False
        change_btn.set_text(t("settings_btn_change_key"))
        top.unbind("<KeyPress>")

    def start_capturing() -> None:
        if is_capturing[0]:
            return
        is_capturing[0] = True
        change_btn.set_text(t("settings_press_key"))
        top.bind("<KeyPress>", on_key_press)

    change_btn = widgets.NeonButton(
        hotkey_frame,
        t("settings_btn_change_key"),
        command=start_capturing,
    )
    change_btn.pack(side="right", padx=5)

    # Layout: Sound section
    sound_frame = tk.LabelFrame(
        top,
        text=t("settings_sound_sec"),
        bg=theme.BG,
        fg=theme.NEON_CYAN,
        font=theme.FONT_HEADING,
        padx=15,
        pady=10,
        bd=1,
        relief="solid",
        highlightbackground=theme.BORDER_DIM,
    )
    sound_frame.pack(fill="both", expand=True, padx=15, pady=10)

    # Enable checkbutton
    chk = tk.Checkbutton(
        sound_frame,
        text=t("settings_sound_enabled"),
        variable=sound_enabled_var,
        bg=theme.BG,
        fg=theme.TEXT,
        selectcolor=theme.PANEL,
        activebackground=theme.BG,
        activeforeground=theme.TEXT,
        font=theme.FONT_UI,
        bd=0,
        highlightthickness=0,
    )
    chk.pack(anchor="w", pady=(0, 10))

    # Controls container
    ctrls_frame = tk.Frame(sound_frame, bg=theme.BG)
    ctrls_frame.pack(fill="both", expand=True)

    # Group: On Lock
    lock_grp = tk.LabelFrame(
        ctrls_frame,
        text=t("settings_sound_lock"),
        bg=theme.BG,
        fg=theme.TEXT,
        font=theme.FONT_UI,
        padx=10,
        pady=5,
    )
    lock_grp.pack(fill="x", pady=5)

    lock_freq_label = tk.Label(
        lock_grp,
        text="",
        bg=theme.BG,
        fg=theme.TEXT,
        font=theme.FONT_UI,
    )
    lock_freq_label.pack(side="left", padx=5)
    lock_freq_scale = tk.Scale(
        lock_grp,
        from_=200,
        to=2000,
        resolution=50,
        orient="horizontal",
        showvalue=False,
        bg=theme.BG,
        fg=theme.TEXT,
        highlightthickness=0,
        troughcolor=theme.PANEL,
        activebackground=theme.NEON_CYAN,
        command=lambda val: lock_freq_label.config(text=t("settings_freq", value=val)),
    )
    lock_freq_scale.set(config.get("sound_lock_freq", 900))
    lock_freq_scale.pack(side="left", fill="x", expand=True, padx=5)

    lock_dur_label = tk.Label(
        lock_grp,
        text="",
        bg=theme.BG,
        fg=theme.TEXT,
        font=theme.FONT_UI,
    )
    lock_dur_label.pack(side="left", padx=5)
    lock_dur_scale = tk.Scale(
        lock_grp,
        from_=50,
        to=1000,
        resolution=50,
        orient="horizontal",
        showvalue=False,
        bg=theme.BG,
        fg=theme.TEXT,
        highlightthickness=0,
        troughcolor=theme.PANEL,
        activebackground=theme.NEON_CYAN,
        command=lambda val: lock_dur_label.config(text=t("settings_dur", value=val)),
    )
    lock_dur_scale.set(config.get("sound_lock_dur", 200))
    lock_dur_scale.pack(side="left", fill="x", expand=True, padx=5)

    lock_test_btn = widgets.NeonButton(
        lock_grp,
        t("settings_btn_test"),
        command=lambda: test_beep(int(lock_freq_scale.get()), int(lock_dur_scale.get())),
    )
    lock_test_btn.pack(side="right", padx=5)

    # Group: On Unlock
    unlock_grp = tk.LabelFrame(
        ctrls_frame,
        text=t("settings_sound_unlock"),
        bg=theme.BG,
        fg=theme.TEXT,
        font=theme.FONT_UI,
        padx=10,
        pady=5,
    )
    unlock_grp.pack(fill="x", pady=5)

    unlock_freq_label = tk.Label(
        unlock_grp,
        text="",
        bg=theme.BG,
        fg=theme.TEXT,
        font=theme.FONT_UI,
    )
    unlock_freq_label.pack(side="left", padx=5)
    unlock_freq_scale = tk.Scale(
        unlock_grp,
        from_=200,
        to=2000,
        resolution=50,
        orient="horizontal",
        showvalue=False,
        bg=theme.BG,
        fg=theme.TEXT,
        highlightthickness=0,
        troughcolor=theme.PANEL,
        activebackground=theme.NEON_CYAN,
        command=lambda val: unlock_freq_label.config(
            text=t("settings_freq", value=val)
        ),
    )
    unlock_freq_scale.set(config.get("sound_unlock_freq", 400))
    unlock_freq_scale.pack(side="left", fill="x", expand=True, padx=5)

    unlock_dur_label = tk.Label(
        unlock_grp,
        text="",
        bg=theme.BG,
        fg=theme.TEXT,
        font=theme.FONT_UI,
    )
    unlock_dur_label.pack(side="left", padx=5)
    unlock_dur_scale = tk.Scale(
        unlock_grp,
        from_=50,
        to=1000,
        resolution=50,
        orient="horizontal",
        showvalue=False,
        bg=theme.BG,
        fg=theme.TEXT,
        highlightthickness=0,
        troughcolor=theme.PANEL,
        activebackground=theme.NEON_CYAN,
        command=lambda val: unlock_dur_label.config(text=t("settings_dur", value=val)),
    )
    unlock_dur_scale.set(config.get("sound_unlock_dur", 200))
    unlock_dur_scale.pack(side="left", fill="x", expand=True, padx=5)

    unlock_test_btn = widgets.NeonButton(
        unlock_grp,
        t("settings_btn_test"),
        command=lambda: test_beep(int(unlock_freq_scale.get()), int(unlock_dur_scale.get())),
    )
    unlock_test_btn.pack(side="right", padx=5)

    # Enable/disable sub-controls when sound checkbutton is toggled
    def toggle_sound_controls() -> None:
        state: Literal["normal", "disabled"] = "normal" if sound_enabled_var.get() else "disabled"
        for scale in (
            lock_freq_scale,
            lock_dur_scale,
            unlock_freq_scale,
            unlock_dur_scale,
        ):
            scale.config(state=state)
        lock_test_btn.set_state(state)
        unlock_test_btn.set_state(state)

    chk.config(command=toggle_sound_controls)
    toggle_sound_controls()  # Init state

    # Save / Cancel Buttons
    action_frame = tk.Frame(top, bg=theme.BG)
    action_frame.pack(pady=15)

    def on_save() -> None:
        config.data["hotkey_vk"] = new_vk[0]
        config.data["hotkey_name"] = new_name[0]
        config.data["sound_enabled"] = sound_enabled_var.get()
        config.data["sound_lock_freq"] = int(lock_freq_scale.get())
        config.data["sound_lock_dur"] = int(lock_dur_scale.get())
        config.data["sound_unlock_freq"] = int(unlock_freq_scale.get())
        config.data["sound_unlock_dur"] = int(unlock_dur_scale.get())
        config.save()
        top.destroy()

    widgets.NeonButton(action_frame, t("btn_save"), command=on_save).pack(
        side="left", padx=10
    )
    widgets.NeonButton(
        action_frame,
        t("btn_cancel"),
        command=top.destroy,
        accent=theme.NEON_MAGENTA,
    ).pack(side="left", padx=10)

    top.wait_window(top)
