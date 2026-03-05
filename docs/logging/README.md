# 📋 Система логирования koru-agent

## Обзор

Единая система логирования для koru-agent, обеспечивающая:
- **Централизованное управление** логами через LogManager
- **Быстрый поиск** сессий через LogIndexer (< 100мс)
- **Автоматическую ротацию** и очистку старых логов
- **Структурированный формат** JSONL для машинного чтения
- **Трассировку LLM вызовов** через correlation_id

---

## 🔗 Correlation ID для трассировки LLM вызовов

### Архитектура

```
┌─────────────────────────────────────────────────────────────┐
│                    Компоненты (Patterns/Skills)              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │ ReActPattern │  │PlanningSkill │  │FinalAnswer   │      │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘      │
│         └─────────────────┴─────────────────┘              │
│                           │                                │
│                           ▼                                │
│                  ┌─────────────────┐                       │
│                  │  LLMRequest     │                       │
│                  │  (без correlation_id) │                 │
│                  └────────┬────────┘                       │
└───────────────────────────┼─────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│              Infrastructure Layer (Providers)                │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐  │
│  │              BaseLLMProvider                          │  │
│  │  ┌────────────────────────────────────────────────┐  │  │
│  │  │  generate_structured(request):                 │  │  │
│  │  │    1. correlation_id = uuid.uuid4() ✅         │  │  │
│  │  │    2. Publish LLM_PROMPT_GENERATED             │  │  │
│  │  │    3. Вызов LLM (_generate_structured_impl)    │  │  │
│  │  │    4. Publish LLM_RESPONSE_RECEIVED            │  │  │
│  │  └────────────────────────────────────────────────┘  │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

### Принцип работы

1. **Генерация**: `correlation_id` генерируется в `BaseLLMProvider.generate_structured()` автоматически
2. **Публикация**: Один ID используется для обоих событий:
   - `LLM_PROMPT_GENERATED` — перед вызовом LLM
   - `LLM_RESPONSE_RECEIVED` — после получения ответа
3. **Трассировка**: Позволяет связать промпт и ответ в единый запрос

### Преимущества

| Аспект | Значение |
|--------|----------|
| **Инкапсуляция** | Паттерны не знают о correlation_id |
| **Консистентность** | Единая логика для всех провайдеров |
| **Отсутствие дублирования** | Генерация только в базовом классе |
| **Автоматическое наследование** | Все провайдеры получают бесплатно |

### Пример использования

```python
# Компонент вызывает LLM — correlation_id генерируется автоматически
llm_provider.set_call_context(
    event_bus=event_bus,
    session_id="session_123",
    agent_id="agent_456",
    component="react_pattern",
    phase="think"
)

# correlation_id будет сгенерирован внутри generate_structured()
response = await llm_provider.generate_structured(request)

# События опубликованы с одинаковым correlation_id:
# - LLM_PROMPT_GENERATED(correlation_id="uuid-123")
# - LLM_RESPONSE_RECEIVED(correlation_id="uuid-123")
```

### Поиск по correlation_id

```bash
# Найти все события с correlation_id
python scripts/logs/find_by_correlation.py --correlation-id uuid-123

# Найти пару промпт-ответ
python scripts/logs/find_llm_pair.py --session-id abc123 --phase think
```

---

## 📁 Структура папок

```
logs/
├── active/                        ← Активные логи (текущий день)
│   ├── agent.log                  ← symlink на последний agent_*.log
│   ├── sessions/
│   │   └── latest.log             ← symlink на последнюю сессию
│   └── llm/
│       └── latest.jsonl           ← symlink на последний LLM лог
│
├── archive/                       ← Архив по датам
│   ├── 2026/
│   │   ├── 02/
│   │   │   ├── agent_2026-02-27.log
│   │   │   ├── sessions/
│   │   │   │   └── 2026-02-27_11-56-38_session_abc123.log
│   │   │   └── llm/
│   │   │       └── 2026-02-27_session_abc123.jsonl
│   │   └── 01/
│   └── 2025/
│
├── indexed/                       ← Индексы для поиска
│   ├── sessions_index.jsonl       ← {session_id, timestamp, path}
│   └── agents_index.jsonl         ← {agent_id, session_ids[]}
│
└── config/
    ├── retention_policy.yaml      ← Политика хранения
    └── format_spec.yaml           ← Спецификация форматов
```

---

## 🚀 Быстрый старт

### Инициализация системы

```python
from core.infrastructure.logging import init_logging_system, shutdown_logging_system

# Инициализация
await init_logging_system()

# ... использование ...

# Завершение
await shutdown_logging_system()
```

### Логирование сессии

```python
from core.infrastructure.logging import get_session_logger

# Получение логгера сессии
logger = get_session_logger(session_id)

# Начало сессии
await logger.start(goal="Найти книги Пушкина")

# Логирование LLM вызовов
await logger.log_llm_prompt(
    component="react_pattern",
    phase="think",
    system_prompt="...",
    user_prompt="..."
)

await logger.log_llm_response(
    component="react_pattern",
    phase="think",
    response="...",
    tokens=350,
    latency_ms=1666
)

# Логирование шага
await logger.log_step(
    step_number=1,
    capability="book_library.search_books",
    success=True,
    latency_ms=670
)

# Завершение сессии
await logger.end(success=True, result="Книги найдены")
```

---

## 🔍 Поиск логов

### Найти последнюю сессию

```python
from core.infrastructure.logging import get_latest_session

session = await get_latest_session()
print(f"Session: {session.session_id}")
print(f"Path: {session.path}")
```

### Найти сессию по ID

```python
from core.infrastructure.logging import find_session

session = await find_session("abc123")
```

### Найти все LLM вызовы сессии

```python
from core.infrastructure.logging import get_session_llm_calls

calls = await get_session_llm_calls("abc123")
for call in calls:
    print(f"{call['component']}/{call['phase']}: {call['type']}")
```

### Найти последний LLM вызов

```python
from core.infrastructure.logging import get_last_llm_call

call = await get_last_llm_call("abc123", phase="think")
print(f"Prompt: {call['system_prompt'][:100]}...")
```

---

## 🛠️ CLI утилиты

| Утилита | Описание |
|---------|----------|
| `find_latest_session.py` | Найти последнюю сессию |
| `find_session.py` | Найти сессию по ID/агенту/goal |
| `find_last_llm.py` | Найти последний LLM вызов |
| `cleanup_old_logs.py` | Очистка старых логов |
| `check_log_size.py` | Проверка размера логов |
| `rebuild_index.py` | Перестроить индекс |
| `export_session.py` | Экспорт сессии в JSON |

### Примеры использования

```bash
# Найти последнюю сессию
python scripts/logs/find_latest_session.py

# Найти сессию по ID
python scripts/logs/find_session.py --session-id abc123

# Найти сессии агента
python scripts/logs/find_session.py --agent-id agent_001 --latest

# Найти последний LLM вызов
python scripts/logs/find_last_llm.py --session-id abc123 --phase think

# Очистить логи старше 30 дней (dry-run)
python scripts/logs/cleanup_old_logs.py --days 30 --dry-run

# Проверить размер логов
python scripts/logs/check_log_size.py

# Перестроить индекс
python scripts/logs/rebuild_index.py

# Экспорт сессии
python scripts/logs/export_session.py --session-id abc123 --output session.json
```

---

## 📊 Форматы логов

### Агент (текстовый)

```
2026-02-27T11:56:38.526 | INFO  | koru.agent | 🚀 Agent started | session=abc123
2026-02-27T11:56:41.456 | ERROR | koru.agent | ❌ Error occurred | session=abc123, error=TimeoutError
```

### Сессия (JSONL)

```jsonl
{"timestamp":"2026-02-27T11:56:38.526Z","type":"session_started","session_id":"abc123","agent_id":"agent_001","goal":"Найти книги Пушкина"}
{"timestamp":"2026-02-27T11:56:41.456Z","type":"step_executed","session_id":"abc123","step_number":1,"capability":"book_library.search_books","success":true,"latency_ms":670}
{"timestamp":"2026-02-27T11:56:45.789Z","type":"session_completed","session_id":"abc123","steps":5,"total_time_ms":7263,"success":true}
```

### LLM вызовы (JSONL)

```jsonl
{"timestamp":"2026-02-27T11:56:39.123Z","type":"llm_prompt","session_id":"abc123","component":"react_pattern","phase":"think","system_prompt":"...","user_prompt":"...","prompt_length":1250}
{"timestamp":"2026-02-27T11:56:40.789Z","type":"llm_response","session_id":"abc123","component":"react_pattern","phase":"think","tokens":350,"latency_ms":1666}
```

---

## ⚙️ Конфигурация

### Политика хранения

```yaml
logging:
  retention:
    active_days: 7          # Хранить в active/
    archive_months: 12      # Хранить в archive/
    max_size_mb: 100        # Макс размер файла
    max_files_per_day: 100  # Макс файлов в день
```

### Индексация

```yaml
logging:
  indexing:
    enabled: true
    index_sessions: true
    index_agents: true
    update_interval_sec: 60
```

---

## 📈 Метрики

| Метрика | Значение |
|---------|----------|
| Время поиска сессии | < 100 мс |
| Время записи лога | < 10 мс |
| Экономия места | ×3 (убрано дублирование) |

---

## 📚 Документы

- [Форматы логов](formats.md)
- [Структура папок](structure.md)
- [CLI утилиты](cli.md)
- [Политика хранения](retention.md)
