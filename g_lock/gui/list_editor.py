from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Optional

from questionary import ValidationError

from config.globallist import Blacklist, GlobalList, Whitelist
from gui import theme, widgets
from gui.i18n import t
from validator.ip import IPValidator
from validator.name import NameValidator


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

        columns = ("name", "ip")
        self.tree = ttk.Treeview(parent, columns=columns, show="headings", height=10)
        self.tree.heading("name", text=t("col_name"))
        self.tree.heading("ip", text=t("col_ip"))
        self.tree.column("name", width=200)
        self.tree.column("ip", width=200)
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

        self.refresh()

    def refresh(self) -> None:
        self.tree.delete(*self.tree.get_children())
        global_list = self.list_type()
        for ip, name in global_list:
            self.tree.insert("", "end", iid=ip, values=(name, ip))

    def _selected_ip(self) -> Optional[str]:
        selection = self.tree.selection()
        return selection[0] if selection else None

    def _on_add(self) -> None:
        self._open_form(
            title=t("form_title_add"), initial_name="", initial_ip="", existing_ip=None
        )

    def _on_edit(self) -> None:
        ip = self._selected_ip()
        if ip is None:
            return
        global_list = self.list_type()
        name = global_list.get(ip, "")
        self._open_form(
            title=t("form_title_edit"), initial_name=name, initial_ip=ip, existing_ip=ip
        )

    def _on_delete(self) -> None:
        ip = self._selected_ip()
        if ip is None:
            return
        global_list = self.list_type()
        global_list.remove(ip)
        global_list.save()
        self.refresh()

    def _open_form(
        self, title: str, initial_name: str, initial_ip: str, existing_ip: Optional[str]
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

        tk.Label(form, text=t("col_name"), bg=theme.BG, fg=theme.TEXT).grid(
            row=0, column=0, sticky="w", padx=10, pady=(14, 2)
        )
        name_entry = tk.Entry(form, width=28, **entry_kwargs)  # type: ignore[arg-type]
        name_entry.insert(0, initial_name)
        name_entry.grid(row=1, column=0, padx=10, pady=(0, 10), ipady=3)

        tk.Label(form, text=t("col_ip"), bg=theme.BG, fg=theme.TEXT).grid(
            row=2, column=0, sticky="w", padx=10
        )
        ip_entry = tk.Entry(form, width=28, **entry_kwargs)  # type: ignore[arg-type]
        ip_entry.insert(0, initial_ip)
        ip_entry.grid(row=3, column=0, padx=10, pady=(0, 10), ipady=3)

        error_label = tk.Label(
            form, text="", bg=theme.BG, fg=theme.DANGER, wraplength=260, justify="left"
        )
        error_label.grid(row=4, column=0, sticky="w", padx=10)

        def _save() -> None:
            name = name_entry.get().strip()
            ip = ip_entry.get().strip()
            global_list: GlobalList = self.list_type()

            if name != initial_name or existing_ip is None:
                try:
                    name = NameValidator.validate_get(name, global_list)
                except ValidationError:
                    error_label.configure(text=t("error_name_duplicate"))
                    return

            try:
                ip = IPValidator.validate_get(ip)
            except ValidationError:
                error_label.configure(text=t("error_ip_invalid"))
                return

            if ip != existing_ip and ip in global_list:
                error_label.configure(text=t("error_ip_duplicate"))
                return

            if existing_ip is not None:
                global_list.remove(existing_ip)
            global_list.add(ip, name)
            global_list.save()
            self.refresh()
            form.destroy()

        button_row = tk.Frame(form, bg=theme.BG)
        button_row.grid(row=5, column=0, pady=(6, 14))
        widgets.NeonButton(button_row, t("btn_save"), command=_save).pack(
            side="left", padx=6
        )
        widgets.NeonButton(
            button_row, t("btn_cancel"), command=form.destroy, accent=theme.NEON_MAGENTA
        ).pack(side="left", padx=6)

        from gui.dialogs import center_toplevel

        center_toplevel(form, self.root)
        form.grab_set()
