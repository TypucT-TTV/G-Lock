---
name: tauri-build-automation
description: Помогает агенту собирать и упаковывать приложение G-Lock v2 на базе Tauri v2, компилировать нативный Rust бэкенд и развертывать сборки в NSIS и MSI инсталляторы.
---

# Навык автоматизации сборки и упаковки (Tauri v2) в G-Lock v2

Этот навык содержит инструкции по локальной компиляции, сборке и упаковке приложения G-Lock v2.

---

## 🛠️ Сборка релиза Tauri

Сборка осуществляется через Node CLI с вызовом Tauri Bundler:

* **Команда полной сборки**:
  ```powershell
  npm run tauri build
  ```
  Или через npx:
  ```powershell
  npx tauri build
  ```

* **Что происходит во время сборки**:
  1. Vite компилирует фронтенд (Svelte + TypeScript) в статические файлы в папку `build/`.
  2. Cargo компилирует Rust бэкенд (`g-lock-tauri`) в режиме оптимизации (`release`).
  3. Tauri упаковывает скомпилированные веб-ресурсы, бинарные файлы WinDivert и базу данных `db.json` в результирующие установщики.

* **Результаты сборки**:
  Готовые файлы сохраняются в директорию `src-tauri/target/release/bundle/`:
  - `nsis/G-Lock_<версия>_x64-setup.exe` — установщик для Windows (NSIS).
  - `msi/G-Lock_<версия>_x64_en-US.msi` — MSI-пакет.

---

## 📦 Копирование WinDivert бинарников

Для корректной работы сетевого бэкенда в директории релиза рядом с исполняемым файлом `g-lock-tauri.exe` обязательно должны находиться файлы драйвера WinDivert. `src-tauri/build.rs` проверяет исходные файлы и автоматически копирует их в профиль Cargo. Ручное копирование требуется только как диагностический fallback:

```powershell
Copy-Item -Path "src-tauri\WinDivert.dll" -Destination "src-tauri\target\release\WinDivert.dll" -Force
Copy-Item -Path "src-tauri\WinDivert64.sys" -Destination "src-tauri\target\release\WinDivert64.sys" -Force
```

---

## 🏷️ Процедура обновления версий (SemVer)

При внесении любых изменений, исправлении багов или добавлении новых функций, строго выполняйте обновление версии во всех следующих файлах:

1. `package.json` и `package-lock.json`: `"version": "X.Y.Z"`
2. `src-tauri/Cargo.toml` и запись пакета G-Lock в `src-tauri/Cargo.lock`: `version = "X.Y.Z"`
3. `src-tauri/tauri.conf.json`: `"version": "X.Y.Z"`
4. `src/routes/+page.svelte`: видимая версия в интерфейсе.
