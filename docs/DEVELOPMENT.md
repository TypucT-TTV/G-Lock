# Руководство разработчика G-Lock v2

## Стек

- Tauri v2 и Rust 2021 — elevated Windows-бэкенд.
- Svelte 5, TypeScript, Vite и статический SPA-адаптер — интерфейс.
- `windivert 0.6.0` / `windivert-sys 0.10.0` и WinDivert 2.2.2-A — фильтрация IPv4 UDP.
- Tauri IPC (`invoke`) и события (`emit`) — обмен между Rust и Svelte.

Звуки воспроизводятся Web Audio API внутри WebView. Отдельного `sound.rs` и
зависимости `rodio` в проекте нет.

## Подготовка окружения

Требуются Windows 10/11 x64, Node.js LTS, npm, Rust stable MSVC и WebView2.

```powershell
npm ci
npm run tauri dev
```

Запуск Tauri требует терминала с правами администратора. Статические проверки и
модульные тесты администратора не требуют.

Сборка установщиков:

```powershell
npm run tauri build
```

## Структура

```text
src/routes/+page.svelte       Svelte UI, локализация и Tauri IPC
src-tauri/src/main.rs         проверка elevation и точка входа
src-tauri/src/lib.rs          команды IPC, hotkeys и настройка Tauri
src-tauri/src/firewall.rs     WinDivert, Open/Lock, relay-классификация и IPS
src-tauri/src/config.rs       конфигурация, валидация и атомарное сохранение
src-tauri/db.json             встроенные диапазоны Azure
```

## Инварианты сетевой логики

1. Постоянный blacklist имеет абсолютный приоритет, включая heartbeat-пакеты и кэш известных участников.
2. Heartbeat payload размером 12, 18 или 63 байта пропускается для адресов вне blacklist.
3. При переходе Open → Lock сохраняется кэш уже замеченных peer IP. Неизвестные
   non-service пакеты в Lock блокируются.
4. Relay-диапазоны исключены из IPS-банов. Встроенная база загружается синхронно,
   RIPE refresh выполняется в фоне.
5. Таблицы `rates`, временных банов, известных peer и log cooldown ограничены 4096
   адресами и очищаются по TTL.
6. Capture worker запускается один раз на UDP 6672. При Windows error 1058 приложение
   один раз восстанавливает для службы WinDivert режим `demand` и путь к комплектному
   драйверу через `sc.exe config`, но не останавливает и не удаляет службу.
7. Capture проверяет оба направления. Peer IP — source для inbound и destination для outbound.
8. Поддерживаются только состояния Open и Lock. Solo/Whitelist не входят в публичный
   контракт: момент раскрытия direct peer IP не позволяет гарантировать их поведение.

## Конфигурация и безопасность

- Пользовательский `data.json` хранится в `%LOCALAPPDATA%\G-Lock` и заменяется
  атомарно через `MoveFileExW`. При первом запуске автоматически импортируется
  прежний файл рядом с executable, поэтому обновление установщика не сбрасывает настройки.
- Проверка обновлений выполняется Rust-бэкендом через GitHub Releases API с таймаутом;
  UI не расширяет `connect-src` CSP и при отсутствии сети продолжает работать.
- Основной global hotkey захватывается из `KeyboardEvent.code`: поддерживаются
  одиночные F1–F24 и сочетания с Ctrl/Alt (и необязательным Shift) с буквами, цифрами, Num- и
  навигационными клавишами. Бэкенд сохраняет VK и битовые модификаторы, добавляет
  `MOD_NOREPEAT` и перерегистрирует сочетание в hotkey thread после `save_settings`.
  Ctrl+F9 зарезервирован для принудительного перехода в Open; он не отключает
  фильтр и не очищает постоянный blacklist.
- Скроллбары основных прокручиваемых областей остаются видимыми для навигации,
  но оформляются тонким тёмным WebKit/Firefox-совместимым стилем.
- IPC принимает только Open/Lock, тип `blacklist` и корректные IPv4/CIDR.
- Ручной blacklist доступен в расширенных настройках и применяется только к уже
  раскрытому сетевому адресу, а не к идентификатору игрока.
- Каталог приложения не добавляется в исключения Windows Defender автоматически.
- CSP задаётся в `src-tauri/tauri.conf.json`; не отключайте её без отдельного анализа.

## Версия и проверки

Версию синхронизируйте в `package.json`, `package-lock.json`, `src-tauri/Cargo.toml`,
`src-tauri/tauri.conf.json` и видимой подписи UI.

```powershell
npm run check
cargo fmt --all --manifest-path src-tauri/Cargo.toml -- --check
cargo clippy --manifest-path src-tauri/Cargo.toml --all-targets -- -D warnings
cargo test --manifest-path src-tauri/Cargo.toml
```

## Происхождение и лицензия

При разработке использован Guardian 3.5.0 от TheMythologist, изначально созданный
Speyedr. Guardian и производная работа распространяются по GNU LGPL v3. Тексты
LGPL и GPL v3 находятся в `LICENSE` и `GPL-3.0.txt`, ссылки на Guardian,
WinDivert и Rust-обёртку — в `SOURCE`, а сведения о сторонних компонентах —
в `THIRD_PARTY_NOTICES.md`. Эти лицензионные файлы включаются в Tauri bundle
как ресурсы.
