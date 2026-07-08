from __future__ import annotations

import logging
from multiprocessing import Pipe
from typing import Any, Callable, ClassVar
from webbrowser import open as open_browser

import questionary

from config.configdata import ConfigData
from config.globallist import Blacklist, Whitelist
from dispatcher.context import Context
from gui.adapter import UIAdapter
from gui.i18n import t
from network.sessions import AbstractPacketFilter, PrivateSession, SoloSession
from util.constants import DONATION_URL
from util.dynamicblacklist import get_dynamic_blacklist
from util.network import construct_cidr_block_set, get_private_ip, get_public_ip
from util.printer import print_invalid_ip
from validator.ip import IPValidator

debug_logger = logging.getLogger("debugger")

PRIVATE_IP = get_private_ip()
PUBLIC_IP = get_public_ip()


class Menu:
    parent_conn, child_conn = Pipe()
    context = Context(parent_conn)
    config = ConfigData()
    blacklist = Blacklist()
    whitelist = Whitelist()
    dynamic_blacklist = get_dynamic_blacklist()

    # Set once, by __main__.py, before any of the methods below run. Business
    # logic here is UI-toolkit-agnostic: it only ever talks to Menu.ui, never
    # to tkinter (or questionary) directly, so it can be exercised the same
    # way regardless of what's presenting the confirm/select/progress prompts.
    ui: ClassVar[UIAdapter]

    @staticmethod
    def confirm_session(session_type: type[AbstractPacketFilter] | str) -> bool:
        key = Prompts.SESSION_KEYS[session_type]
        name = t(f"name_{key}")
        explanation = t(f"explain_{key}")
        return Menu.ui.confirm(t("confirm_title", name=name), explanation)

    @staticmethod
    def launch_session(
        session_type: type[AbstractPacketFilter], *args: Any, **kwargs: Any
    ) -> None:
        if Menu.confirm_session(session_type):
            session = session_type(*args, **kwargs)
            Menu.context.add_filter(session)
            Menu.context.start_latest_filter()

    @staticmethod
    def launch_solo_session() -> None:
        Menu.launch_session(
            SoloSession, priority=Menu.context.priority, connection=Menu.child_conn
        )

    @staticmethod
    def launch_private_session(locked: bool) -> None:
        if Menu.context.is_filter_running():
            Menu.context.kill_latest_filter()

        ip_set = set()
        cidr_set = set()
        for ip, name in Menu.whitelist:
            try:
                ip_calc = IPValidator.validate_get(ip)
                if "/" in ip_calc:
                    cidr_set.add(ip_calc)
                else:
                    ip_set.add(ip_calc)
            except questionary.ValidationError:
                print_invalid_ip(ip)
        whitelist_blocks = construct_cidr_block_set(list(cidr_set))

        blacklist_ips = set()
        blacklist_cidr = set()
        for ip, name in Menu.blacklist:
            try:
                ip_calc = IPValidator.validate_get(ip)
                if "/" in ip_calc:
                    blacklist_cidr.add(ip_calc)
                else:
                    blacklist_ips.add(ip_calc)
            except questionary.ValidationError:
                pass
        blacklist_blocks = construct_cidr_block_set(list(blacklist_cidr))

        session = PrivateSession(
            locked=locked,
            priority=Menu.context.priority,
            connection=Menu.child_conn,
            whitelist_ips=ip_set,
            whitelist_blocks=whitelist_blocks,
            blacklist_ips=blacklist_ips,
            blacklist_blocks=blacklist_blocks,
            dynamic_blacklist=Menu.dynamic_blacklist,
            known_allowed={PRIVATE_IP, PUBLIC_IP},
        )
        session.mode_label = "PrivateSessionLocked" if locked else "PrivateSessionOpen"
        Menu.context.add_filter(session)
        Menu.context.start_latest_filter()

    @staticmethod
    def toggle_lock() -> None:
        is_locked = Menu.context.is_locked()
        Menu.launch_private_session(locked=not is_locked)

    @staticmethod
    def launch_new_session() -> None:
        if Menu.confirm_session("empty_session"):
            session = SoloSession(Menu.context.priority, connection=Menu.child_conn)
            Menu.context.add_filter(session)
            Menu.context.start_latest_filter()

    @staticmethod
    def open_donation() -> None:
        open_browser(DONATION_URL)

    @staticmethod
    def launch_default_blacklist_session() -> None:
        Menu.launch_private_session(locked=False)

    @staticmethod
    def stop_session() -> None:
        """Disables whatever session filter is currently active, and automatically
        falls back to the default blacklist filter."""
        if Menu.context.is_filter_running():
            Menu.context.kill_latest_filter()
        Menu.launch_default_blacklist_session()


class Prompts:
    # "value" is either a zero-arg callable to run on a background thread, or
    # one of the string sentinels below for entries MainWindow special-cases
    # (they need a Tk parent widget / the main thread itself, neither of
    # which a plain Callable[[], None] can carry).
    EDIT_LISTS = "edit_lists"
    EDIT_SETTINGS = "edit_settings"
    QUIT = "quit"

    # Each entry's "id" is a stable, language-independent identifier: it's
    # used both as the i18n key suffix for the button's display text
    # (t(f"menu_{id}")) and, in gui/main_window.py, to look up which
    # AbstractPacketFilter subclass (if any) that button corresponds to for
    # its on/off indicator dot. Display text must never be used for that kind
    # of lookup, since it changes with the selected language.
    MAIN_MENU: list[dict[str, str | Callable[[], None]]] = [
        {"id": "solo_session", "value": Menu.launch_solo_session},
        {"id": "empty_session", "value": Menu.launch_new_session},
        {"id": "edit_lists", "value": EDIT_LISTS},
        {"id": "edit_settings", "value": EDIT_SETTINGS},
        {"id": "donate", "value": Menu.open_donation},
        {"id": "quit", "value": QUIT},
    ]

    # Keys used by Menu.confirm_session() to look up "name_{key}" /
    # "explain_{key}" translation strings for a given session launch.
    SESSION_KEYS: dict[type[AbstractPacketFilter] | str, str] = {
        SoloSession: "solo_session",
        PrivateSession: "private_session",
        "empty_session": "empty_session",
    }
