# 🗓️ Политика хранения логов

## Обзор

Политика хранения определяет правила ротации, архивации и удаления логов.

---

## Уровни хранения

### 1. Active (активные логи)

**Расположение:** `logs/active/`

**Назначение:** Логи текущего дня для быстрого доступа.

**Политика:**
- Хранятся **7 дней** (настраивается через `retention.active_days`)
- Максимальный размер файла: **100 MB**
- Максимум файлов в день: **100**

**Автоматические действия:**
- Ротация при превышении размера
- Перемещение в archive в конце дня

---

### 2. Archive (архив)

**Расположение:** `logs/archive/YYYY/MM/`

**Назначение:** Долгосрочное хранение логов.

**Политика:**
- Хранятся **12 месяцев** (настраивается через `retention.archive_months`)
- Организация по годам и месяцам
- Сжатие старых файлов в gzip (опционально)

**Структура:**
```
archive/
├── 2026/
│   ├── 02/
│   │   ├── agent_2026-02-27.log
│   │   ├── sessions/
│   │   │   └── 2026-02-27_11-56-38_session_abc123.log
│   │   └── llm/
│   │       └── 2026-02-27_session_abc123.jsonl
│   └── 01/
└── 2025/
```

---

### 3. Indexed (индексы)

**Расположение:** `logs/indexed/`

**Назначение:** Быстрый поиск по логам.

**Файлы:**
- `sessions_index.jsonl` — индекс сессий
- `agents_index.jsonl` — индекс агентов

**Политика:**
- Не удаляются (перестраиваются при необходимости)
- Автоматическое обновление каждые 60 секунд

---

## Настройка

### Конфигурация через YAML

**Файл:** `logs/config/logging_config.yaml`

```yaml
logging:
  # Политика хранения
  retention:
    active_days: 7          # Дней в active/
    archive_months: 12      # Месяцев в archive/
    max_size_mb: 100        # Макс размер файла
    max_files_per_day: 100  # Макс файлов в день
  
  # Индексация
  indexing:
    enabled: true
    index_sessions: true
    index_agents: true
    update_interval_sec: 60
  
  # Symlinks
  symlinks:
    enabled: true
    latest_session: true
    latest_agent: true
    latest_llm: true
```

### Программная настройка

```python
from core.infrastructure.logging import LoggingConfig, configure_logging

config = LoggingConfig(
    retention=RetentionConfig(
        active_days=7,
        archive_months=12,
        max_size_mb=100,
        max_files_per_day=100,
    ),
    indexing=IndexingConfig(
        enabled=True,
        update_interval_sec=60,
    ),
)

configure_logging(config)
```

---

## Автоматическая очистка

### Фоновая задача

LogRotator автоматически запускает очистку:
- **Проверка размера:** каждый час
- **Очистка старых логов:** раз в сутки в 3:00

### Ручная очистка

```bash
# Очистка логов старше 30 дней
python scripts/logs/cleanup_old_logs.py --days 30

# Dry-run (без удаления)
python scripts/logs/cleanup_old_logs.py --days 30 --dry-run

# Очистка до даты
python scripts/logs/cleanup_old_logs.py --before 2025-01-01
```

---

## Сжатие архивов

### Автоматическое сжатие

Файлы старше 30 дней могут быть сжаты в gzip:

```python
from core.infrastructure.logging import get_log_rotator

rotator = get_log_rotator()
compressed = await rotator.compress_old_archives(older_than_days=30)
```

### Ручное сжатие

```bash
python scripts/logs/cleanup_old_logs.py --days 30 --compress
```

---

## Мониторинг

### Проверка размера

```bash
python scripts/logs/check_log_size.py
```

### Метрики

| Метрика | Порог | Действие |
|---------|-------|----------|
| daily_log_size_mb | > 500 | Предупреждение |
| archive_size_mb | > 10000 | Очистка старых месяцев |
| index_age_hours | > 1 | Перестроение индекса |

---

## Рекомендации

### Для разработки

```yaml
retention:
  active_days: 3
  archive_months: 1
  max_size_mb: 50
```

### Для продакшена

```yaml
retention:
  active_days: 14
  archive_months: 24
  max_size_mb: 200
```

### Для отладки

```yaml
retention:
  active_days: 30
  archive_months: 6
  max_size_mb: 500
```

---

## Алгоритм очистки

```
1. Получить текущую дату
2. Вычислить cutoff_date = now - retention.active_days
3. Для каждого файла в active/:
   - Если mtime < cutoff_date → удалить
4. Для каждой директории в archive/YYYY/MM/:
   - Если дата месяца < now - retention.archive_months → удалить директорию
5. Обновить индексы
```

---

## Восстановление после очистки

### Из backup

Если логи были удалены ошибочно:
1. Остановить агента
2. Восстановить файлы из backup
3. Перестроить индекс: `python scripts/logs/rebuild_index.py`

### Из внешних систем

Если настроена отправка логов во внешнюю систему (ELK, Splunk):
1. Запросить логи из внешней системы
2. Экспортировать в JSON
3. Импортировать в локальную систему
