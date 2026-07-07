"""
Detailed, per-second aggregated packet logging used to identify the source of
crash/flood attacks while a session is open. Deliberately separate from
connectionlog.py's lightweight "who joined and when" log: this one classifies
every inbound peer (friend / R*-Azure tunnel / LAN / unknown), records an
allow/block decision summary once per second per peer, and raises an
immediate warning if any single peer's packet rate crosses a flood threshold.

Writing to disk happens on a background thread (see verbose_log_listener_loop,
started from gui/main_window.py) that drains _verbose_queue — the packet loop
in network/sessions.py only ever does a cheap dict update plus, at most, one
queue.put() per active peer per second.
"""

from __future__ import annotations

import logging
import multiprocessing
import time
from datetime import date
from pathlib import Path
from typing import Any, Optional, TextIO

from util.network import construct_cidr_block_set, ip_in_cidr_block_set
from util.types import CIDR_BLOCK

logger = logging.getLogger(__name__)

LOG_DIR = Path("logs")
MAX_LOG_FILES = 10
FLOOD_WINDOW_SECONDS = 1.0

# Azure relay ranges observed being used for R* Services tend to fall under
# 52.139.x.x specifically, in addition to whatever's in the full dynamic
# blacklist (see util/dynamicblacklist.py) - checked as a cheap prefix test
# before falling back to the full CIDR search.
_AZURE_RELAY_PREFIX = "52.139."

# Shared Queue at module level (instantiated in the parent process, passed to
# child filter processes), same pattern as network/connectionlog.py.
_verbose_queue: Any = multiprocessing.Queue()


def _timestamp() -> str:
    now = time.time()
    millis = int(now * 1000) % 1000
    return time.strftime("%H:%M:%S", time.localtime(now)) + f".{millis:03d}"


def is_lan_ip(ip: str) -> bool:
    parts = ip.split(".")
    if len(parts) != 4:
        return False
    try:
        first, second = int(parts[0]), int(parts[1])
    except ValueError:
        return False
    return (
        first == 10
        or (first == 192 and second == 168)
        or (first == 172 and 16 <= second <= 31)
    )


def classify_ip(
    ip: str,
    whitelist_ips: set[str],
    whitelist_cidr_blocks: set[CIDR_BLOCK],
    dynamic_blacklist: set[CIDR_BLOCK],
) -> str:
    if ip in whitelist_ips or ip_in_cidr_block_set(ip, whitelist_cidr_blocks):
        return "WHITELIST_FRIEND"
    if ip.startswith(_AZURE_RELAY_PREFIX) or ip_in_cidr_block_set(
        ip, dynamic_blacklist
    ):
        return "R_STAR_AZURE"
    if is_lan_ip(ip):
        return "LAN"
    return "UNKNOWN"


def canonical_reason(cls: str, decision: bool, raw_reason: str) -> str:
    """Maps the free-text reason strings returned by is_packet_allowed() (which
    differ per session type) down to the fixed reason vocabulary used in the
    verbose log."""
    raw = raw_reason.lower()
    if cls == "LAN":
        return "LAN"
    if (
        "whitelisted ip" in raw
        or "whitelisted range" in raw
        or "matchmaker bypass" in raw
    ):
        return "WHITELIST"
    if cls == "R_STAR_AZURE":
        return "R*_SERVICE" if decision else "DYN_TUNNEL"
    if "blacklist" in raw:
        return "BLACKLIST"
    return "UNKNOWN_PEER"


def build_classification_context() -> (
    tuple[bool, int, set[str], set[CIDR_BLOCK], set[CIDR_BLOCK]]
):
    """
    Snapshots the data needed to classify IPs and gate verbose logging, for a
    session about to be started.

    Must be called from the parent process (network/sessions.py's
    AbstractPacketFilter.__init__ runs there) rather than from inside a
    spawned filter process: importing menu.menu fresh inside a child process
    would re-run its module-level network calls (RIPE/Azure/ipify) all over
    again instead of reusing the already-fetched data.
    """
    from menu.menu import Menu

    verbose_enabled = bool(Menu.config.get("verbose_logging_enabled", True))
    flood_threshold = int(Menu.config.get("verbose_flood_threshold", 50))

    whitelist_ips: set[str] = set()
    whitelist_cidr: list[str] = []
    for ip, _name in Menu.whitelist:
        if "/" in ip:
            whitelist_cidr.append(ip)
        else:
            whitelist_ips.add(ip)

    return (
        verbose_enabled,
        flood_threshold,
        whitelist_ips,
        construct_cidr_block_set(whitelist_cidr),
        Menu.dynamic_blacklist,
    )


def write_marker(text: str) -> None:
    """Writes a session-event marker line to the verbose log (e.g. F9
    lock/unlock, session start/stop). Safe to call from any process; a
    failure here must never affect packet filtering."""
    try:
        _verbose_queue.put(f"[{_timestamp()}] === {text} ===")
    except Exception:
        logger.exception("Failed to write verbose log marker")


class _IPWindow:
    __slots__ = ("count", "port", "decision", "reason", "cls", "flood_warned")

    def __init__(self) -> None:
        self.count = 0
        self.port = 0
        self.decision = False
        self.reason = ""
        self.cls = "UNKNOWN"
        self.flood_warned = False


class VerboseAggregator:
    """
    Aggregates per-packet allow/block decisions into one summary line per
    active source IP per second (instead of one line per packet), so verbose
    logging never adds more than one queue.put() per active peer per second
    to the packet loop's hot path. Flood detection piggybacks on the same
    per-second counters and fires an immediate WARN the moment an IP crosses
    the configured packets/sec threshold.
    """

    def __init__(self, mode_label: str, flood_threshold: int, verbose_queue: Any):
        self.mode_label = mode_label
        self.flood_threshold = flood_threshold
        self.verbose_queue = verbose_queue
        self._window_start = time.monotonic()
        self._windows: dict[str, _IPWindow] = {}

    def record(self, ip: str, port: int, cls: str, decision: bool, reason: str) -> None:
        try:
            window = self._windows.get(ip)
            if window is None:
                window = _IPWindow()
                self._windows[ip] = window
            window.count += 1
            window.port = port
            window.decision = decision
            window.reason = reason
            window.cls = cls
            if not window.flood_warned and window.count >= self.flood_threshold:
                window.flood_warned = True
                self._emit_flood(ip, port, cls, decision, window.count)
            self._maybe_flush()
        except Exception:
            logger.exception("Verbose aggregator failed to record a packet")

    def _emit_flood(
        self, ip: str, port: int, cls: str, decision: bool, count: int
    ) -> None:
        decision_str = "ALLOW" if decision else "BLOCK"
        self.verbose_queue.put(
            f"[{_timestamp()}] !!! FLOOD from {ip}:{port}  class={cls}  "
            f"decision={decision_str}  {count} pkt/s"
        )

    def _maybe_flush(self) -> None:
        now = time.monotonic()
        if now - self._window_start < FLOOD_WINDOW_SECONDS:
            return
        self._window_start = now
        if not self._windows:
            return
        timestamp = _timestamp()
        for ip, window in self._windows.items():
            decision_str = "ALLOW" if window.decision else "BLOCK"
            self.verbose_queue.put(
                f"[{timestamp}] IN  {ip}:{window.port}  {window.cls}  "
                f"{decision_str}  pkts={window.count}  reason={window.reason}  "
                f"mode={self.mode_label}"
            )
        self._windows.clear()


def _prune_old_verbose_logs() -> None:
    files = sorted(LOG_DIR.glob("verbose_*.log"))
    for old_file in files[:-MAX_LOG_FILES]:
        old_file.unlink(missing_ok=True)


def verbose_log_listener_loop(verbose_queue: Any) -> None:
    LOG_DIR.mkdir(exist_ok=True)
    _prune_old_verbose_logs()

    current_date: Optional[date] = None
    handle: Optional[TextIO] = None

    while True:
        try:
            line = verbose_queue.get()
            if line is None:
                break

            today = date.today()
            if today != current_date:
                if handle is not None:
                    handle.close()
                current_date = today
                handle = (LOG_DIR / f"verbose_{today.isoformat()}.log").open(
                    "a", encoding="utf-8"
                )
                _prune_old_verbose_logs()

            assert handle is not None
            handle.write(line + "\n")
            handle.flush()
        except Exception:
            logger.exception("Error in verbose_log_listener_loop")
