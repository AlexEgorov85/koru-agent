# 🛠️ CLI утилиты для работы с логами

## Обзор

CLI утилиты расположены в `scripts/logs/` и предоставляют удобный доступ к системе логирования.

---

## find_latest_session.py

Найти последнюю сессию.

### Использование

```bash
python scripts/logs/find_latest_session.py
```

### Вывод

```
🔍 Поиск последней сессии...

✅ Последняя сессия найдена:
   Session ID: abc123
   Agent ID:   agent_001
   Timestamp:  2026-02-27T11:56:38.526Z
   Goal:       Найти книги Пушкина
   Status:     completed
   Steps:      5
   Total Time: 7263 ms

📁 Путь к файлу:
   logs/archive/2026/02/sessions/2026-02-27_11-56-38_session_abc123.log

📊 Записей в логе: 25
📞 LLM вызовов: 8
```

---

## find_session.py

Найти сессию по ID, агенту или goal.

### Использование

```bash
# По session_id
python scripts/logs/find_session.py --session-id abc123

# По agent_id (последняя сессия)
python scripts/logs/find_session.py --agent-id agent_001 --latest

# По agent_id (все сессии)
python scripts/logs/find_session.py --agent-id agent_001 --limit 20

# По goal
python scripts/logs/find_session.py --goal "книги" --limit 10
```

### Опции

| Опция | Описание |
|-------|----------|
| `--session-id` | ID сессии |
| `--agent-id` | ID агента |
| `--goal` | Паттерн для поиска в goal |
| `--latest` | Показать только последнюю |
| `--limit` | Максимум результатов (по умолчанию 10) |
| `--status` | Фильтр по статусу (started/completed/failed) |

---

## find_last_llm.py

Найти последний LLM вызов сессии.

### Использование

```bash
# Последний вызов
python scripts/logs/find_last_llm.py --session-id abc123

# По фазе
python scripts/logs/find_last_llm.py --session-id abc123 --phase think

# Все вызовы
python scripts/logs/find_last_llm.py --session-id abc123 --type all

# С полным текстом
python scripts/logs/find_last_llm.py --session-id abc123 --full
```

### Опции

| Опция | Описание |
|-------|----------|
| `--session-id` | ID сессии (обязательно) |
| `--phase` | Фильтр по фазе (think/act/observe) |
| `--type` | Тип (prompt/response/all) |
| `--full` | Показать полный текст промптов/ответов |

---

## cleanup_old_logs.py

Очистка старых логов.

### Использование

```bash
# Очистка логов старше 30 дней
python scripts/logs/cleanup_old_logs.py --days 30

# Dry-run (без удаления)
python scripts/logs/cleanup_old_logs.py --days 30 --dry-run

# Очистка до даты
python scripts/logs/cleanup_old_logs.py --before 2025-01-01

# Сжатие старых архивов
python scripts/logs/cleanup_old_logs.py --days 30 --compress
```

### Опции

| Опция | Описание |
|-------|----------|
| `--days` | Удалить логи старше N дней (по умолчанию 30) |
| `--before` | Удалить логи до даты (YYYY-MM-DD) |
| `--archive` | Очистить архив (старые месяцы) |
| `--dry-run` | Не удалять, только показать |
| `--compress` | Сжать старые архивы в gzip |

### Вывод

```
🧹 Очистка старых логов

⚠️  РЕЖИМ DRY-RUN: файлы не будут удалены

📊 Статистика до очистки:
   Active:  5 файлов, 12.34 MB
   Archive: 150 файлов, 256.78 MB
   Indexed: 2 файлов, 1.23 MB
   TOTAL:   270.35 MB

🗑️  Удаление логов старше 30 дней...

📊 Результаты очистки:
   Удалено файлов:     45
   Удалено размера:    85.67 MB

📊 Статистика после очистки:
   Active:  5 файлов, 12.34 MB
   Archive: 105 файлов, 171.11 MB
   Indexed: 2 файлов, 1.23 MB
   TOTAL:   184.68 MB

💾 Экономия: 85.67 MB
```

---

## check_log_size.py

Проверка размера логов.

### Использование

```bash
# Обычный вывод
python scripts/logs/check_log_size.py

# JSON вывод
python scripts/logs/check_log_size.py --json
```

### Опции

| Опция | Описание |
|-------|----------|
| `--json` | Вывод в JSON формате |

### Вывод

```
📊 Статистика использования дискового пространства

📁 Active логи (текущий день):
   Файлов: 5
   Размер: 12.34 MB

📁 Archive логи:
   Файлов: 150
   Размер: 256.78 MB

   По месяцам:
   2026/02: 50 файлов, 85.67 MB
   2026/01: 45 файлов, 78.90 MB
   2025/12: 30 файлов, 52.34 MB
   ...

📁 Indexed (индексы):
   Файлов: 2
   Размер: 1.23 MB

==================================================
💾 ОБЩИЙ РАЗМЕР: 270.35 MB
```

---

## rebuild_index.py

Перестроить индекс логов.

### Использование

```bash
# Обычное перестроение
python scripts/logs/rebuild_index.py

# Подробный вывод
python scripts/logs/rebuild_index.py --verbose
```

### Опции

| Опция | Описание |
|-------|----------|
| `--verbose` | Подробный вывод |

### Вывод

```
🔄 Перестроение индекса логов...

✅ Индекс перестроен!
   Сессий проиндексировано: 250
   Агентов проиндексировано: 15
   Время выполнения: 2.34 сек

📊 Детали:
   Sessions index: 250 записей
   Agents index:   15 записей

📁 Последняя сессия:
   ID:        abc123
   Agent:     agent_001
   Timestamp: 2026-02-27T11:56:38.526Z
   Goal:      Найти книги Пушкина
```

---

## export_session.py

Экспорт сессии в JSON или текст.

### Использование

```bash
# Экспорт в JSON
python scripts/logs/export_session.py --session-id abc123

# С указанием пути
python scripts/logs/export_session.py --session-id abc123 --output session.json

# Текстовый формат
python scripts/logs/export_session.py --session-id abc123 --format text

# С LLM вызовами
python scripts/logs/export_session.py --session-id abc123 --include-llm
```

### Опции

| Опция | Описание |
|-------|----------|
| `--session-id` | ID сессии (обязательно) |
| `--output` | Путь для экспорта |
| `--format` | Формат (json/text) |
| `--include-llm` | Включить LLM вызовы |

### Вывод

```
📤 Экспорт сессии: abc123

✅ Сессия найдена:
   Agent:     agent_001
   Timestamp: 2026-02-27T11:56:38.526Z
   Goal:      Найти книги Пушкина
   Status:    completed

📊 Записей в логе: 25
📞 LLM вызовов: 8

💾 Экспорт в session_abc123_export.json...
✅ Экспорт завершён!
   Файл: /path/to/session_abc123_export.json
   Размер: 15234 байт
```

---

## Автоматизация

### Cron задачи (Linux/Mac)

```bash
# Очистка старых логов каждый день в 3 часа
0 3 * * * cd /path/to/Agent_v5 && python scripts/logs/cleanup_old_logs.py --days 30

# Перестроение индекса каждый час
0 * * * * cd /path/to/Agent_v5 && python scripts/logs/rebuild_index.py

# Проверка размера логов каждый день в 8 утра
0 8 * * * cd /path/to/Agent_v5 && python scripts/logs/check_log_size.py >> /var/log/agent_log_size.log
```

### Планировщик задач (Windows)

```powershell
# Создание задачи на очистку логов
$action = New-ScheduledTaskAction -Execute "python" `
    -Argument "scripts/logs/cleanup_old_logs.py --days 30" `
    -WorkingDirectory "C:\path\to\Agent_v5"

$trigger = New-ScheduledTaskTrigger -Daily -At 3am

Register-ScheduledTask -TaskName "Agent Logs Cleanup" `
    -Action $action -Trigger $trigger -User "username"
```

---

## Скрипты для разработки

### Найти все сессии с ошибками

```bash
python scripts/logs/find_session.py --status failed --limit 100
```

### Экспорт всех сессий агента

```bash
for session_id in $(python scripts/logs/find_session.py --agent-id agent_001 --limit 100 | grep "Session ID" | cut -d: -f2); do
    python scripts/logs/export_session.py --session-id $session_id --output "exports/session_${session_id}.json"
done
```

### Найти сессии по дате

```bash
python scripts/logs/find_session.py --date-from 2026-02-01 --date-to 2026-02-28 --limit 50
```
