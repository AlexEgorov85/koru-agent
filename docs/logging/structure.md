# 📁 Структура папок системы логирования

## Обзор

Единая структура папок для всех логов koru-agent.

---

## Дерево директорий

```
logs/
│
├── active/                        ← Активные логи (текущий день)
│   ├── agent.log                  → symlink на agent_YYYY-MM-DD.log
│   │
│   ├── sessions/
│   │   └── latest.log             → symlink на последнюю сессию
│   │
│   └── llm/
│       └── latest.jsonl           → symlink на последний LLM лог
│
├── archive/                       ← Архив по датам
│   ├── YYYY/                      ← Год
│   │   ├── MM/                    ← Месяц
│   │   │   ├── agent_YYYY-MM-DD.log
│   │   │   │
│   │   │   ├── sessions/
│   │   │   │   └── YYYY-MM-DD_HH-MM-SS_session_{id}.log
│   │   │   │
│   │   │   └── llm/
│   │   │       └── YYYY-MM-DD_session_{id}.jsonl
│   │   │
│   │   └── ... (другие месяцы)
│   │
│   └── ... (другие годы)
│
├── indexed/                       ← Индексы для поиска
│   ├── sessions_index.jsonl       ← Индекс сессий
│   └── agents_index.jsonl         ← Индекс агентов
│
└── config/
    ├── logging_config.yaml        ← Конфигурация
    ├── retention_policy.yaml      ← Политика хранения
    └── format_spec.yaml           ← Спецификация форматов
```

---

## Детальное описание

### active/

**Назначение:** Быстрый доступ к текущим логам.

**Файлы:**
| Файл | Описание |
|------|----------|
| `agent.log` | Symlink на текущий лог агента |
| `sessions/latest.log` | Symlink на последнюю сессию |
| `llm/latest.jsonl` | Symlink на последний LLM лог |

**Пример использования:**
```bash
# Просмотр последнего лога агента
cat logs/active/agent.log

# Просмотр последней сессии
tail -f logs/active/sessions/latest.log

# Просмотр последних LLM вызовов
cat logs/active/llm/latest.jsonl | tail -20
```

---

### archive/

**Назначение:** Долгосрочное хранение логов.

**Структура:**
- **Год:** `YYYY/` (например, `2026/`)
- **Месяц:** `MM/` (например, `02/`)
- **Типы логов:**
  - `agent_YYYY-MM-DD.log` — логи агента за день
  - `sessions/` — логи сессий
  - `llm/` — логи LLM вызовов

**Примеры имён файлов:**

| Тип | Шаблон | Пример |
|-----|--------|--------|
| Агент | `agent_YYYY-MM-DD.log` | `agent_2026-02-27.log` |
| Сессия | `YYYY-MM-DD_HH-MM-SS_session_{id}.log` | `2026-02-27_11-56-38_session_abc123.log` |
| LLM | `YYYY-MM-DD_session_{id}.jsonl` | `2026-02-27_session_abc123.jsonl` |
| Метрики | `YYYY-MM-DD_{capability}.metrics.jsonl` | `2026-02-27_book_library.metrics.jsonl` |

---

### indexed/

**Назначение:** Быстрый поиск по логам.

**Файлы:**

#### sessions_index.jsonl

Индекс сессий (JSONL формат):
```jsonl
{"session_id":"abc123","timestamp":"2026-02-27T11:56:38.526Z","path":"logs/archive/2026/02/sessions/2026-02-27_11-56-38_session_abc123.log","agent_id":"agent_001","goal":"Найти книги Пушкина","status":"completed","steps":5,"total_time_ms":7263}
{"session_id":"def456","timestamp":"2026-02-27T10:30:15.123Z","path":"logs/archive/2026/02/sessions/2026-02-27_10-30-15_session_def456.log","agent_id":"agent_001","goal":"Анализ данных","status":"completed","steps":3,"total_time_ms":4521}
```

#### agents_index.jsonl

Индекс агентов (JSONL формат):
```jsonl
{"agent_id":"agent_001","session_ids":["abc123","def456"],"first_session":"2026-02-27T10:30:15.123Z","last_session":"2026-02-27T11:56:38.526Z","total_sessions":2}
```

---

### config/

**Назначение:** Хранение конфигурации системы логирования.

**Файлы:**

#### logging_config.yaml

Основная конфигурация:
```yaml
logging:
  paths:
    base: logs
    active: logs/active
    archive: logs/archive
    index: logs/indexed

  formats:
    agent: text
    session: jsonl
    llm: jsonl
    metrics: jsonl

  retention:
    active_days: 7
    archive_months: 12
    max_size_mb: 100
    max_files_per_day: 100

  indexing:
    enabled: true
    index_sessions: true
    index_agents: true
    update_interval_sec: 60

  symlinks:
    enabled: true
    latest_session: true
    latest_agent: true
    latest_llm: true
```

---

## Доступ к файлам

### Через symlink (быстро)

```bash
# Последняя сессия
cat logs/active/sessions/latest.log

# Последний LLM лог
cat logs/active/llm/latest.jsonl
```

### Через индекс (поиск по ID)

```bash
# Найти сессию по ID
python scripts/logs/find_session.py --session-id abc123
```

### Прямой доступ (по известному пути)

```bash
# Лог агента за сегодня
cat logs/archive/2026/02/agent_2026-02-27.log

# Конкретная сессия
cat logs/archive/2026/02/sessions/2026-02-27_11-56-38_session_abc123.log
```

---

## Создание директорий

Автоматически при инициализации:

```python
from core.infrastructure.logging import init_logging_system

await init_logging_system()
# Создаёт все необходимые директории
```

Вручную:

```bash
mkdir -p logs/active/{sessions,llm}
mkdir -p logs/archive/2026/02/{sessions,llm}
mkdir -p logs/indexed
mkdir -p logs/config
```

---

## Права доступа (Linux/Mac)

```bash
# Установка прав
chmod 755 logs/
chmod 755 logs/archive/
chmod 644 logs/archive/**/*.log
chmod 644 logs/indexed/*.jsonl
```

---

## Резервное копирование

### Ежедневное backup

```bash
# Копирование архива
tar -czf logs_backup_$(date +%Y%m%d).tar.gz logs/archive/
```

### Инкрементальное backup

```bash
# Копирование только новых файлов
rsync -av --files-from=<(find logs/archive -mtime -1) logs/ backup/logs/
```
