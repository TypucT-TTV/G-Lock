from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Optional

from questionary import ValidationError

from config.globallist import Blacklist, GlobalList, Whitelist
from gui import theme, widgets
from gui.i18n import t
from validator.ip import IPValidator


def open_list_editor(root: tk.Tk) -> None:
    """
    Entry point for the "Edit lists" button. Pure Tk widget interaction (no
    long-running work, no Menu.ui bridging needed), so this is safe to call
    directly from the main thread's button handler.
    """
    top = tk.Toplevel(root)
    top.title(t("list_editor_title"))
    top.configure(bg=theme.BG)
    top.transient(root)
    top.geometry("520x460")

    notebook = ttk.Notebook(top)
    notebook.pack(fill="both", expand=True, padx=10, pady=10)

    whitelist_frame = tk.Frame(notebook, bg=theme.BG)
    blacklist_frame = tk.Frame(notebook, bg=theme.BG)
    notebook.add(whitelist_frame, text=t("tab_whitelist"))
    notebook.add(blacklist_frame, text=t("tab_blacklist"))

    _ListTab(whitelist_frame, top, Whitelist)
    _ListTab(blacklist_frame, top, Blacklist)

    from gui.dialogs import center_toplevel

    center_toplevel(top, root)


class _ListTab:
    def __init__(
        self,
        parent: tk.Frame,
        root: tk.Toplevel,
        list_type: type[Whitelist] | type[Blacklist],
    ):
        self.root = root
        self.list_type = list_type

        columns = ("ip",)
        self.tree = ttk.Treeview(parent, columns=columns, show="headings", height=10)
        self.tree.heading("ip", text=t("col_ip"))
        self.tree.column("ip", width=350, anchor="center")
        self.tree.pack(fill="both", expand=True, padx=10, pady=(10, 6))

        button_row = tk.Frame(parent, bg=theme.BG)
        button_row.pack(pady=(0, 10))
        widgets.NeonButton(button_row, t("btn_add"), command=self._on_add).pack(
            side="left", padx=4
        )
        widgets.NeonButton(button_row, t("btn_edit"), command=self._on_edit).pack(
            side="left", padx=4
        )
        widgets.NeonButton(
            button_row,
            t("btn_delete"),
            command=self._on_delete,
            accent=theme.NEON_MAGENTA,
        ).pack(side="left", padx=4)
        widgets.NeonButton(
            button_row,
            t("btn_clear"),
            command=self._on_clear,
            accent=theme.NEON_MAGENTA,
        ).pack(side="left", padx=4)

        self.refresh()

    def refresh(self) -> None:
        self.tree.delete(*self.tree.get_children())
        global_list = self.list_type()
        for ip, name in global_list:
            self.tree.insert("", "end", iid=ip, values=(ip,))

    def _selected_ip(self) -> Optional[str]:
        selection = self.tree.selection()
        return selection[0] if selection else None

    def _on_add(self) -> None:
        self._open_form(
            title=t("form_title_add"), initial_ip="", existing_ip=None
        )

    def _on_edit(self) -> None:
        ip = self._selected_ip()
        if ip is None:
            return
        self._open_form(
            title=t("form_title_edit"), initial_ip=ip, existing_ip=ip
        )

    def _on_delete(self) -> None:
        ip = self._selected_ip()
        if ip is None:
            return
        global_list = self.list_type()
        global_list.remove(ip)
        global_list.save()
        self.refresh()
        self._reload_session_on_change()

    def _on_clear(self) -> None:
        global_list = self.list_type()
        global_list.data.clear()
        global_list.save()
        self.refresh()
        self._reload_session_on_change()

    def _reload_session_on_change(self) -> None:
        from menu.menu import Menu
        import threading
        if Menu.context.active_session_name() == "PrivateSession":
            is_locked = Menu.context.is_locked()
            threading.Thread(
                target=Menu.launch_private_session,
                args=(is_locked,),
                daemon=True,
            ).start()

    def _open_form(
        self, title: str, initial_ip: str, existing_ip: Optional[str]
    ) -> None:
        form = tk.Toplevel(self.root)
        form.title(title)
        form.configure(bg=theme.BG)
        form.transient(self.root)
        form.resizable(False, False)

        entry_kwargs: dict[str, object] = {
            "bg": theme.PANEL,
            "fg": theme.TEXT,
            "insertbackground": theme.TEXT,
            "relief": "flat",
            "highlightthickness": 1,
            "highlightbackground": theme.BORDER_DIM,
            "highlightcolor": theme.NEON_CYAN,
        }

        tk.Label(form, text=t("col_ip"), bg=theme.BG, fg=theme.TEXT).grid(
            row=0, column=0, sticky="w", padx=10, pady=(14, 2)
        )
        ip_entry = tk.Entry(form, width=28, **entry_kwargs)  # type: ignore[arg-type]
        ip_entry.insert(0, initial_ip)
        ip_entry.grid(row=1, column=0, padx=10, pady=(0, 10), ipady=3)

        error_label = tk.Label(
            form, text="", bg=theme.BG, fg=theme.DANGER, wraplength=260, justify="left"
        )
        error_label.grid(row=2, column=0, sticky="w", padx=10)

        def _save() -> None:
            ip = ip_entry.get().strip()
            global_list: GlobalList = self.list_type()

            try:
                ip = IPValidator.validate_get(ip)
            except ValidationError:
                error_label.configure(text=t("error_ip_invalid"))
                return

            from menu.menu import Menu
            from util.network import ip_in_cidr_block_set
            if self.list_type is Whitelist and ip_in_cidr_block_set(ip, Menu.dynamic_blacklist):
                error_label.configure(text=t("error_ip_is_rockstar_relay"))
                return

            if ip != existing_ip and ip in global_list:
                error_label.configure(text=t("error_ip_duplicate"))
                return

            if existing_ip is not None:
                global_list.remove(existing_ip)
            global_list.add(ip, "")
            global_list.save()
            self.refresh()
            self._reload_session_on_change()
            form.destroy()

        button_row = tk.Frame(form, bg=theme.BG)
        button_row.grid(row=3, column=0, pady=(6, 14))
        widgets.NeonButton(button_row, t("btn_save"), command=_save).pack(
            side="left", padx=6
        )
        widgets.NeonButton(
            button_row, t("btn_cancel"), command=form.destroy, accent=theme.NEON_MAGENTA
        ).pack(side="left", padx=6)

        from gui.dialogs import center_toplevel

        center_toplevel(form, self.root)
        form.grab_set()
