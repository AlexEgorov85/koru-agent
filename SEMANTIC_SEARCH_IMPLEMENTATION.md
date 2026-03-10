# Отчёт: Добавление семантического поиска в BookLibrarySkill

## Обзор изменений

Добавлена новая capability `book_library.semantic_search` для семантического поиска по текстам книг с использованием векторной базы данных (FAISS) и инструмента `VectorBooksTool`.

---

## Выполненные изменения

### 1. Конфигурация векторного поиска

**Файл:** `core/config/defaults/dev.yaml`

Добавлена секция `vector_search`:

```yaml
vector_search:
  enabled: true
  indexes:
    knowledge: "knowledge_index.faiss"
    history: "history_index.faiss"
    docs: "docs_index.faiss"
    books: "books_index.faiss"
  faiss:
    index_type: "Flat"
    metric: "IP"
  embedding:
    model_name: "all-MiniLM-L6-v2"
    dimension: 384
  chunking:
    chunk_size: 500
    chunk_overlap: 50
    min_chunk_size: 50
  storage:
    base_path: "data/vector"
```

---

### 2. Регистрация VectorBooksTool

**Файл:** `core/config/app_config.py`

В метод `AppConfig.from_discovery` добавлена регистрация инструмента:

```python
if 'vector_books_tool' not in tool_configs:
    tool_configs['vector_books_tool'] = ComponentConfig(
        variant_id=f"vector_books_tool_{profile}",
        side_effects_enabled=(profile == "prod"),
        detailed_metrics=False,
        parameters={},
        dependencies=[],
        prompt_versions={
            "vector_books.search": "v1.0.0",
            "vector_books.get_document": "v1.0.0",
            "vector_books.analyze": "v1.0.0",
            "vector_books.query": "v1.0.0"
        },
        input_contract_versions={...},
        output_contract_versions={...}
    )
```

---

### 3. Контракты для semantic_search

**Входной контракт:** `data/contracts/skill/book_library/book_library.semantic_search_input_v1.0.0.yaml`

```yaml
capability: book_library.semantic_search
version: v1.0.0
status: active
component_type: skill
direction: input
schema_data:
  type: object
  properties:
    query:
      type: string
      description: "Текст запроса для семантического поиска"
    top_k:
      type: integer
      description: "Количество результатов"
      default: 10
    min_score:
      type: number
      description: "Минимальный порог схожести"
      default: 0.5
  required:
    - query
```

**Выходной контракт:** `data/contracts/skill/book_library/book_library.semantic_search_output_v1.0.0.yaml`

```yaml
capability: book_library.semantic_search
version: v1.0.0
status: active
component_type: skill
direction: output
schema_data:
  type: object
  properties:
    results:
      type: array
      items:
        type: object
        properties:
          chunk_id: {type: string}
          document_id: {type: string}
          book_id: {type: integer}
          chapter: {type: integer}
          score: {type: number}
          content: {type: string}
          metadata: {type: object}
    total_found: {type: integer}
    execution_type: {type: string, default: "vector"}
```

---

### 4. Обновление BookLibrarySkill

**Файл:** `core/application/skills/book_library/skill.py`

#### 4.1. Добавлена capability в `supported_capabilities`:

```python
self.supported_capabilities = {
    "book_library.search_books": self._search_books_dynamic,
    "book_library.execute_script": self._execute_script_static,
    "book_library.list_scripts": self._list_scripts,
    "book_library.semantic_search": self._semantic_search  # новая
}
```

#### 4.2. Добавлена Capability в `get_capabilities()`:

```python
Capability(
    name="book_library.semantic_search",
    description="Семантический поиск по текстам книг с использованием векторной БД (быстрый поиск по смыслу, а не ключевым словам)",
    skill_name=self.name,
    supported_strategies=["react", "planning"],
    visiable=True,
    meta={
        "contract_version": "v1.0.0",
        "prompt_version": "v1.0.0",
        "requires_llm": False,
        "execution_type": "vector"
    }
)
```

#### 4.3. Реализован метод `_semantic_search()`:

Метод:
1. Валидирует входные параметры (`query`, `top_k`, `min_score`)
2. Получает инструмент `vector_books_tool` через `application_context.components`
3. Вызывает `vector_tool.execute()` с capability `vector_books.search`
4. Обрабатывает результат и возвращает валидированную Pydantic модель

---

### 5. Промпт для semantic_search

**Файл:** `data/prompts/skill/book_library/book_library.semantic_search.system_v1.0.0.yaml`

Системный промпт с инструкциями для LLM по использованию семантического поиска.

---

## Использование

### Пример вызова через агент

```python
# Запрос к агенту с использованием семантического поиска
result = await agent.execute_goal(
    "Найди книги, где говорится о любви и отношениях",
    session_context=session_context
)
```

### Прямой вызов capability

```python
from core.application.context.application_context import ApplicationContext
from core.models.data.capability import Capability

# Получение навыка
book_skill = app_context.components.get(ComponentType.SKILL, "book_library")

# Вызов семантического поиска
result = await book_skill.execute(
    capability=Capability(
        name="book_library.semantic_search",
        description="...",
        skill_name="book_library"
    ),
    parameters={
        "query": "искусственный интеллект и машинное обучение",
        "top_k": 10,
        "min_score": 0.5
    },
    execution_context=exec_context
)

# Результат
print(f"Найдено результатов: {result.data.total_found}")
for item in result.data.results:
    print(f"  - Книга {item.book_id}, глава {item.chapter}, score={item.score:.2f}")
    print(f"    {item.content[:100]}...")
```

---

## Сравнение capability BookLibrarySkill

| Capability | Тип | LLM | Время | Описание |
|------------|-----|-----|-------|----------|
| `book_library.search_books` | dynamic | ✅ | ~2000мс | Генерация SQL через LLM |
| `book_library.execute_script` | static | ❌ | ~100мс | Выполнение заготовленного SQL |
| `book_library.semantic_search` | vector | ❌ | ~100-500мс | Семантический поиск по тексту |
| `book_library.list_scripts` | informational | ❌ | ~10мс | Список доступных скриптов |

---

## Требования

### 1. Векторный индекс книг

Для работы семантического поиска необходим FAISS-индекс книг:

```bash
# Запуск скрипта индексации (если существует)
python scripts/vector/initial_indexing.py
```

Или создайте индекс программно:

```python
from core.infrastructure.context.infrastructure_context import InfrastructureContext
from core.infrastructure.providers.vector.faiss_provider import FAISSProvider

# Инициализация FAISS провайдера
provider = FAISSProvider(dimension=384, config=faiss_config)
await provider.initialize()

# Индексация книг (псевдокод)
for book in books:
    chunks = chunk_text(book.content)
    for chunk in chunks:
        embedding = await embedding_provider.generate([chunk.text])
        await provider.add(
            vector=embedding[0],
            metadata={
                "book_id": book.id,
                "chapter": chunk.chapter,
                "content": chunk.text
            }
        )

# Сохранение индекса
await provider.save("data/vector/books_index.faiss")
```

### 2. Модель эмбеддингов

Убедитесь, что модель `all-MiniLM-L6-v2` доступна:

```python
from sentence_transformers import SentenceTransformer
model = SentenceTransformer('all-MiniLM-L6-v2')
```

---

## Тестирование

### 1. Проверка инициализации

```bash
python -c "
from core.config.models import SystemConfig
from core.infrastructure.context.infrastructure_context import InfrastructureContext

config = SystemConfig.from_yaml('core/config/defaults/dev.yaml')
infra = InfrastructureContext(config)
await infra.initialize()

print('FAISS провайдеры:', list(infra._faiss_providers.keys()))
print('Books индекс:', 'books' in infra._faiss_providers)
"
```

### 2. Проверка capability

```bash
python -c "
from core.application.context.application_context import ApplicationContext
from core.models.enums.common_enums import ComponentType

app_context = ApplicationContext(...)
book_skill = app_context.components.get(ComponentType.SKILL, 'book_library')

capabilities = book_skill.get_capabilities()
for cap in capabilities:
    print(f'{cap.name}: {cap.description}')
"
```

### 3. Интеграционный тест

```python
import asyncio
from core.application.skills.book_library.skill import BookLibrarySkill

async def test_semantic_search():
    # Инициализация контекста
    app_context = ApplicationContext(...)
    book_skill = app_context.components.get(ComponentType.SKILL, 'book_library')
    await book_skill.initialize()
    
    # Вызов семантического поиска
    result = await book_skill.execute(
        capability=Capability(name='book_library.semantic_search', ...),
        parameters={'query': 'любовь и отношения', 'top_k': 5},
        execution_context=ExecutionContext(...)
    )
    
    print(f'Status: {result.status}')
    print(f'Results: {result.data.total_found}')
    for r in result.data.results:
        print(f'  Book {r.book_id}: {r.content[:50]}...')

asyncio.run(test_semantic_search())
```

---

## Возможные ошибки и решения

### Ошибка: "Инструмент vector_books_tool не зарегистрирован"

**Решение:** Убедитесь, что `vector_books_tool` зарегистрирован в `AppConfig`:

```python
print('Tool configs:', list(app_config.tool_configs.keys()))
```

### Ошибка: "FAISS provider for books not initialized"

**Решение:** Проверьте, что:
1. В конфигурации `vector_search.enabled: true`
2. Индекс `books_index.faiss` существует в `data/vector/`
3. `InfrastructureContext._init_vector_search()` выполнен успешно

### Ошибка: "Контракт book_library.semantic_search.input не загружен"

**Решение:** Убедитесь, что:
1. Файл контракта существует в `data/contracts/skill/book_library/`
2. `ResourceDiscovery.discover_contracts()` находит контракт
3. Статус контракта `active`

---

## Следующие шаги

1. **Создание индекса книг:** Запустить скрипт индексации текстов книг
2. **Тестирование:** Проверить работу семантического поиска на реальных запросах
3. **Оптимизация:** Настроить параметры `chunk_size`, `min_score` для лучшей точности
4. **Мониторинг:** Добавить метрики качества поиска (precision, recall)

---

## Файлы изменений

| Файл | Изменения |
|------|-----------|
| `core/config/defaults/dev.yaml` | Добавлена секция `vector_search` |
| `core/config/app_config.py` | Регистрация `vector_books_tool` |
| `core/application/skills/book_library/skill.py` | Добавлена capability `semantic_search` |
| `data/contracts/skill/book_library/book_library.semantic_search_input_v1.0.0.yaml` | Новый файл |
| `data/contracts/skill/book_library/book_library.semantic_search_output_v1.0.0.yaml` | Новый файл |
| `data/prompts/skill/book_library/book_library.semantic_search.system_v1.0.0.yaml` | Новый файл |

---

**Дата:** 9 марта 2026 г.  
**Статус:** ✅ Завершено
