"""
Minimal translation layer: a flat key -> text dict per language, a currently
selected language (persisted via ConfigData, same file whitelist/blacklist
already live in), and a t(key, **kwargs) lookup with .format() support for
the handful of strings that need a dynamic value inserted.
"""

from __future__ import annotations

from config.configdata import ConfigData

LANG_RU = "ru"
LANG_EN = "en"

_TRANSLATIONS: dict[str, dict[str, str]] = {
    LANG_EN: {
        "menu_solo_session": "Solo Session",
        "menu_whitelisted_session": "Whitelisted Session",
        "menu_blacklisted_session": "Blacklisted Session",
        "menu_auto_whitelisted_session": "Auto Whitelisted Session",
        "menu_locked_session": "Locked Session",
        "menu_kick_unknowns": "Kick unknowns",
        "menu_empty_session": "Empty Session (force Session Host)",
        "menu_kick_by_ip": "Kick by IP",
        "menu_edit_lists": "Edit lists",
        "menu_edit_settings": "Settings",
        "menu_donate": "Thank ТурисТ",
        "menu_quit": "Quit",
        "btn_stop_session": "Stop Session",
        "btn_lock_session": "Lock Session",
        "btn_unlock_session": "Unlock Session",
        "settings_title": "G-Lock Settings",
        "settings_hotkey_sec": "Global Hotkey",
        "settings_sound_sec": "Sound Notifications (Beep)",
        "settings_current_key": "Current key: {hotkey}",
        "settings_btn_change_key": "Change...",
        "settings_press_key": "Press any key...",
        "settings_sound_enabled": "Enable beep sounds",
        "settings_sound_lock": "On Session Lock",
        "settings_sound_unlock": "On Session Unlock",
        "settings_freq": "Frequency: {value} Hz",
        "settings_dur": "Duration: {value} ms",
        "settings_vol": "Volume: {value}%",
        "settings_btn_test": "Test",
        "status_open": "Open",
        "status_open_blacklist": "Open (Blacklist Active)",
        "status_locked": "LOCKED",
        "status_active": "Active: {name}",
        "name_solo_session": "Solo Session",
        "name_whitelisted_session": "Whitelisted Session",
        "name_blacklisted_session": "Blacklisted Session",
        "name_locked_session": "Locked Session",
        "name_auto_whitelisted_session": "Auto-Whitelisted Session",
        "name_kick_unknowns": "Kick Unknowns",
        "name_empty_session": "Empty Session",
        "name_kick_by_ip": "Kick by IP",
        "confirm_title": "Session type: {name}, are you sure?",
        "explain_solo_session": (
            "No one can connect to your game session, but critical R* and SocialClub activity "
            "will still go through.\nIf you are in a session with any other players, they will "
            "lose connection to you."
        ),
        "explain_whitelisted_session": (
            "Only IP addresses in your Whitelist will be allowed to connect to you.\nIf you are "
            "the host of a session, anyone not in your Whitelist will likely lose connection to "
            "the session.\nIf you are not the host (and any player in the session is not in your "
            "Whitelist), you will lose connection to everyone else."
        ),
        "explain_blacklisted_session": (
            "IP addresses in your Blacklist will not be allowed to connect to you.\nIf a "
            "connection is routed through R* servers, that connection will also be blocked as a "
            "security measure.\nThis mode is NOT RECOMMENDED as GTA Online has custom routing if "
            "only a handful of IP addresses are blocked."
        ),
        "explain_locked_session": (
            "This mode blocks all join requests, preventing new players from entering the "
            "session.\nAnyone already in the session will not be kicked out. This mode prevents "
            "people from entering the session through R* servers if someone is being tunnelled "
            "through a R* IP.\nHowever, if a player leaves the session, they will not be able to "
            "join again."
        ),
        "explain_auto_whitelisted_session": (
            "Similar to Whitelisted session, except everybody currently in the session is "
            "temporarily added to your whitelist, which prevents them from being kicked.\nAny "
            "automatically collected IPs will be lost once the session ends.\nIf G-Lock detects "
            "that a player in your session is being routed through R* servers, you will be warned "
            "and prompted whether you wish to add this IP to the temporary whitelist.\nIf you do "
            "decide to allow these IPs, your session may not properly protected."
        ),
        "explain_kick_unknowns": (
            "Attempts to kick any IP that is not on your Whitelist out of the session.\nKeeping "
            "your sessions safe in this manner is NOT RECOMMENDED, as clients may try to route "
            "unknown player traffic through IPs that are on your Whitelist."
        ),
        "explain_empty_session": (
            "Splits you from the current session so you are alone. Being the only player in a "
            "session ensures that you are the session Host."
        ),
        "explain_kick_by_ip": (
            "Captures IPs in your session, then allows you to choose which IPs to kick.\nThis "
            "mode is NOT RECOMMENDED for the same reason that kicking unknowns may not work."
        ),
        "btn_yes_start": "Yes, start",
        "btn_no_back": "No, go back",
        "btn_ok": "OK",
        "btn_cancel": "Cancel",
        "tunnels_title": "Potential tunnel IPs detected",
        "tunnels_warning": (
            "WARNING! G-Lock has detected {count} IP(s) in your current session that may be "
            "used for connection tunnelling, and may break session security if added to the "
            "whitelist.\nUnless you know what you're doing, it is HIGHLY RECOMMENDED that you DO "
            "NOT allow these IPs to be added to the whitelist.\nPlease note that excluding an IP "
            "from this list will likely result in players connected through that IP to be dropped "
            "from the session.\nIf this happens, then you may have to check both you and your "
            "friend's Windows Firewall settings to see why they can't directly connect to you.\nIf "
            "this is a false-positive and you are sure an IP is a direct connection, you can "
            "prevent this message from appearing by manually adding them to your Whitelist.\n\n"
            "Select the potentially session-security-breaking IPs you wish to keep whitelisted, "
            "if any."
        ),
        "kick_by_ip_message": "Select IPs to kick",
        "list_editor_title": "Edit lists",
        "tab_whitelist": "Whitelist",
        "tab_blacklist": "Blacklist",
        "col_name": "Name",
        "col_ip": "IP address",
        "btn_add": "Add",
        "btn_edit": "Edit",
        "btn_delete": "Delete",
        "btn_save": "Save",
        "form_title_add": "Add entry",
        "form_title_edit": "Edit entry",
        "error_name_duplicate": "Name already in list",
        "error_ip_invalid": "Invalid IP",
        "error_ip_duplicate": "IP already in list",
        "log_panel_title": "Network Activity",
        "col_time": "Time",
        "col_action": "Action",
        "col_detail": "Details",
        "log_menu_copy_ip": "Copy IP",
        "log_menu_add_whitelist": "Add to Whitelist",
        "log_menu_add_blacklist": "Add to Blacklist",
        "dialog_enter_name_title": "Enter name",
        "dialog_enter_name_msg": "Enter name for IP {ip}:",
    },
    LANG_RU: {
        "menu_solo_session": "Solo-сессия",
        "menu_whitelisted_session": "Сессия по вайтлисту",
        "menu_blacklisted_session": "Сессия по блэклисту",
        "menu_auto_whitelisted_session": "Авто-вайтлист сессии",
        "menu_locked_session": "Закрытая сессия (Lock)",
        "menu_kick_unknowns": "Кикнуть неизвестных",
        "menu_empty_session": "Пустая сессия (стать хостом)",
        "menu_kick_by_ip": "Кикнуть по IP",
        "menu_edit_lists": "Списки (вайт/блэклист)",
        "menu_edit_settings": "Настройки",
        "menu_donate": "Поблагодарить ТурисТа",
        "menu_quit": "Выход",
        "btn_stop_session": "Остановить сессию",
        "btn_lock_session": "Запереть сессию",
        "btn_unlock_session": "Открыть сессию",
        "settings_title": "Настройки G-Lock",
        "settings_hotkey_sec": "Горячая клавиша",
        "settings_sound_sec": "Звуковые сигналы (Beep)",
        "settings_current_key": "Текущая клавиша: {hotkey}",
        "settings_btn_change_key": "Изменить...",
        "settings_press_key": "Нажмите любую клавишу...",
        "settings_sound_enabled": "Включить звуковые сигналы",
        "settings_sound_lock": "При блокировке (Locked)",
        "settings_sound_unlock": "При разблокировке (Unlocked)",
        "settings_freq": "Частота: {value} Гц",
        "settings_dur": "Длительность: {value} мс",
        "settings_vol": "Громкость: {value}%",
        "settings_btn_test": "Тест",
        "status_open": "Открыто",
        "status_open_blacklist": "Открыто (ЧС активен)",
        "status_locked": "ЗАПЕРТО",
        "status_active": "Активно: {name}",
        "name_solo_session": "Solo-сессия",
        "name_whitelisted_session": "Сессия по вайтлисту",
        "name_blacklisted_session": "Сессия по блэклисту",
        "name_locked_session": "Закрытая сессия",
        "name_auto_whitelisted_session": "Авто-вайтлист сессии",
        "name_kick_unknowns": "Кик неизвестных",
        "name_empty_session": "Пустая сессия",
        "name_kick_by_ip": "Кик по IP",
        "confirm_title": "Тип сессии: {name}, вы уверены?",
        "explain_solo_session": (
            "Никто не сможет подключиться к вашей игровой сессии, но важный трафик R* и Social "
            "Club продолжит проходить.\nЕсли вы сейчас в сессии с другими игроками, они потеряют "
            "соединение с вами."
        ),
        "explain_whitelisted_session": (
            "Подключаться к вам смогут только IP-адреса из вашего вайтлиста.\nЕсли вы хост "
            "сессии, все, кого нет в вайтлисте, скорее всего потеряют соединение с сессией.\nЕсли "
            "вы не хост (и в сессии есть игрок не из вашего вайтлиста), вы потеряете соединение "
            "со всеми остальными."
        ),
        "explain_blacklisted_session": (
            "IP-адреса из вашего блэклиста не смогут подключиться к вам.\nЕсли соединение идёт "
            "через серверы R*, оно тоже будет заблокировано в целях безопасности.\nЭтот режим НЕ "
            "РЕКОМЕНДУЕТСЯ, так как у GTA Online есть особая маршрутизация на случай блокировки "
            "лишь нескольких IP-адресов."
        ),
        "explain_locked_session": (
            "Этот режим блокирует все запросы на вход, не давая новым игрокам зайти в сессию.\n"
            "Тех, кто уже в сессии, никто не кикнет. Этот режим также не даёт войти через серверы "
            "R*, если кого-то туннелируют через IP от R*.\nОднако если игрок выйдет из сессии, "
            "зайти обратно он уже не сможет."
        ),
        "explain_auto_whitelisted_session": (
            "Похоже на сессию по вайтлисту, но все, кто сейчас в сессии, временно добавляются в "
            "вайтлист, чтобы их не выкинуло.\nАвтоматически собранные IP пропадут после "
            "завершения сессии.\nЕсли G-Lock обнаружит, что кто-то из сессии идёт через серверы "
            "R*, вас предупредят и спросят, хотите ли вы временно добавить этот IP в вайтлист.\n"
            "Если вы разрешите эти IP, защита сессии может быть неполной."
        ),
        "explain_kick_unknowns": (
            "Пытается выкинуть из сессии все IP, которых нет в вашем вайтлисте.\nЗащищать сессию "
            "таким способом НЕ РЕКОМЕНДУЕТСЯ, так как трафик неизвестных игроков может "
            "маршрутизироваться через IP, которые есть в вашем вайтлисте."
        ),
        "explain_empty_session": (
            "Отделяет вас от текущей сессии, чтобы вы остались одни. Если вы единственный игрок "
            "в сессии — вы гарантированно её хост."
        ),
        "explain_kick_by_ip": (
            "Собирает IP-адреса в вашей сессии, затем даёт выбрать, кого из них выкинуть.\nЭтот "
            "режим НЕ РЕКОМЕНДУЕТСЯ по той же причине, по которой может не сработать кик "
            "неизвестных."
        ),
        "btn_yes_start": "Да, запустить",
        "btn_no_back": "Нет, назад",
        "btn_ok": "ОК",
        "btn_cancel": "Отмена",
        "tunnels_title": "Обнаружены потенциальные IP-туннели",
        "tunnels_warning": (
            "ВНИМАНИЕ! G-Lock обнаружил в вашей текущей сессии IP-адреса ({count} шт.), которые "
            "могут использоваться для туннелирования соединения и могут нарушить безопасность "
            "сессии при добавлении в вайтлист.\nЕсли вы не уверены, что делаете, НАСТОЯТЕЛЬНО "
            "РЕКОМЕНДУЕТСЯ НЕ разрешать добавление этих IP в вайтлист.\nОбратите внимание: "
            "исключение IP из этого списка, скорее всего, приведёт к тому, что игроки, "
            "подключённые через этот IP, будут выброшены из сессии.\nЕсли так произошло, "
            "проверьте настройки брандмауэра Windows у себя и у друга — возможно, поэтому вы не "
            "можете подключиться напрямую.\nЕсли это ложное срабатывание и вы уверены, что IP — "
            "это прямое подключение, вы можете добавить его вручную в вайтлист, чтобы это "
            "сообщение больше не появлялось.\n\nВыберите потенциально небезопасные IP, которые вы "
            "всё же хотите оставить в вайтлисте, если такие есть."
        ),
        "kick_by_ip_message": "Выберите IP для кика",
        "list_editor_title": "Списки",
        "tab_whitelist": "Вайтлист",
        "tab_blacklist": "Блэклист",
        "col_name": "Имя",
        "col_ip": "IP-адрес",
        "btn_add": "Добавить",
        "btn_edit": "Изменить",
        "btn_delete": "Удалить",
        "btn_save": "Сохранить",
        "form_title_add": "Добавить запись",
        "form_title_edit": "Изменить запись",
        "error_name_duplicate": "Такое имя уже есть в списке",
        "error_ip_invalid": "Неверный IP-адрес",
        "error_ip_duplicate": "Такой IP уже есть в списке",
        "log_panel_title": "Сетевая активность",
        "col_time": "Время",
        "col_action": "Действие",
        "col_detail": "Причина",
        "log_menu_copy_ip": "Копировать IP",
        "log_menu_add_whitelist": "В белый список (Whitelist)",
        "log_menu_add_blacklist": "В черный список (Blacklist)",
        "dialog_enter_name_title": "Добавить имя",
        "dialog_enter_name_msg": "Введите имя для IP {ip}:",
    },
}

# Maps AbstractPacketFilter subclass names to the same friendly-name keys
# used for menu labels, so the "Active: ..." status text is localized too
# instead of showing a raw Python class name.
FILTER_CLASS_NAME_KEY = {
    "SoloSession": "name_solo_session",
    "PrivateSession": "status_open",
}

_current_language = LANG_RU


def load_saved_language() -> None:
    global _current_language
    saved = ConfigData().get_language()
    _current_language = saved if saved in _TRANSLATIONS else LANG_RU


def get_language() -> str:
    return _current_language


def set_language(language: str) -> None:
    global _current_language
    if language not in _TRANSLATIONS:
        return
    _current_language = language
    ConfigData().set_language(language)


def t(key: str, **kwargs: object) -> str:
    text = _TRANSLATIONS.get(_current_language, {}).get(key)
    if text is None:
        text = _TRANSLATIONS[LANG_EN].get(key, key)
    return text.format(**kwargs) if kwargs else text
