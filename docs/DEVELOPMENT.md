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
src-tauri/src/firewall.rs     WinDivert, режимы, relay-классификация и IPS
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
8. В открытом Whitelist relay/matchmaking проходит без кэширования, прямой трафик разрешён только whitelist.
   Закрытый Whitelist сохраняет известных peer и блокирует всех новых, включая новые whitelist IP.

## Конфигурация и безопасность

- `data.json` хранится рядом с executable и заменяется атомарно через `MoveFileExW`.
- IPC принимает только известные режимы, типы списков и корректные IPv4/CIDR.
- Whitelist и blacklist взаимоисключающие; новое правило удаляет адрес из второго списка.
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
