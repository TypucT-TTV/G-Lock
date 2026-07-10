from __future__ import annotations

import ctypes
import logging
import socket
import struct
from ctypes import wintypes
from typing import Optional

logger = logging.getLogger(__name__)

# Win32 Constants
TH32CS_SNAPPROCESS = 0x00000002
INVALID_HANDLE_VALUE = -1
AF_INET = 2  # IPv4
UDP_TABLE_OWNER_PID = 1  # class to get owner PID


class PROCESSENTRY32W(ctypes.Structure):
    _fields_ = [
        ("dwSize", wintypes.DWORD),
        ("cntUsage", wintypes.DWORD),
        ("th32ProcessID", wintypes.DWORD),
        ("th32DefaultHeapID", ctypes.c_size_t),
        ("th32ModuleID", wintypes.DWORD),
        ("cntThreads", wintypes.DWORD),
        ("th32ParentProcessID", wintypes.DWORD),
        ("pcPriClassBase", wintypes.LONG),
        ("dwFlags", wintypes.DWORD),
        ("szExeFile", wintypes.WCHAR * 260),
    ]


def get_pid_by_name(process_name: str) -> Optional[int]:
    """
    Finds the Process ID of the first process matching the given name using Toolhelp32.
    """
    try:
        kernel32 = ctypes.windll.kernel32

        # Configure ctypes arguments and return types for 64-bit safety
        kernel32.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
        kernel32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE

        kernel32.Process32FirstW.argtypes = [
            wintypes.HANDLE,
            ctypes.POINTER(PROCESSENTRY32W),
        ]
        kernel32.Process32FirstW.restype = wintypes.BOOL

        kernel32.Process32NextW.argtypes = [
            wintypes.HANDLE,
            ctypes.POINTER(PROCESSENTRY32W),
        ]
        kernel32.Process32NextW.restype = wintypes.BOOL

        kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel32.CloseHandle.restype = wintypes.BOOL

        h_snapshot = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
        if h_snapshot == INVALID_HANDLE_VALUE or h_snapshot is None:
            return None

        pe32 = PROCESSENTRY32W()
        pe32.dwSize = ctypes.sizeof(PROCESSENTRY32W)

        if not kernel32.Process32FirstW(h_snapshot, ctypes.byref(pe32)):
            kernel32.CloseHandle(h_snapshot)
            return None

        pid: Optional[int] = None
        while True:
            # WCHAR array is automatically converted to python string
            if pe32.szExeFile.lower() == process_name.lower():
                pid = pe32.th32ProcessID
                break
            if not kernel32.Process32NextW(h_snapshot, ctypes.byref(pe32)):
                break

        kernel32.CloseHandle(h_snapshot)
        return pid
    except Exception as e:
        logger.warning("Error looking up process PID for %s: %s", process_name, e)
        return None


def get_udp_ports_for_pid(pid: int) -> list[int]:
    """
    Queries the extended UDP table to find all local ports bound by the specified PID.
    """
    try:
        iphlpapi = ctypes.windll.iphlpapi

        # Configure ctypes arguments and return types for 64-bit safety
        iphlpapi.GetExtendedUdpTable.argtypes = [
            ctypes.c_void_p,
            ctypes.POINTER(wintypes.DWORD),
            wintypes.BOOL,
            wintypes.ULONG,
            ctypes.c_int,
            wintypes.ULONG,
        ]
        iphlpapi.GetExtendedUdpTable.restype = wintypes.DWORD

        dwSize = wintypes.DWORD(0)

        # First call to get the required buffer size
        iphlpapi.GetExtendedUdpTable(
            None, ctypes.byref(dwSize), False, AF_INET, UDP_TABLE_OWNER_PID, 0
        )
        if dwSize.value == 0:
            return []

        # Allocate buffer
        buffer = ctypes.create_string_buffer(dwSize.value)

        # Second call to populate the buffer
        result = iphlpapi.GetExtendedUdpTable(
            buffer, ctypes.byref(dwSize), False, AF_INET, UDP_TABLE_OWNER_PID, 0
        )
        if result != 0:
            logger.warning("GetExtendedUdpTable failed with error code %d", result)
            return []

        # The layout of MIB_UDPTABLE_OWNER_PID in memory:
        # DWORD dwNumEntries (4 bytes)
        # Followed by dwNumEntries rows of MIB_UDPROW_OWNER_PID.
        # Each row is 12 bytes: dwLocalAddr (4), dwLocalPort (4), dwOwningPid (4)
        num_entries = struct.unpack_from("I", buffer.raw, 0)[0]
        ports: list[int] = []

        offset = 4
        for _ in range(num_entries):
            addr, port_raw, row_pid = struct.unpack_from("III", buffer.raw, offset)
            if row_pid == pid:
                # dwLocalPort returned is in network byte order in the lower 16 bits of the DWORD.
                # Use socket.ntohs to convert to host byte order.
                port = socket.ntohs(port_raw & 0xFFFF)
                if port > 0:
                    ports.append(port)
            offset += 12

        return ports
    except Exception as e:
        logger.warning("Error getting UDP table for PID %d: %s", pid, e)
        return []


def get_gta_udp_port(default_port: int = 6672) -> int:
    """
    Finds the UDP port used by GTA5.exe. If not found or if multiple are used,
    returns the first one or falls back to the default port.
    """
    pid = get_pid_by_name("GTA5.exe")
    if pid is not None:
        ports = get_udp_ports_for_pid(pid)
        if ports:
            logger.info(
                "Detected GTA5.exe running with PID %d on UDP port %d", pid, ports[0]
            )
            return ports[0]
        else:
            logger.warning(
                "GTA5.exe process found (PID %d), but no active UDP ports detected", pid
            )
    else:
        logger.debug("GTA5.exe is not running")

    return default_port
