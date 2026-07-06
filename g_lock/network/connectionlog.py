import contextlib
import logging
import time
from datetime import date
from multiprocessing import Process
from pathlib import Path
from typing import Optional, TextIO

import pydivert

from network.sessions import MATCHMAKING_SIZES, PACKET_FILTER

logger = logging.getLogger(__name__)

LOG_DIR = Path("logs")
MAX_LOG_FILES = 10
# Once an IP has been logged, ignore further matchmaking-sized packets from
# it for this long before logging it again — avoids one join spamming
# several near-identical lines, while still logging a fresh disconnect+rejoin.
REJOIN_COOLDOWN_SECONDS = 30
# Priority is fixed and deliberately outside the range Context hands out to
# session filters (which starts at 0 and counts up) — this logger isn't
# managed by Context at all, it runs for G-Lock's entire lifetime
# regardless of which (if any) session filter is currently active.
LOGGER_PRIORITY = -100


def _prune_old_logs() -> None:
    files = sorted(LOG_DIR.glob("connections_*.log"))
    for old_file in files[:-MAX_LOG_FILES]:
        old_file.unlink(missing_ok=True)


class ConnectionLogger:
    """
    Runs continuously for G-Lock's entire lifetime, independent of
    whichever session filter (if any) is active via Context. Passively
    observes traffic (pydivert.Flag.SNIFF — doesn't block or interfere with
    any other active filter, including "no filter" at all) and appends a
    dated, rotating text log of which IPs appear to send join/matchmaking
    packets and when, so a cheater who got into a session can be identified
    after the fact.
    """

    def __init__(self, priority: int = LOGGER_PRIORITY):
        self.priority = priority
        self.process = Process(target=self.run, daemon=True)

    def start(self) -> None:
        self.process.start()
        logger.info("Dispatched ConnectionLogger process")

    def run(self) -> None:
        LOG_DIR.mkdir(exist_ok=True)
        _prune_old_logs()

        current_date: Optional[date] = None
        handle: Optional[TextIO] = None
        last_seen: dict[str, float] = {}

        with contextlib.suppress(KeyboardInterrupt):
            with pydivert.WinDivert(
                PACKET_FILTER, priority=self.priority, flags=pydivert.Flag.SNIFF
            ) as w:
                for packet in w:
                    if not packet.is_inbound or len(packet.payload) not in MATCHMAKING_SIZES:
                        continue

                    ip = packet.ip.src_addr
                    now = time.monotonic()
                    if ip in last_seen and now - last_seen[ip] < REJOIN_COOLDOWN_SECONDS:
                        continue
                    last_seen[ip] = now

                    today = date.today()
                    if today != current_date:
                        if handle is not None:
                            handle.close()
                        current_date = today
                        handle = (LOG_DIR / f"connections_{today.isoformat()}.log").open(
                            "a", encoding="utf-8"
                        )
                        _prune_old_logs()

                    assert handle is not None  # always set by the block above
                    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
                    handle.write(f"[{timestamp}] {ip}\n")
                    handle.flush()
