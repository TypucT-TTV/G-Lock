---
name: poetry-build-automation
description: Помогает агенту управлять зависимостями Poetry, запускать проверки линтерами (black, isort, mypy, flake8) и автоматизировать сборку проекта G-Lock в один исполняемый файл через PyInstaller.
---

# Навык автоматизации сборки и проверок (Poetry & PyInstaller) в G-Lock

Этот навык содержит инструкции по управлению проектом с помощью инструмента Poetry, настройки линтеров и запуска процесса сборки в `.exe` файл для Windows.

---

## 🛠️ Среда окружения Poetry

Проект использует Poetry для изоляции зависимостей. Основные команды разработчика:

* **Установка зависимостей**:
  ```bash
  poetry install
  ```
  Это установит библиотеки из [pyproject.toml](file:///g:/guardian-3.5.0/pyproject.toml) и зафиксирует версии в `poetry.lock`.
* **Запуск скриптов**:
  ```bash
  poetry run python g_lock
  ```
  Запуск приложения G-Lock напрямую из исходного кода в изолированном виртуальном окружении.

---

## 🔍 Линтинг и проверки качества кода

Перед каждым коммитом код должен проверяться с помощью статических анализаторов. Вы можете запускать их как по отдельности, так и через `pre-commit` хуки.

* **Запуск форматирования (Black)**:
  ```bash
  poetry run black g_lock tests
  ```
* **Запуск сортировки импортов (Isort)**:
  ```bash
  poetry run isort g_lock tests
  ```
* **Запуск статической типизации (Mypy)**:
  ```bash
  poetry run mypy g_lock
  ```
* **Запуск линтера стилей (Flake8)**:
  ```bash
  poetry run pflake8 g_lock tests
  ```
  *(Примечание: используется `pflake8`, так как настройки flake8 заданы в `pyproject.toml`)*.
* **Автоматические хуки (Pre-commit)**:
  ```bash
  poetry run pre-commit run --all-files
  ```

---

## 📦 Сборка исполняемого файла (.exe)

Сборка осуществляется с помощью PyInstaller через встроенный скрипт Poetry:

* **Команда запуска сборки**:
  ```bash
  poetry run build
  ```
  Эта команда вызывает функцию `build` из модуля `g_lock.build` (см. `[tool.poetry.scripts]` в [pyproject.toml](file:///g:/guardian-3.5.0/pyproject.toml)).
* **Скрипт сборки**:
  Скрипт сборки [build.py](file:///g:/guardian-3.5.0/g_lock/build.py) конфигурирует параметры запуска PyInstaller:
  - Сборка в один файл (`--onefile`).
  - Отключение отображения консоли при старте (`--noconsole`).
  - Упаковка необходимых ресурсов (таких как `db.json` и `data.json`).
* **Итоговый файл**: Готовый `.exe` файл сохраняется в директорию `dist/`.
