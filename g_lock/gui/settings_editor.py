from __future__ import annotations

import tkinter as tk
from typing import Any, Literal

from config.configdata import ConfigData
from gui import theme, widgets
from gui.i18n import t
from util.hotkeys import play_beep

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
    # Taller window to fit all vertical controls comfortably
    top.geometry("480x820")
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
    sound_frame.pack(fill="x", padx=15, pady=10)

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
    ctrls_frame.pack(fill="x", expand=True)

    # Helper to build a clean vertical group with grid
    def build_sound_group(
        parent: tk.Frame,
        title: str,
        default_freq: int,
        default_dur: int,
        default_vol: int,
    ) -> tuple[tk.LabelFrame, tk.Scale, tk.Scale, tk.Scale, widgets.NeonButton]:
        group = tk.LabelFrame(
            parent,
            text=title,
            bg=theme.BG,
            fg=theme.TEXT,
            font=theme.FONT_UI,
            padx=10,
            pady=5,
        )
        group.columnconfigure(1, weight=1)

        # Labels
        freq_label = tk.Label(
            group,
            text=t("settings_freq", value=default_freq),
            bg=theme.BG,
            fg=theme.TEXT,
            font=theme.FONT_UI,
            width=18,
            anchor="w",
        )
        freq_label.grid(row=0, column=0, sticky="w", padx=5, pady=2)

        dur_label = tk.Label(
            group,
            text=t("settings_dur", value=default_dur),
            bg=theme.BG,
            fg=theme.TEXT,
            font=theme.FONT_UI,
            width=18,
            anchor="w",
        )
        dur_label.grid(row=1, column=0, sticky="w", padx=5, pady=2)

        vol_label = tk.Label(
            group,
            text=t("settings_vol", value=default_vol),
            bg=theme.BG,
            fg=theme.TEXT,
            font=theme.FONT_UI,
            width=18,
            anchor="w",
        )
        vol_label.grid(row=2, column=0, sticky="w", padx=5, pady=2)

        # Scales
        scale_kwargs: dict[str, Any] = {
            "orient": "horizontal",
            "showvalue": False,
            "bg": theme.BG,
            "fg": theme.TEXT,
            "highlightthickness": 0,
            "troughcolor": theme.PANEL,
            "activebackground": theme.NEON_CYAN,
        }

        freq_scale = tk.Scale(
            group,
            from_=200,
            to=2000,
            resolution=50,
            command=lambda val: freq_label.config(text=t("settings_freq", value=val)),
            **scale_kwargs,
        )
        freq_scale.set(default_freq)
        freq_scale.grid(row=0, column=1, sticky="ew", padx=5, pady=2)

        dur_scale = tk.Scale(
            group,
            from_=50,
            to=1000,
            resolution=50,
            command=lambda val: dur_label.config(text=t("settings_dur", value=val)),
            **scale_kwargs,
        )
        dur_scale.set(default_dur)
        dur_scale.grid(row=1, column=1, sticky="ew", padx=5, pady=2)

        vol_scale = tk.Scale(
            group,
            from_=0,
            to=100,
            resolution=5,
            command=lambda val: vol_label.config(text=t("settings_vol", value=val)),
            **scale_kwargs,
        )
        vol_scale.set(default_vol)
        vol_scale.grid(row=2, column=1, sticky="ew", padx=5, pady=2)

        test_btn = widgets.NeonButton(
            group,
            t("settings_btn_test"),
            command=lambda: play_beep(
                int(freq_scale.get()), int(dur_scale.get()), int(vol_scale.get())
            ),
        )
        test_btn.grid(row=0, column=2, rowspan=3, padx=10, pady=2)

        return group, freq_scale, dur_scale, vol_scale, test_btn

    # Group: On Lock
    (
        lock_grp,
        lock_freq_scale,
        lock_dur_scale,
        lock_vol_scale,
        lock_test_btn,
    ) = build_sound_group(
        ctrls_frame,
        t("settings_sound_lock"),
        config.get("sound_lock_freq", 900),
        config.get("sound_lock_dur", 200),
        config.get("sound_lock_vol", 80),
    )
    lock_grp.pack(fill="x", pady=5)

    # Group: On Unlock
    (
        unlock_grp,
        unlock_freq_scale,
        unlock_dur_scale,
        unlock_vol_scale,
        unlock_test_btn,
    ) = build_sound_group(
        ctrls_frame,
        t("settings_sound_unlock"),
        config.get("sound_unlock_freq", 400),
        config.get("sound_unlock_dur", 200),
        config.get("sound_unlock_vol", 80),
    )
    unlock_grp.pack(fill="x", pady=5)

    # Enable/disable sub-controls when sound checkbutton is toggled
    def toggle_sound_controls() -> None:
        state: Literal["normal", "disabled"] = (
            "normal" if sound_enabled_var.get() else "disabled"
        )
        for scale in (
            lock_freq_scale,
            lock_dur_scale,
            lock_vol_scale,
            unlock_freq_scale,
            unlock_dur_scale,
            unlock_vol_scale,
        ):
            scale.config(state=state)
        lock_test_btn.set_state(state)
        unlock_test_btn.set_state(state)

    chk.config(command=toggle_sound_controls)
    toggle_sound_controls()  # Init state

    # Layout: Security section
    security_frame = tk.LabelFrame(
        top,
        text=t("settings_security_sec"),
        bg=theme.BG,
        fg=theme.NEON_CYAN,
        font=theme.FONT_HEADING,
        padx=15,
        pady=10,
        bd=1,
        relief="solid",
        highlightbackground=theme.BORDER_DIM,
    )
    security_frame.pack(fill="x", padx=15, pady=10)

    auto_lock_var = tk.BooleanVar(value=config.get("auto_lock_on_attack", False))
    auto_lock_chk = tk.Checkbutton(
        security_frame,
        text=t("settings_auto_lock"),
        variable=auto_lock_var,
        bg=theme.BG,
        fg=theme.TEXT,
        selectcolor=theme.PANEL,
        activebackground=theme.BG,
        activeforeground=theme.TEXT,
        font=theme.FONT_UI,
        bd=0,
        highlightthickness=0,
    )
    auto_lock_chk.pack(anchor="w")

    # Slider for multiplier
    multiplier_label = tk.Label(
        security_frame,
        text=t("settings_adaptive_multiplier") + f": {config.get('ips_adaptive_multiplier', 5)}",
        bg=theme.BG,
        fg=theme.TEXT,
        font=theme.FONT_UI,
        anchor="w",
    )
    multiplier_label.pack(anchor="w", pady=(10, 2))

    multiplier_scale = tk.Scale(
        security_frame,
        from_=2,
        to=10,
        resolution=1,
        orient="horizontal",
        showvalue=False,
        bg=theme.BG,
        fg=theme.TEXT,
        highlightthickness=0,
        troughcolor=theme.PANEL,
        activebackground=theme.NEON_CYAN,
        command=lambda val: multiplier_label.config(text=t("settings_adaptive_multiplier") + f": {val}"),
    )
    multiplier_scale.set(config.get("ips_adaptive_multiplier", 5))
    multiplier_scale.pack(fill="x", pady=(0, 10))

    # Slider for fallback threshold
    fallback_label = tk.Label(
        security_frame,
        text=t("settings_fallback_threshold") + f": {config.get('ips_fallback_threshold', 250)} PPS",
        bg=theme.BG,
        fg=theme.TEXT,
        font=theme.FONT_UI,
        anchor="w",
    )
    fallback_label.pack(anchor="w", pady=(5, 2))

    fallback_scale = tk.Scale(
        security_frame,
        from_=50,
        to=500,
        resolution=10,
        orient="horizontal",
        showvalue=False,
        bg=theme.BG,
        fg=theme.TEXT,
        highlightthickness=0,
        troughcolor=theme.PANEL,
        activebackground=theme.NEON_CYAN,
        command=lambda val: fallback_label.config(text=t("settings_fallback_threshold") + f": {val} PPS"),
    )
    fallback_scale.set(config.get("ips_fallback_threshold", 250))
    fallback_scale.pack(fill="x", pady=(0, 10))

    # Save / Cancel Buttons
    action_frame = tk.Frame(top, bg=theme.BG)
    action_frame.pack(pady=15)

    def on_save() -> None:
        config.data["hotkey_vk"] = new_vk[0]
        config.data["hotkey_name"] = new_name[0]
        config.data["sound_enabled"] = sound_enabled_var.get()
        config.data["sound_lock_freq"] = int(lock_freq_scale.get())
        config.data["sound_lock_dur"] = int(lock_dur_scale.get())
        config.data["sound_lock_vol"] = int(lock_vol_scale.get())
        config.data["sound_unlock_freq"] = int(unlock_freq_scale.get())
        config.data["sound_unlock_dur"] = int(unlock_dur_scale.get())
        config.data["sound_unlock_vol"] = int(unlock_vol_scale.get())
        config.data["auto_lock_on_attack"] = auto_lock_var.get()
        config.data["ips_adaptive_multiplier"] = int(multiplier_scale.get())
        config.data["ips_fallback_threshold"] = int(fallback_scale.get())
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

    from gui.dialogs import center_toplevel

    center_toplevel(top, root)
    top.wait_window(top)
