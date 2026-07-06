import json
from pathlib import Path
from typing import Any, Literal, TypedDict, TypeVar

from util.singleton import Singleton

LIST_TYPE = Literal["blacklist", "whitelist"]
T = TypeVar("T", bound=dict[str, str])


class ConfigDataType(TypedDict, total=False):
    blacklist: dict[str, str]
    whitelist: dict[str, str]
    language: str
    hotkey_vk: int
    hotkey_name: str
    sound_enabled: bool
    sound_lock_freq: int
    sound_lock_dur: int
    sound_unlock_freq: int
    sound_unlock_dur: int


class ConfigData(metaclass=Singleton):
    def __init__(self, data_file: str = "data.json"):
        self.data_file = Path(data_file)
        self.data: ConfigDataType
        if self.data_file.is_file():
            self.load()
            # Migrate older configs
            updated = False
            defaults = {
                "hotkey_vk": 0x78,       # VK_F9
                "hotkey_name": "F9",
                "sound_enabled": True,
                "sound_lock_freq": 900,
                "sound_lock_dur": 200,
                "sound_unlock_freq": 400,
                "sound_unlock_dur": 200,
            }
            for k, v in defaults.items():
                if k not in self.data:
                    self.data[k] = v  # type: ignore[literal-required]
                    updated = True
            if updated:
                self.save()
        else:
            self.data = {
                "blacklist": {},
                "whitelist": {},
                "language": "ru",
                "hotkey_vk": 0x78,       # VK_F9
                "hotkey_name": "F9",
                "sound_enabled": True,
                "sound_lock_freq": 900,
                "sound_lock_dur": 200,
                "sound_unlock_freq": 400,
                "sound_unlock_dur": 200,
            }
            self.save()


    def load(self) -> None:
        with self.data_file.open("r") as file:
            self.data = json.load(file)

    def save(self) -> None:
        with self.data_file.open("w") as file:
            json.dump(self.data, file, indent=4)

    def get(self, key: str, default: Any = None) -> Any:
        """
        Retrieve data from the configuration
        :param key: Key to find in the config data
        :param default: Value to return if key is not present
        :return: Appropiate value or None
        """
        return self.data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """
        Set data to configuration
        :param key: Key to store the data on the config
        :param value: Value to store
        """
        self.data[key] = value  # type: ignore[literal-required]

    def get_language(self) -> str:
        return self.data.get("language", "ru")

    def set_language(self, language: str) -> None:
        self.data["language"] = language
        self.save()
