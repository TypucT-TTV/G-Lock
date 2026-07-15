# Тестирование G-Lock v2

## Полный набор проверок

Из корня репозитория:

```powershell
npm ci
npm run check
cargo fmt --all --manifest-path src-tauri/Cargo.toml -- --check
cargo clippy --manifest-path src-tauri/Cargo.toml --all-targets -- -D warnings
cargo test --manifest-path src-tauri/Cargo.toml
```

Бинарная цель Tauri помечена `test = false`, потому что встроенный manifest
`requireAdministrator` не позволяет Windows test harness запускать её без UAC.
Модульные тесты библиотеки при этом запускаются без прав администратора.

## Что покрыто

- миграция неполного `data.json` через `#[serde(default)]` и валидация настроек;
- загрузка Azure ranges и lookup relay IP;
- диапазон `/0` в двухуровневой relay-таблице;
- IPv4/UDP parser с переменным IHL;
- heartbeat разрешён для адресов вне blacklist;
- абсолютный приоритет blacklist над heartbeat и кэшем разрешённых адресов;
- разрешение известных и блокировка неизвестных peer в Lock.
- handshake без кэширования и допуск только whitelist peer в открытом Whitelist;
- блокировка новых whitelist peer в закрытом Whitelist;
- выбор peer IP по source для inbound и destination для outbound.

Тесты WinDivert не открывают реальный драйвер. Интеграционную проверку захвата,
переключения F9 и поведения GTA выполняют вручную на Windows из elevated-сборки.

## CI

Workflow `.github/workflows/build.yml` запускает Svelte check, rustfmt, Clippy и
Rust-тесты для pull request и push в `main`. Установщики создаются только для тегов
`v*` или ручного `workflow_dispatch`.
