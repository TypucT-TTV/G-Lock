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
- сравнение SemVer из GitHub Releases и выбор NSIS-установщика среди assets;
- загрузка Azure ranges и lookup relay IP;
- диапазон `/0` в двухуровневой relay-таблице;
- IPv4/UDP parser с переменным IHL;
- heartbeat разрешён для адресов вне blacklist;
- абсолютный приоритет blacklist над heartbeat и кэшем разрешённых адресов;
- разрешение известных и блокировка неизвестных peer в Lock;
- отклонение неподдерживаемых типов сессий и списков;
- выбор peer IP по source для inbound и destination для outbound.

Тесты WinDivert не открывают реальный драйвер. Интеграционную проверку захвата,
переключения выбранной клавишей, расширенного blacklist и поведения GTA выполняют вручную на Windows
из elevated-сборки. Отдельно проверяют, что UI не предлагает Solo/Whitelist и не
содержит быстрых кнопок блокировки в журнале. Также записывают одиночную F-клавишу
и сочетание вроде Ctrl+Shift+K, проверяют отказ для обычной буквы без модификатора
и зарезервированного Ctrl+F9, сохраняют настройки и проверяют немедленное переключение, перезапуск приложения,
миграцию старого `data.json` и сохранение `%LOCALAPPDATA%\G-Lock\data.json` после
обновления установщиком. Статус версии проверяют с сетью и без неё.

## CI

Workflow `.github/workflows/build.yml` запускает Svelte check, rustfmt, Clippy и
Rust-тесты для pull request и push в `main`. Установщики создаются только для тегов
`v*` или ручного `workflow_dispatch`.
