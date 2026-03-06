# 🚀 Быстрый старт рефакторинга

**Дата:** 6 марта 2026  
**Статус:** Этап 2 завершён ✅

---

## ✅ Что сделано

### Этап 1: Порты и Mock-объекты (Неделя 1)

| Компонент | Файл | Статус |
|-----------|------|--------|
| **Порты (Ports)** | `core/infrastructure/interfaces/ports.py` | ✅ 7 портов |
| **Mock-порты** | `tests/mocks/ports.py` | ✅ 7 mock-классов |
| **Примеры тестов** | `tests/unit/example/test_skill_with_mocks.py` | ✅ 10/10 passed |

### Этап 2: Адаптеры (Неделя 2) — НОВОЕ!

| Компонент | Файл | Статус |
|-----------|------|--------|
| **PostgreSQLAdapter** | `core/infrastructure/adapters/database/postgresql_adapter.py` | ✅ Готов |
| **SQLiteAdapter** | `core/infrastructure/adapters/database/postgresql_adapter.py` | ✅ Готов |
| **LlamaCppAdapter** | `core/infrastructure/adapters/llm/llama_adapter.py` | ✅ Готов |
| **MockLLMAdapter** | `core/infrastructure/adapters/llm/llama_adapter.py` | ✅ Готов |
| **FAISSAdapter** | `core/infrastructure/adapters/vector/faiss_adapter.py` | ✅ Готов |
| **MockVectorAdapter** | `core/infrastructure/adapters/vector/faiss_adapter.py` | ✅ Готов |
| **MemoryCacheAdapter** | `core/infrastructure/adapters/cache/memory_cache_adapter.py` | ✅ Готов |
| **RedisCacheAdapter** | `core/infrastructure/adapters/cache/memory_cache_adapter.py` | ✅ Готов |
| **Интеграционные тесты** | `tests/integration/adapters/test_adapter_integration.py` | ✅ 21/21 passed |

---

## 📦 Установка

Ничего дополнительно устанавливать не нужно. Все зависимости уже в `requirements.txt`.

---

## 🧪 Запуск тестов

### 1. Примеры тестов с mock-портами

```bash
# Все примеры
pytest tests/unit/example/ -v

# Конкретный тест
pytest tests/unit/example/test_skill_with_mocks.py::TestExampleSkillWithDB -v
```

**Ожидаемый результат:**
```
======================== 10 passed in 0.21s ========================
```

---

## 📚 Как использовать порты

### Шаг 1: Импортировать порт

```python
from core.infrastructure.interfaces.ports import DatabasePort, LLMPort
```

### Шаг 2: Внедрить в компонент

```python
class BookLibrarySkill(BaseSkill):
    def __init__(
        self,
        name: str,
        db_port: DatabasePort,  # ← Абстракция
        llm_port: LLMPort,
        executor: ActionExecutor
    ):
        self._db_port = db_port
        self._llm_port = llm_port
        self._executor = executor
```

### Шаг 3: Использовать в коде

```python
async def execute(self, ...):
    # ✅ Через порт
    results = await self._db_port.query(sql, params)
    
    # ✅ Через порт
    response = await self._llm_port.generate(messages)
```

---

## 🧪 Как тестировать с моками

### Пример 1: Тест с MockDatabasePort

```python
from tests.mocks.ports import MockDatabasePort

@pytest.fixture
def mock_db():
    return MockDatabasePort(predefined_results={
        "SELECT * FROM books": [
            {"id": 1, "title": "Test Book"}
        ]
    })

async def test_search(mock_db):
    skill = BookLibrarySkill(db_port=mock_db, ...)
    await skill.initialize()
    
    results = await skill.search_books("Test")
    
    assert len(results) == 1
    assert mock_db.queries_executed[0]["sql"].startswith("SELECT")
```

### Пример 2: Тест с MockLLMPort

```python
from tests.mocks.ports import MockLLMPort

@pytest.fixture
def mock_llm():
    return MockLLMPort(predefined_responses=[
        "Mock analysis result"
    ])

async def test_analyze(mock_llm):
    skill = BookLibrarySkill(llm_port=mock_llm, ...)
    
    result = await skill.analyze_book("Book content")
    
    assert mock_llm.call_count == 1
    assert result["analysis"] == "Mock analysis result"
```

---

## 📊 Доступные порты

| Порт | Назначение | Mock |
|------|-----------|------|
| `DatabasePort` | Работа с БД | `MockDatabasePort` |
| `LLMPort` | Генерация текста | `MockLLMPort` |
| `VectorPort` | Векторный поиск | `MockVectorPort` |
| `CachePort` | Кэширование | `MockCachePort` |
| `EventPort` | События | `MockEventPort` |
| `StoragePort` | Файлы | `MockStoragePort` |
| `MetricsPort` | Метрики | `MockMetricsPort` |

---

## 🎯 Следующие шаги

### Неделя 1: Базовые порты

1. ✅ Создать `core/infrastructure/interfaces/ports.py`
2. ✅ Создать `tests/mocks/ports.py`
3. ⬜ Создать адаптеры для текущих провайдеров:
   - `core/infrastructure/adapters/database/postgresql_adapter.py`
   - `core/infrastructure/adapters/llm/vllm_adapter.py`
   - `core/infrastructure/adapters/vector/faiss_adapter.py`

### Неделя 2: Миграция компонентов

1. ⬜ Обновить `BookLibrarySkill` на использование портов
2. ⬜ Написать юнит-тесты для `BookLibrarySkill` с моками
3. ⬜ Повторить для других навыков

### Неделя 3: Удаление дублирования

1. ⬜ Удалить `core/utils/lifecycle.py`
2. ⬜ Обновить импорты на `core/components/lifecycle.py`
3. ⬜ Запустить все тесты для проверки

---

## 🔍 Проверка прогресса

```bash
# 1. Тесты без инфраструктуры
pytest tests/unit/  # Должно работать без БД/LLM

# 2. Нет прямых импортов инфраструктуры в skills
grep -r "infrastructure_context" core/application/skills/  # Должно быть 0 matches

# 3. Порты используются
grep -r "DatabasePort" core/application/  # Должно быть > 0 matches
```

---

## 📚 Ресурсы

- [REFACTORING_PLAN.md](REFACTORING_PLAN.md) — Полный план
- [core/infrastructure/interfaces/ports.py](core/infrastructure/interfaces/ports.py) — Интерфейсы
- [tests/mocks/ports.py](tests/mocks/ports.py) — Mock-реализации
- [tests/unit/example/test_skill_with_mocks.py](tests/unit/example/test_skill_with_mocks.py) — Примеры тестов

---

## ❓ Вопросы

### Почему порты лучше прямого доступа?

| Критерий | Прямой доступ | Порты |
|----------|--------------|-------|
| **Тестирование** | ❌ Нужна реальная БД | ✅ Mock за 1ms |
| **Заменяемость** | ❌ Жёсткая привязка | ✅ Можно сменить БД |
| **Границы слоёв** | ❌ Нарушены | ✅ Соблюдены |

### Когда использовать порты?

- ✅ Для **внешних зависимостей** (БД, LLM, кэш)
- ✅ Для **тестируемости** компонентов
- ❌ Для **внутренней логики** (модели данных, утилиты)

### Сколько портов нужно?

Начните с минимума:
1. `DatabasePort` — для работы с данными
2. `LLMPort` — для генерации текста
3. `CachePort` — для кэширования

Остальные добавляйте по мере необходимости.
