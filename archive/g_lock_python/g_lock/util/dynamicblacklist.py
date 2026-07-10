from __future__ import annotations

import json
import logging
import re
import time
from pathlib import Path

import requests

from util.network import construct_cidr_block_set
from util.types import CIDR_BLOCK

# This file contains classes and methods to manage acquiring, parsing, and
# updating a possibly dynamic list of IP ranges that G-Lock needs to be
# aware of.  Such ranges include R* / T2 official IPs, as well as IPs that
# can be used for miscellaneous R* Services, such as Microsoft Azure.

logger = logging.getLogger(__name__)


class ScrapeError(Exception):
    """Could not scrape the HTML for data for some reason."""


# Without an explicit timeout, requests will wait indefinitely for a slow or
# unresponsive server.  Since Menu's class body calls get_dynamic_blacklist()
# at import time (before any window can even appear, GUI or console), a hung
# connection here would freeze startup with no visible feedback at all.
REQUEST_TIMEOUT_SECONDS = 10

# How many times to retry a failed HTTP request before giving up.
MAX_RETRIES = 2

# Base delay between retries (exponential backoff: delay * 2^attempt).
RETRY_BASE_DELAY_SECONDS = 1.0

# User-Agent sent with every outgoing request so servers don't reject us
# as an anonymous script.
_USER_AGENT = "G-Lock/1.0 (GTA5-Firewall; +https://github.com)"

# RIPE Stat REST API endpoint.  Returns announced prefixes for a given ASN
# as JSON (no authentication required).
_RIPE_STAT_URL = "https://stat.ripe.net/data/announced-prefixes/data.json"

# Static fallback prefixes used when RIPE Stat is unreachable.
_T2_EU_STATIC: set[str] = {
    "185.56.64.0/24",
    "185.56.64.0/22",
    "185.56.65.0/24",
    "185.56.66.0/24",
    "185.56.67.0/24",
}

_T2_US_STATIC: set[str] = {
    "104.255.104.0/24",
    "104.255.104.0/22",
    "104.255.105.0/24",
    "104.255.106.0/24",
    "104.255.107.0/24",
    "192.81.240.0/24",
    "192.81.240.0/22",
    "192.81.241.0/24",
    "192.81.242.0/24",
    "192.81.243.0/24",
    "192.81.244.0/24",
    "192.81.244.0/22",
    "192.81.245.0/24",
    "192.81.246.0/24",
    "192.81.247.0/24",
    "198.133.210.0/24",
}


def _request_with_retries(
    url: str,
    *,
    params: dict[str, str] | None = None,
    max_retries: int = MAX_RETRIES,
) -> requests.Response:
    """HTTP GET with exponential-backoff retries and proper headers."""
    last_exc: Exception | None = None
    for attempt in range(1 + max_retries):
        try:
            resp = requests.get(
                url,
                params=params,
                headers={"User-Agent": _USER_AGENT},
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
            resp.raise_for_status()
            return resp
        except requests.RequestException as exc:
            last_exc = exc
            if attempt < max_retries:
                delay = RETRY_BASE_DELAY_SECONDS * (2**attempt)
                logger.warning(
                    "Request to %s failed (attempt %d/%d): %s — " "retrying in %.1fs",
                    url,
                    attempt + 1,
                    1 + max_retries,
                    exc,
                    delay,
                )
                time.sleep(delay)
    # All attempts exhausted — re-raise the last exception.
    assert last_exc is not None
    raise last_exc


# ---------------------------------------------------------------------------
# R* / Take-Two prefix fetching via RIPE Stat REST (replaces prsw)
# ---------------------------------------------------------------------------


def _fetch_ripe_prefixes(asn: int) -> set[str]:
    """Fetch announced prefixes for *asn* from the RIPE Stat REST API.

    Returns a set of CIDR strings (e.g. ``{"185.56.64.0/22", …}``).
    Raises on network / parse errors — the caller is expected to catch
    and fall back to the static list.
    """
    resp = _request_with_retries(_RIPE_STAT_URL, params={"resource": f"AS{asn}"})
    data = resp.json()
    prefixes_raw = data["data"]["prefixes"]
    return {entry["prefix"] for entry in prefixes_raw}


def _get_t2_prefixes() -> tuple[set[str], set[str]]:
    """Return (T2_EU, T2_US) prefix sets.

    Tries RIPE Stat first; on any failure falls back to the hardcoded
    static lists and logs a warning.
    """
    try:
        t2_eu = _fetch_ripe_prefixes(202021)
    except Exception:
        logger.warning(
            "RIPE Stat lookup for AS202021 failed — using static "
            "fallback (%d prefixes)",
            len(_T2_EU_STATIC),
            exc_info=True,
        )
        t2_eu = _T2_EU_STATIC

    try:
        t2_us = _fetch_ripe_prefixes(46555)
    except Exception:
        logger.warning(
            "RIPE Stat lookup for AS46555 failed — using static "
            "fallback (%d prefixes)",
            len(_T2_US_STATIC),
            exc_info=True,
        )
        t2_us = _T2_US_STATIC

    return t2_eu, t2_us


T2_EU, T2_US = _get_t2_prefixes()


# ---------------------------------------------------------------------------
# Azure IP ranges
# ---------------------------------------------------------------------------

# This URL should return information about the most up-to-date JSON file
# containing Azure IP ranges.  Microsoft claims that a new file is
# published every 7 days, and that any new IPs will not be used for
# another 7 days.
AZURE_GET_PUBLIC_CLOUD_URL = (
    "https://www.microsoft.com/en-us/download/confirmation.aspx?id=56519"
)
# The regex pattern to find download files on the page.
MICROSOFT_DOWNLOAD_REGEX = re.compile(
    r"https://download\.microsoft\.com/download[^\"]*\.json"
)


def determine_best_azure_file(urls: list[str]) -> tuple[str, bytes]:
    """Given multiple azure URLs, identify the best JSON file to return
    based on the largest changeNumber.

    Returns the URL, and the contents of the JSON file as bytes.
    """
    highest_change_number = 0
    best_response = b""
    best_url = ""
    for url in urls:
        response = _request_with_retries(url)
        content = response.content
        change_number = json.loads(content)["changeNumber"]
        if change_number > highest_change_number:
            highest_change_number = change_number
            best_response = content
            best_url = url
    return best_url, best_response


def get_azure_ip_ranges_download(
    page_to_search: str = AZURE_GET_PUBLIC_CLOUD_URL,
) -> tuple[str, bytes]:
    """Finds the URL to the most recent Azure JSON file.

    There is no official API, so we scrape the human-readable download
    page.  If multiple possibly-valid files are found, only the file
    with the highest ``changeNumber`` is returned.
    """
    response = _request_with_retries(page_to_search)
    if response.status_code != 200:
        raise ScrapeError(
            f"URL to scrape returned {response.status_code} instead " f"of 200.",
            response,
        )

    # Search through the HTML for all download.microsoft.com JSON files.
    re_files = re.findall(MICROSOFT_DOWNLOAD_REGEX, str(response.content))
    if not re_files:
        raise ScrapeError(
            "Did not find any valid download URLs while searching " "the page.",
            response,
        )

    files = list(set(re_files))
    return determine_best_azure_file(files)


def azure_file_add_timestamp(azure_file_contents: bytes, filename: str) -> bytes:
    as_list = azure_file_contents.splitlines(True)
    # add timestamp and filename
    as_list.insert(1, f'  "acquiredFrom": "{filename}",\n'.encode())
    as_list.insert(1, f'  "acquiredWhen": "{time.time()}",\n'.encode())
    return b"".join(as_list)


def parse_azure_ip_ranges(azure_file_contents: bytes) -> list[str]:
    azure_cloud_json = json.loads(azure_file_contents)
    categories = azure_cloud_json["values"]
    arr_ranges = next(
        (
            cat["properties"]["addressPrefixes"]
            for cat in categories
            if cat["name"] == "AzureCloud"
        ),
        None,
    )
    if arr_ranges is None:
        raise ValueError("Could not find AzureCloud category in values array.")
    return arr_ranges  # type: ignore[no-any-return]


def get_resource_path(relative_path: str) -> Path:
    """Get absolute path to resource, works for dev and for PyInstaller."""
    import sys

    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        meipass_path = Path(sys._MEIPASS) / relative_path
        if meipass_path.is_file():
            return meipass_path
    return Path(relative_path)


def get_dynamic_blacklist(
    backup_file: str = "db.json",
) -> set[CIDR_BLOCK]:
    read_path = get_resource_path(backup_file)
    write_path = Path(backup_file)
    try:
        download_link, content = get_azure_ip_ranges_download()
        ranges = parse_azure_ip_ranges(content)
        write_path.write_bytes(azure_file_add_timestamp(content, download_link))
        ranges.extend(T2_EU)  # add R* EU ranges
        ranges.extend(T2_US)  # add R* US ranges
    except Exception as e:
        logger.warning("Could not fetch Azure ranges from URL: %s", e)
        if not read_path.is_file() and not write_path.is_file():
            raise FileNotFoundError(
                f"ERROR: Could not find backup file {backup_file}."
            ) from e
        path_to_read = read_path if read_path.is_file() else write_path
        ranges = parse_azure_ip_ranges(path_to_read.read_bytes())
    return construct_cidr_block_set(ranges)
