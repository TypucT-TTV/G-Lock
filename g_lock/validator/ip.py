import contextlib
import re
import socket
from typing import Callable

from prompt_toolkit.document import Document
from questionary import ValidationError, Validator

from config.globallist import Blacklist, GlobalList, Whitelist

ipv4 = re.compile(r"((25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)(\.|$)){4}")


def validate_cidr(text: str) -> bool:
    if "/" not in text:
        return False
    parts = text.split("/")
    if len(parts) != 2:
        return False
    ip, suffix_str = parts
    if not ipv4.match(ip):
        return False
    try:
        socket.inet_aton(ip)
    except socket.error:
        return False
    try:
        suffix = int(suffix_str)
        if not (0 <= suffix <= 32):
            return False
    except ValueError:
        return False
    return True


class IPValidator(Validator):
    def __init__(self, global_list: Callable[[], GlobalList]):
        self.list = global_list()

    def validate(self, document: Document) -> None:
        error = ValidationError(
            message="Invalid IP or CIDR", cursor_position=len(document.text)
        )
        ip = document.text
        if "/" in ip:
            if not validate_cidr(ip):
                raise error
        else:
            if not ipv4.match(ip):
                raise error
            try:
                socket.inet_aton(ip)
            except socket.error:
                raise error
        if ip in self.list:
            raise ValidationError(message="IP already in list", cursor_position=len(ip))

    # TODO: Add an extra validator to check if an IP could be used by R* services (i.e. it's part of Microsoft Azure)

    @staticmethod
    def validate_get(text: str) -> str:
        error = ValidationError(message="Invalid IP or CIDR", cursor_position=len(text))
        if "/" in text:
            if validate_cidr(text):
                return text
        else:
            with contextlib.suppress(socket.error):
                if ipv4.match(text):
                    socket.inet_aton(text)
                    return text
        raise error


class IPInBlacklist(IPValidator):
    def __init__(self) -> None:
        super().__init__(Blacklist)


class IPInWhitelist(IPValidator):
    def __init__(self) -> None:
        super().__init__(Whitelist)
