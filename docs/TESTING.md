# 🧪 Руководство по тестированию koru-agent

> **Версия:** 5.29.0
> **Дата обновления:** 2026-03-04
> **Статус:** approved

---

## 📋 Содержание

1. [Быстрый старт](#быстрый-старт)
2. [Структура тестов](#структура-тестов)
3. [Запуск тестов](#запуск-тестов)
4. [Написание тестов](#написание-тестов)
5. [CI/CD](#cicd)
6. [Покрытие кода](#покрытие-кода)
7. [Troubleshooting](#troubleshooting)

---

## 🚀 Быстрый старт

### Установка зависимостей

```bash
# Установить зависимости для разработки
pip install -r requirements-dev.txt

# Проверить установку
pytest --version
```

### Запуск всех тестов

```bash
# Все тесты
pytest tests/ -v

# Быстрый запуск (без coverage)
pytest tests/ -q

# С coverage
pytest tests/ --cov=core --cov-report=html
```

---

## 📁 Структура тестов

```
tests/
├── unit/                          # Модульные тесты
│   ├── observability/             # Тесты observability
│   ├── infrastructure/            # Тесты инфраструктуры
│   ├── config/                    # Тесты конфигурации
│   └── ...
│
├── integration/                   # Интеграционные тесты
│   ├── integration_infrastructure/ # Интеграция инфраструктуры
│   ├── test_error_handling.py     # Negative тесты
│   └── ...
│
├── e2e/                           # E2E тесты
│   ├── test_benchmark_cycle.py    # Benchmark цикл
│   └── test_optimization_cycle.py # Optimization цикл
│
├── benchmark/                     # Benchmark тесты
│   └── test_mock_llm_performance.py
│
└── stress/                        # Стресс тесты
    └── test_stress.py
```

### Типы тестов

| Тип | Расположение | Время | Покрытие |
|-----|-------------|-------|----------|
| **Unit** | `tests/unit/` | < 1 мин | Критический путь |
| **Integration** | `tests/integration/` | 1-5 мин | Взаимодействие |
| **E2E** | `tests/e2e/` | 5-15 мин | Полный цикл |
| **Benchmark** | `tests/benchmark/` | 1-2 мин | Производительность |
| **Stress** | `tests/stress/` | 5-10 мин | Нагрузка |

---

## 🏃 Запуск тестов

### Базовые команды

```bash
# Все тесты
pytest tests/ -v

# Только unit тесты
pytest tests/unit/ -v

# Только integration тесты
pytest tests/integration/ -v

# Только E2E тесты
pytest tests/e2e/ -v

# Конкретный файл
pytest tests/unit/observability/test_observability_manager.py -v

# Конкретный тест
pytest tests/unit/observability/test_observability_manager.py::TestObservabilityManagerCreation::test_create_observability_manager -v

# По ключевому слову
pytest tests/ -k "observability" -v
```

### С coverage

```bash
# Coverage для конкретного модуля
pytest tests/unit/observability/ --cov=core/observability --cov-report=html

# Coverage для всего проекта
pytest tests/ --cov=core --cov-report=html --cov-report=term-missing

# Открыть HTML отчёт
# Windows:
start htmlcov\index.html
# macOS/Linux:
open htmlcov/index.html
```

### С флагами

```bash
# Тихий режим
pytest tests/ -q

# Подробный вывод
pytest tests/ -vv

# Остановить после первой ошибки
pytest tests/ -x

# Повторить упавшие тесты
pytest tests/ --lf

# Запустить последние упавшие тесты
pytest tests/ --ff

# Таймаут для тестов
pytest tests/ --timeout=60

# Параллельный запуск
pytest tests/ -n auto
```

### Маркировка тестов

```bash
# Запустить только E2E тесты
pytest tests/ -m e2e -v

# Запустить только integration тесты
pytest tests/ -m integration -v

# Запустить только stress тесты
pytest tests/ -m stress -v

# Исключить медленные тесты
pytest tests/ -m "not slow" -v
```

---

## ✍️ Написание тестов

### Структура теста

```python
"""
Тесты для компонента X.

ТЕСТЫ:
- test_x_creation: Создание компонента
- test_x_operation: Операция компонента
- test_x_error: Обработка ошибок
"""
import pytest
from unittest.mock import AsyncMock, MagicMock

from core.x import ComponentX


@pytest.fixture
def component_x():
    """Фикстура: компонент X"""
    return ComponentX()


class TestComponentXCreation:
    """Тесты создания компонента X"""

    def test_create_component_x(self):
        """Создание компонента X"""
        component = ComponentX()

        assert component is not None
        assert component.is_initialized is False

    @pytest.mark.asyncio
    async def test_initialize_component_x(self, component_x):
        """Инициализация компонента X"""
        result = await component_x.initialize()

        assert result is True
        assert component_x.is_initialized is True


class TestComponentXOperation:
    """Тесты операций компонента X"""

    @pytest.mark.asyncio
    async def test_operation_success(self, component_x):
        """Успешная операция"""
        await component_x.initialize()

        result = await component_x.execute(param="value")

        assert result is not None
        assert result.success is True

    @pytest.mark.asyncio
    async def test_operation_with_error(self, component_x):
        """Операция с ошибкой"""
        await component_x.initialize()

        with pytest.raises(ValueError):
            await component_x.execute(param=None)
```

### Negative тесты

```python
class TestComponentXErrors:
    """Negative тесты компонента X"""

    @pytest.mark.asyncio
    async def test_timeout_error(self, component_x):
        """Тест: Timeout операции"""
        import asyncio

        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(
                component_x.execute(slow=True),
                timeout=0.1
            )

    @pytest.mark.asyncio
    async def test_connection_error(self, component_x):
        """Тест: Ошибка соединения"""
        component_x.connection = AsyncMock(side_effect=ConnectionError("Connection lost"))

        with pytest.raises(ConnectionError):
            await component_x.execute()

    @pytest.mark.asyncio
    async def test_invalid_response(self, component_x):
        """Тест: Невалидный ответ"""
        component_x.get_response = AsyncMock(return_value="Invalid JSON {{{")

        with pytest.raises(json.JSONDecodeError):
            await component_x.parse_response()
```

### Фикстуры

```python
# tests/conftest.py
import pytest
from pathlib import Path
import tempfile
import shutil


@pytest.fixture
def temp_data_dir():
    """Фикстура: временная директория данных"""
    temp_dir = tempfile.mkdtemp()
    (Path(temp_dir) / "prompts").mkdir(exist_ok=True)
    (Path(temp_dir) / "contracts").mkdir(exist_ok=True)
    yield Path(temp_dir)
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def mock_llm_response():
    """Фикстура: mock LLM ответ"""
    from unittest.mock import MagicMock

    response = MagicMock()
    response.content = '{"answer": "Test answer"}'
    response.model = 'test-mock'
    response.tokens_used = 100
    response.generation_time = 0.5
    return response


@pytest.fixture
async def infrastructure_context(temp_data_dir):
    """Фикстура: инициализированный InfrastructureContext"""
    from core.config.models import SystemConfig
    from core.infrastructure.context.infrastructure_context import InfrastructureContext

    config = SystemConfig(
        data_dir=str(temp_data_dir),
        llm_providers={
            'test_llm': {
                'provider_type': 'llama_cpp',
                'model_name': 'test',
                'enabled': True,
                'parameters': {
                    'model_path': 'models/test.gguf',
                    'n_ctx': 100
                }
            }
        }
    )

    infra = InfrastructureContext(config)
    await infra.initialize()
    yield infra
    await infra.shutdown()
```

---

## 🔄 CI/CD

### GitHub Actions

**Файлы workflow:**
- `.github/workflows/ci-cd.yml` - Основной CI/CD пайплайн
- `.github/workflows/nightly-e2e.yml` - Nightly E2E тесты

### Триггеры

```yaml
# Push на основные ветки
on:
  push:
    branches: [agentv5, main, master]

# Pull request
on:
  pull_request:
    branches: [agentv5, main, master]

# Nightly build (каждый день в 2:00 UTC)
on:
  schedule:
    - cron: '0 2 * * *'

# Ручной запуск
on:
  workflow_dispatch:
```

### Jobs

| Job | Описание | Время |
|-----|----------|-------|
| **test** | Unit + Integration + E2E тесты | ~15 мин |
| **security** | Проверка зависимостей | ~2 мин |
| **docs** | Валидация документации | ~1 мин |
| **version-check** | Проверка версий | ~1 мин |
| **nightly-e2e** | Nightly E2E тесты | ~30 мин |

### Артефакты

- `coverage-report/` - HTML отчёт coverage
- `test-results/` - XML результаты тестов

---

## 📊 Покрытие кода

### Конфигурация

**Файл:** `.coveragerc`

```ini
[run]
branch = True
source = core/
omit =
    */tests/*
    */__pycache__/*

[report]
precision = 2
show_missing = True
skip_covered = False

[html]
directory = htmlcov
```

### Целевые метрики

| Модуль | Цель | Статус |
|--------|------|--------|
| **observability** | 95% | ✅ 98% |
| **infrastructure** | 90% | 🟡 85% |
| **application** | 90% | 🟡 80% |
| **config** | 95% | ✅ 96% |
| **models** | 95% | ✅ 97% |

### Проверка порога

```bash
# Проверка порога 80%
pytest tests/ --cov=core --cov-fail-under=80

# В CI/CD
python -c "
import xml.etree.ElementTree as ET
tree = ET.parse('coverage.xml')
root = tree.getroot()
lines_valid = int(root.get('lines-valid'))
lines_covered = int(root.get('lines-covered'))
coverage_pct = (lines_covered / lines_valid * 100) if lines_valid > 0 else 0
if coverage_pct < 80:
    exit(1)
"
```

---

## 🔧 Troubleshooting

### Частые проблемы

#### 1. Тесты не находят модули

**Ошибка:** `ModuleNotFoundError: No module named 'core'`

**Решение:**
```bash
# Установить пакет в режиме разработки
pip install -e .

# Или добавить PYTHONPATH
export PYTHONPATH=$PYTHONPATH:$(pwd)
```

#### 2. Async тесты не работают

**Ошибка:** `async def functions are not natively supported`

**Решение:**
```python
# Добавить pytest.mark.asyncio
@pytest.mark.asyncio
async def test_async_function():
    ...
```

#### 3. Фикстуры не работают

**Ошибка:** `fixture 'x' not found`

**Решение:**
- Проверить что фикстура в `conftest.py` или импортирована
- Проверить область видимости (scope)

#### 4. Coverage не собирается

**Ошибка:** `No data to report`

**Решение:**
```bash
# Проверить что pytest-cov установлен
pip install pytest-cov

# Проверить путь к исходникам
pytest tests/ --cov=core/ --cov-report=term-missing
```

#### 5. Тесты падают в CI/CD но не локально

**Причины:**
- Разные версии Python
- Разные зависимости
- Разное окружение

**Решение:**
```bash
# Использовать ту же версию Python
python --version

# Обновить зависимости
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Запустить в Docker (как в CI/CD)
docker run -it python:3.11 bash
```

### Логи

**Где искать:**
- GitHub Actions: `Actions` → `Workflow run` → `Job`
- Локально: `pytest tests/ -v --log-cli-level=DEBUG`

### Отчёты

**Coverage:**
- Локально: `htmlcov/index.html`
- CI/CD: Артефакты workflow run

**Тесты:**
- Локально: `pytest-results.xml`
- CI/CD: Артефакты workflow run

---

## 📞 Поддержка

**Вопросы по тестированию:**
- Создать issue с тегом `testing`
- Приложить отчёт coverage
- Указать шаги для воспроизведения

**Контакты:**
- Telegram: @koru-agent-dev
- Email: dev@koru-agent.com

---

## 📚 Дополнительные ресурсы

- [pytest документация](https://docs.pytest.org/)
- [pytest-cov документация](https://pytest-cov.readthedocs.io/)
- [GitHub Actions документация](https://docs.github.com/en/actions)
- [Coverage.py документация](https://coverage.readthedocs.io/)
