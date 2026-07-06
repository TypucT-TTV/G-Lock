# Тестирование в проекте G-Lock

В проекте используется библиотека `pytest` для запуска и автоматического контроля тестов. Настоящий документ описывает текущую структуру тестов, команды для их запуска и рекомендации по написанию тестов для новых модулей.

---

## 1. Запуск тестов

Для запуска тестов воспользуйтесь Poetry:

```bash
# Запуск всех тестов в проекте
poetry run pytest

# Запуск тестов с выводом подробной информации (verbose)
poetry run pytest -v
```

---

## 2. Структура тестов

Все тесты расположены в корневой папке `tests/`:
- [test_singleton.py](file:///g:/g_lock-3.5.0/tests/test_singleton.py): проверяет работу метакласса одиночки `Singleton` (используется для логгера подключений и других глобальных служб).

---

## 3. Рекомендации по написанию тестов

При добавлении нового функционала старайтесь покрывать его тестами. Ниже описаны основные подходы для этого проекта.

### Тестирование валидаторов (простые юнит-тесты)
Модули валидации IP-адресов ([ip.py](file:///g:/g_lock-3.5.0/g_lock/validator/ip.py)) и имен игроков ([name.py](file:///g:/g_lock-3.5.0/g_lock/validator/name.py)) являются чистыми функциями. Их тестирование тривиально:

```python
from validator.ip import validate_ip

def test_ip_validation_valid():
    assert validate_ip("192.168.1.1") is True

def test_ip_validation_invalid():
    assert validate_ip("999.999.999.999") is False
```

### Тестирование конфигурации
При тестировании загрузки конфигураций ([configdata.py](file:///g:/g_lock-3.5.0/g_lock/config/configdata.py)) используйте фикстуры `pytest` для создания временных файлов конфигурации, чтобы не затирать реальные файлы пользователя:

```python
import pytest
import json

@pytest.fixture
def temp_config_file(tmp_path):
    config_file = tmp_path / "test_config.json"
    data = {"language": "en", "whitelist": []}
    config_file.write_text(json.dumps(data))
    return config_file
```

### Мокирование WinDivert и сетевой логики
Драйвер WinDivert требует прав администратора и работает только в среде ОС Windows. Для тестов, запускаемых в CI/CD (например, GitHub Actions в контейнерах Ubuntu), реальный вызов `pydivert` невозможен.

Используйте библиотеку `unittest.mock` для изоляции сетевых вызовов:

```python
from unittest.mock import MagicMock, patch

@patch("pydivert.WinDivert")
def test_network_session_start(mock_windivert):
    # Создаем мок-объект WinDivert
    mock_instance = MagicMock()
    mock_windivert.return_value = mock_instance
    
    # Имитируем получение пакетов
    mock_instance.__enter__.return_value = [
        MagicMock(payload=b"test_packet", interface=1)
    ]
    
    # Здесь вызывается логика фильтрации
    # ...
```
