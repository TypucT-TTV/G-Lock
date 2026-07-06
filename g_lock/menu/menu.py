from __future__ import annotations

import logging
import threading
import time
from multiprocessing import Pipe
from typing import Any, Callable, ClassVar, Optional
from webbrowser import open as open_browser

import questionary

from config.configdata import ConfigData
from config.globallist import Blacklist, Whitelist
from dispatcher.context import Context
from gui.adapter import UIAdapter
from gui.i18n import t
from network.sessions import (
    AbstractPacketFilter,
    BlacklistSession,
    IPCollector,
    LockedSession,
    SoloSession,
    WhitelistSession,
)
from util.constants import DONATION_URL
from util.dynamicblacklist import get_dynamic_blacklist
from util.network import get_private_ip, get_public_ip, ip_in_cidr_block_set
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
    def launch_whitelisted_session() -> None:
        ip_set = set()
        debug_logger.debug("Validating whitelisted IPs")
        for ip, name in Menu.whitelist:
            try:
                ip_calc = IPValidator.validate_get(ip)
                ip_set.add(ip_calc)
            except questionary.ValidationError:
                print_invalid_ip(ip)
        Menu.launch_session(
            WhitelistSession,
            ips=ip_set,
            priority=Menu.context.priority,
            connection=Menu.child_conn,
        )

    @staticmethod
    def launch_blacklisted_session() -> None:
        ip_set = set()
        debug_logger.debug("Validating blacklisted IPs")
        for ip, name in Menu.blacklist:
            try:
                ip_calc = IPValidator.validate_get(ip)
                ip_set.add(ip_calc)
            except questionary.ValidationError:
                print_invalid_ip(ip)
        Menu.launch_session(
            BlacklistSession,
            ips=ip_set,
            priority=Menu.context.priority,
            connection=Menu.child_conn,
            blocks=Menu.dynamic_blacklist,
            known_allowed={PRIVATE_IP, PUBLIC_IP},
        )

    @staticmethod
    def launch_locked_session() -> None:
        Menu.launch_session(
            LockedSession, priority=Menu.context.priority, connection=Menu.child_conn
        )

    @staticmethod
    def launch_new_session() -> None:
        if Menu.confirm_session("empty_session"):
            session = SoloSession(Menu.context.priority, connection=Menu.child_conn)
            Menu.context.add_filter(session)
            Menu.context.start_latest_filter()

    @staticmethod
    def launch_auto_whitelisted_session() -> None:
        if not Menu.confirm_session("auto_whitelisted_session"):
            return

        cancelled = False

        def _collect(
            on_tick: Callable[[int], None], cancel_event: threading.Event
        ) -> set[str]:
            nonlocal cancelled
            result = Menu.collect_active_ips(
                60, on_tick=on_tick, cancel_event=cancel_event
            )
            cancelled = cancel_event.is_set()
            return result

        ip_set = Menu.ui.run_with_progress(t("name_auto_whitelisted_session"), 60, _collect)
        if cancelled:
            return

        potential_tunnels = {
            ip
            for ip in ip_set
            if ip_in_cidr_block_set(ip, Menu.dynamic_blacklist)
            and ip not in Menu.whitelist
        }
        if potential_tunnels:
            kept = Menu.ui.select_multiple(
                t("tunnels_title"),
                t("tunnels_warning", count=len(potential_tunnels)),
                list(potential_tunnels),
            )
            for ip in kept:
                potential_tunnels.remove(ip)
            for ip in potential_tunnels:
                ip_set.remove(ip)
        session = WhitelistSession(
            ip_set, Menu.context.priority, connection=Menu.child_conn
        )
        Menu.context.add_filter(session)
        Menu.context.start_latest_filter()

    @staticmethod
    def kick_unknowns() -> None:
        if not Menu.confirm_session("kick_unknowns"):
            return
        ip_set = set()
        for ip, name in Menu.whitelist:
            try:
                ip_calc = IPValidator.validate_get(ip)
                ip_set.add(ip_calc)
            except questionary.ValidationError:
                print_invalid_ip(ip)
        session = WhitelistSession(
            ip_set, Menu.context.priority, connection=Menu.child_conn
        )
        Menu.context.add_filter(session)
        Menu.context.start_latest_filter()
        Menu._wait_with_progress(10, t("name_kick_unknowns"))
        Menu.context.kill_latest_filter()

    @staticmethod
    def kick_by_ip() -> None:
        if not Menu.confirm_session("kick_by_ip"):
            return

        cancelled = False

        def _collect(
            on_tick: Callable[[int], None], cancel_event: threading.Event
        ) -> set[str]:
            nonlocal cancelled
            result = Menu.collect_active_ips(
                60, on_tick=on_tick, cancel_event=cancel_event
            )
            cancelled = cancel_event.is_set()
            return result

        ip_set = Menu.ui.run_with_progress(t("name_kick_by_ip"), 60, _collect)
        if cancelled:
            return

        choices = Menu.ui.select_multiple(
            t("name_kick_by_ip"), t("kick_by_ip_message"), list(ip_set)
        )
        for ip in choices:
            ip_set.remove(ip)
        session = WhitelistSession(
            ip_set, Menu.context.priority, connection=Menu.child_conn
        )
        Menu.context.add_filter(session)
        Menu.context.start_latest_filter()
        Menu._wait_with_progress(10, t("name_kick_by_ip"))
        Menu.context.kill_latest_filter()

    @staticmethod
    def open_donation() -> None:
        open_browser(DONATION_URL)

    @staticmethod
    def stop_session() -> None:
        """Disables whatever session filter is currently active, going back
        to no filtering at all. Deliberately a separate action from the
        session-launch buttons/methods above, rather than having each of
        those toggle itself off on a second click."""
        if Menu.context.is_filter_running():
            Menu.context.kill_latest_filter()

    @staticmethod
    def collect_active_ips(
        duration_seconds: int = 60,
        on_tick: Optional[Callable[[int], None]] = None,
        cancel_event: Optional[threading.Event] = None,
    ) -> set[str]:
        collector = IPCollector(Menu.context.priority, packet_count_min_threshold=15)
        collector.start()
        for i in range(duration_seconds):
            if cancel_event is not None and cancel_event.is_set():
                break
            time.sleep(1)
            if on_tick is not None:
                on_tick(i + 1)
        collector.stop()
        return set(collector.ips)

    @staticmethod
    def _wait_with_progress(seconds: int, label: str) -> None:
        def _work(on_tick: Callable[[int], None], cancel_event: threading.Event) -> None:
            for i in range(seconds):
                if cancel_event.is_set():
                    break
                time.sleep(1)
                on_tick(i + 1)

        Menu.ui.run_with_progress(label, seconds, _work)


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
        {"id": "whitelisted_session", "value": Menu.launch_whitelisted_session},
        {"id": "blacklisted_session", "value": Menu.launch_blacklisted_session},
        {"id": "auto_whitelisted_session", "value": Menu.launch_auto_whitelisted_session},
        {"id": "locked_session", "value": Menu.launch_locked_session},
        {"id": "kick_unknowns", "value": Menu.kick_unknowns},
        {"id": "empty_session", "value": Menu.launch_new_session},
        {"id": "kick_by_ip", "value": Menu.kick_by_ip},
        {"id": "edit_lists", "value": EDIT_LISTS},
        {"id": "edit_settings", "value": EDIT_SETTINGS},
        {"id": "donate", "value": Menu.open_donation},
        {"id": "quit", "value": QUIT},
    ]

    # Keys used by Menu.confirm_session() to look up "name_{key}" /
    # "explain_{key}" translation strings for a given session launch.
    SESSION_KEYS: dict[type[AbstractPacketFilter] | str, str] = {
        SoloSession: "solo_session",
        WhitelistSession: "whitelisted_session",
        BlacklistSession: "blacklisted_session",
        LockedSession: "locked_session",
        "auto_whitelisted_session": "auto_whitelisted_session",
        "kick_unknowns": "kick_unknowns",
        "empty_session": "empty_session",
        "kick_by_ip": "kick_by_ip",
    }
