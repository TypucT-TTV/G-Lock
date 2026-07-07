from __future__ import annotations

import contextlib
import logging
import re
from abc import ABC, abstractmethod
from multiprocessing import Process
from multiprocessing.connection import PipeConnection
from typing import Any, Optional

import pydivert

from network.sessioninfo import SessionInfo
from util.network import find_matching_cidr_block, ip_in_cidr_block_set
from util.types import CIDR_BLOCK

logger = logging.getLogger(__name__)
debug_logger = logging.getLogger("debugger")

# It appears that there is *ONE* more problem we may need to take care of which was missed during testing of the prototype.
# Apparently, it's not only R* tunnels, but also client tunnels! If the circumstances are right, then it turns out that
# people in your session can also tunnel players if they could not connect to you directly. Such is the joy of P2P
# gaming.

# This conundrum could be easily solved with packet inspection but I'm going go back on my previous words and try to
# solve this by filtering some outbound packets, as it's the only solution I can think of.

# My idea is that if we receive a matchmaking request (or what could be a matchmaking request), then we will temporarily
# drop responses from us to any other client in the session. This, again, will have to be guessed from the payload size.
# Currently, I have no idea whether the responses to matchmaking requests are unique enough to be blocked without risking
# dropping other game traffic from someone who is actually in the session.

# It's possible that this behaviour can be mitigated by making the whitelist filter "air-tight" as there was a bug in the
# official build which was leaking packets. However, if this bug is reported significantly in testing then I'll go ahead
# and develop my theoretical solution.

# The main flaw in G-Lock lied here, in the reserved IP range. I believe this is the R* / T2 IP space, right?
# In the current public build, any packet from these IPs is allowed, but we can no longer do this. We have to block
# tunnelled connections which may come from this IP range, while still allowing certain services like the
# session heartbeat and matchmaking requests.

# Currently, my proof-of-concept does not discern whether a heartbeat has come from a R* / T2 IP as I have not been able
# to confirm if that actually is the case. Ideally, ipfilter should be a range of all IPs that can send heartbeats
# and / or matchmaking requests, and so the checks for packet sizes will be done only if the packet has come from an IP
# in the ipfilter range.

# So, ipfilter's usage has been removed from the Whitelist class. I didn't completely remove it because I think it would
# still be useful to compare how the new rules can drop tunnels while still letting heartbeats and matchmaking through.

ipfilter = re.compile(r"^(185\.56\.6[4-7]\.\d{1,3})$")

# I decided to filter only on packets inbound to 6672 because most of the new filtering logic only checks inbound packets,
# and I don't think it makes much sense to add extra load by checking outbound packets when we're not doing
# anything interesting with them at the moment. I also found the packet payload sizes to be more consistent when coming
# from R*-owned resources instead of looking at the responses to those requests.
# I also believe that strictly filtering on inbound helps the game remain unaware that packets are being filtered and
# this might mean that the game will probably behave in a more consistent manner.
# (If the game was aware packets weren't reaching clients, it may change its behaviour)

# NOTE: If R* ever updates Online to support IPv6, then "and ip" should be removed from packetfilter,
# and parts of the filter logic (in the Whitelist class) that use the packet.ip attribute should be changed.

# PACKET_FILTER = "udp.SrcPort == 6672 or udp.DstPort == 6672 and ip"
PACKET_FILTER = "udp.DstPort == 6672 and udp.PayloadLength > 0 and ip"

# Based on network observation, the payload sizes of packets which are probably some sort of heartbeat (and therefore
# should be let through so the session stays online), or a matchmaking request (and therefore should be let through so we
# can see who's attempting to connect to us).

# Interesting note: All the matchmaker requests have payload sizes that may be 16 bytes apart.

HEARTBEAT_SIZES = {12, 18, 63}
MATCHMAKING_SIZES = {
    191,
    207,
    223,
    239,
}  # probably a player looking to join the session.
DTLs = {0xFEFF, 0xFEFD}
KNOWNS = {0x39, 0x31, 0x29}
# RECORDS = {20, 21, 22, 23}


KNOWN_SIZES = HEARTBEAT_SIZES.union(MATCHMAKING_SIZES)

# Matchmaking response sizes might be: 45, 125, 205?
# The size 45 payload definitely cannot be blocked as it pops up frequently in normal gameplay.
# It appears that the 125 and 205 packets also pop up from time to time.
# The first *two* packets sent to a client joining do appear to be size 125 and 205, though. Hmmm...
# So the initial join response appears to be 125, 205, 45, 317, 493?

# Looks like blocking 205 inbound is our best bet. 493 outbound is also a possibility but probably has a chance of
# accidentally dropping the client non-tunnels.

# After I wrote these comments it was discovered that G-Lock wasn't filtering packets all the time. This bug has since
# been fixed and hopefully will also mean these "client tunnels" are now no longer an issue. Leaving these notes in just
# in case they're useful later on.


class AbstractPacketFilter(ABC):
    def __init__(
        self,
        ips: set[str],
        priority: int,
        connection: PipeConnection,
        session_info: Optional[SessionInfo] = None,
        debug: bool = False,
    ):
        self.ips = ips
        self.priority = priority
        self.queue = connection
        self.mode_label = self.__class__.__name__.replace("Session", "")
        from network.connectionlog import _filter_active_event, _log_queue
        from network.verboselog import _verbose_queue, build_classification_context

        (
            verbose_enabled,
            flood_threshold,
            whitelist_ips,
            whitelist_cidr_blocks,
            dynamic_blacklist,
        ) = build_classification_context()

        self.process = Process(
            target=self.run,
            args=(
                _log_queue,
                _filter_active_event,
                _verbose_queue,
                verbose_enabled,
                flood_threshold,
                whitelist_ips,
                whitelist_cidr_blocks,
                dynamic_blacklist,
            ),
            daemon=True,
        )
        self.session_info = session_info
        self.debug_print_decisions = debug

    def __str__(self) -> str:
        return f"{self.__class__.__name__} with priority {self.priority}"

    def start(self) -> None:
        self.process.start()
        logger.info("Dispatched %s blocker process", self.__class__.__name__)
        from network.verboselog import write_marker

        write_marker(f"SESSION STARTED ({self.mode_label})")

    def stop(self) -> None:
        self.process.terminate()
        self.process.join()
        from network.connectionlog import _filter_active_event
        from network.verboselog import write_marker

        _filter_active_event.clear()
        logger.info("Terminated %s blocker process", self.__class__.__name__)
        write_marker(f"SESSION STOPPED ({self.mode_label})")

    @abstractmethod
    def is_packet_allowed(self, packet: pydivert.Packet) -> tuple[bool, str]:
        pass

    def run(
        self,
        log_queue: Any,
        filter_active_event: Any,
        verbose_queue: Any,
        verbose_enabled: bool,
        flood_threshold: int,
        whitelist_ips: set[str],
        whitelist_cidr_blocks: set[CIDR_BLOCK],
        dynamic_blacklist: set[CIDR_BLOCK],
    ) -> None:
        import time

        from network.connectionlog import REJOIN_COOLDOWN_SECONDS
        from network.verboselog import VerboseAggregator, canonical_reason, classify_ip

        filter_active_event.set()

        last_seen: dict[tuple[str, bool], float] = {}
        # Classification only depends on (mostly static) whitelist/dynamic
        # blacklist data, not on the packet itself, so it's cached per-IP
        # rather than recomputed every packet — matters most for a flood,
        # where the same source IP repeats hundreds of times a second.
        classification_cache: dict[str, str] = {}
        aggregator = (
            VerboseAggregator(self.mode_label, flood_threshold, verbose_queue)
            if verbose_enabled
            else None
        )

        with contextlib.suppress(KeyboardInterrupt):
            self.queue.send(True)
            with pydivert.WinDivert(PACKET_FILTER, priority=self.priority) as w:
                for packet in w:
                    decision, reason = self.is_packet_allowed(packet)
                    if decision:
                        w.send(packet)

                    if self.session_info is not None:
                        self.session_info.add_packet(packet, allowed=decision)

                    if self.debug_print_decisions:
                        print(self.construct_debug_packet_info(packet, decision))

                    ip = packet.ip.src_addr
                    now = time.monotonic()

                    # Cooldown-based logging to history log
                    should_log = (
                        not decision or len(packet.payload) in MATCHMAKING_SIZES
                    )
                    if should_log:
                        cooldown_key = (ip, decision)
                        if (
                            cooldown_key not in last_seen
                            or now - last_seen[cooldown_key] >= REJOIN_COOLDOWN_SECONDS
                        ):
                            last_seen[cooldown_key] = now
                            timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
                            action = "ALLOW" if decision else "BLOCK"
                            log_queue.put(
                                (
                                    timestamp,
                                    ip,
                                    action,
                                    len(packet.payload),
                                    reason,
                                )
                            )

                    if aggregator is not None and packet.is_inbound:
                        cls = classification_cache.get(ip)
                        if cls is None:
                            cls = classify_ip(
                                ip,
                                whitelist_ips,
                                whitelist_cidr_blocks,
                                dynamic_blacklist,
                            )
                            classification_cache[ip] = cls
                        aggregator.record(
                            ip,
                            packet.src_port,
                            cls,
                            decision,
                            canonical_reason(cls, decision, reason),
                        )

    @staticmethod
    def construct_debug_packet_info(
        packet: pydivert.Packet, decision: Optional[bool] = None
    ) -> str:
        prefix = "" if decision is None else ("ALLOWING" if decision else "DROPPING")

        return f"{prefix} PACKET FROM {packet.src_addr}:{packet.src_port}  Len: {len(packet.payload)}"


class SoloSession(AbstractPacketFilter):
    """
    Packet filter that does not allow join requests at all. Previously, Solo Session was actually just
    "Whitelisted" with an empty list. This variant is technically more secure if you truly don't want anything
    connecting to your client except the heartbeat.
    """

    def __init__(
        self,
        priority: int,
        connection: PipeConnection,
        session_info: Optional[SessionInfo] = None,
        debug: bool = False,
    ):
        super().__init__(set(), priority, connection, session_info, debug)

    def is_packet_allowed(self, packet: pydivert.Packet) -> tuple[bool, str]:
        size = len(packet.payload)

        if size in HEARTBEAT_SIZES:
            return True, "Heartbeat"
        return False, "Solo Session Active"


class PrivateSession(AbstractPacketFilter):
    """
    Unified packet filter that combines whitelist, blacklist (including dynamic
    Azure/Rockstar ranges), and optional Lock state.
    """

    def __init__(
        self,
        locked: bool,
        priority: int,
        connection: PipeConnection,
        whitelist_ips: set[str],
        whitelist_blocks: set[CIDR_BLOCK],
        blacklist_ips: set[str],
        blacklist_blocks: set[CIDR_BLOCK],
        known_allowed: Optional[set[str]] = None,
        session_info: Optional[SessionInfo] = None,
        debug: bool = False,
    ) -> None:
        super().__init__(whitelist_ips, priority, connection, session_info, debug)
        self.locked = locked
        self.whitelist_ips = whitelist_ips
        self.whitelist_blocks = whitelist_blocks
        self.blacklist_ips = blacklist_ips
        self.blacklist_blocks = blacklist_blocks
        self.known_allowed = known_allowed if known_allowed is not None else set()

    def _is_lan_ip(self, ip: str) -> bool:
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

    def is_packet_allowed(self, packet: pydivert.Packet) -> tuple[bool, str]:
        ip = packet.ip.src_addr
        size = len(packet.payload)

        # 0. Fast path for known allowed IPs
        if ip in self.known_allowed:
            return True, "Known Allowed IP"

        # 1. Check blacklist (always block)
        if ip in self.blacklist_ips:
            return False, "Blacklisted IP"

        matched_blacklist_cidr = find_matching_cidr_block(ip, self.blacklist_blocks)
        if matched_blacklist_cidr is not None:
            self.blacklist_ips.add(ip)  # Cache for future lookups
            return False, f"Blacklisted Range ({matched_blacklist_cidr})"

        # 2. Check whitelist (always allow, even when locked)
        if ip in self.whitelist_ips:
            return True, "Whitelisted IP"

        if ip_in_cidr_block_set(ip, self.whitelist_blocks):
            return True, "Whitelisted Range"

        # 3. Always allow LAN and heartbeats
        if self._is_lan_ip(ip):
            return True, "LAN"

        if size in HEARTBEAT_SIZES:
            return True, "Heartbeat"

        # 4. Lock state logic
        if self.locked:
            if size in MATCHMAKING_SIZES:
                return False, "Locked - Unknown Matchmaking Blocked"
            self.known_allowed.add(ip)
            return True, "Locked - Unknown Non-Matchmaking Allowed"

        # 5. Unlocked state: allow everyone else
        self.known_allowed.add(ip)
        return True, "Allowed"


# TODO: Convert this to AbstractPacketFilter
class DebugSession:
    """
    Thread to create a log of the ips matching the packet filter
    """

    def __init__(self, ips: set[str], priority: int):
        self.ips = ips
        self.priority = priority
        self.process = Process(target=self.run, daemon=True)

    def start(self) -> None:
        self.process.start()

    def stop(self) -> None:
        self.process.terminate()
        self.process.join()

    def run(self) -> None:
        debug_logger.debug("Started debugging")
        with pydivert.WinDivert(
            PACKET_FILTER, priority=self.priority, flags=pydivert.Flag.SNIFF
        ) as w:
            for packet in w:
                dst = packet.ip.dst_addr
                src = packet.ip.src_addr
                size = len(packet.payload)
                whitelisted = False
                reserved_allow = False  # Packet from a reserved IP was allowed.
                reserved_block = False  # Packet from a reserved IP was blocked.
                service = False  # Packet allowed because it could be heartbeat / matchmaker but not from a reserved IP.
                if ipfilter.match(dst) or ipfilter.match(src):
                    if size in KNOWN_SIZES:
                        reserved_allow = True
                    else:
                        reserved_block = True  # Came from a "reserved" IP but was blocked under the new rules.
                elif dst in self.ips or src in self.ips:
                    whitelisted = True
                elif size in KNOWN_SIZES:
                    service = True  # Was allowed because it may be service-related, but wasn't from a reserved IP.

                if whitelisted:
                    filler = "Whitelist"
                elif reserved_allow:
                    filler = "Reserved (Allowed)"
                elif reserved_block:
                    filler = "Reserved (Blocked)"
                elif service:
                    filler = "Service (Allowed)"
                else:
                    filler = "Blocked"

                debug_logger.debug(
                    "[%s] %s:%s %s %s:%s",
                    filler,
                    src,
                    packet.src_port,
                    "-->" if packet.is_inbound else "<--",
                    dst,
                    packet.dst_port,
                )
