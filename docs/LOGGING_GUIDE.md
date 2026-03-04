# 📋 Руководство по логам

> **Версия:** 5.29.0
> **Дата обновления:** 2026-03-04
> **Статус:** approved

## Структура логов

```
logs/
├── sessions/                    ← Логи по сессиям
│   └── YYYY-MM-DD_HH-MM-SS/     ← Дата и время старта агента
│       ├── common.log           ← Все общие логи (JSONL)
│       ├── llm.jsonl            ← LLM промпты и ответы
│       └── metrics.jsonl        ← Метрики выполнения
│
├── by_capability/               ← Логи по компонентам
│   └── {capability_name}/
│       └── logs.json
│
└── by_agent/                    ← Логи по агентам
    └── {agent_id}/
        └── logs.json
```

## Где какие логи искать

### 1. **Логи последней сессии**
```
logs/sessions/2026-03-04_14-30-15/
├── common.log      ← Обычные логи (INFO, DEBUG, WARNING, ERROR)
├── llm.jsonl       ← Промпты и ответы LLM
└── metrics.jsonl   ← Метрики (время, токены, успех)
```

**Как найти:**
- Откройте `logs/sessions/`
- Выберите папку с последней датой/временем
- Откройте `common.log` для общих логов

### 2. **LLM промпты и ответы**
```
logs/sessions/2026-03-04_14-30-15/llm.jsonl
```

**Формат записи:**
```json
{
  "timestamp": "2026-03-04T14:30:15.123456",
  "event_type": "llm.prompt.generated",
  "component": "react_pattern",
  "phase": "think",
  "system_prompt": "...",
  "user_prompt": "...",
  "prompt_length": 1234,
  "temperature": 0.7
}
```

### 3. **Метрики выполнения**
```
logs/sessions/2026-03-04_14-30-15/metrics.jsonl
```

**Формат записи:**
```json
{
  "timestamp": "2026-03-04T14:30:15.123456",
  "event_type": "metric.collected",
  "agent_id": "agent_001",
  "capability": "final_answer.generate",
  "metric_type": "gauge",
  "name": "success",
  "value": 1.0,
  "execution_time_ms": 234.5
}
```

### 4. **Логи по компоненту**
```
data/logs/by_capability/react_pattern/logs.json
```

**Зачем:** Анализ работы конкретного компонента across all sessions.

### 5. **Логи по агенту**
```
data/logs/by_agent/{agent_id}/{session_id}/logs.json
```

**Зачем:** Отладка конкретного агента.

---

## Форматы файлов

### `.log` (JSONL)
Каждая строка — отдельный JSON объект:
```json
{"timestamp": "...", "event_type": "log.info", "message": "...", "level": "INFO"}
{"timestamp": "...", "event_type": "log.error", "message": "...", "level": "ERROR"}
```

### `.jsonl` (JSON Lines)
То же что `.log`, но для специфичных данных (LLM, metrics).

---

## Примеры использования

### 1. Найти все LLM промпты за сессию
```bash
cat logs/sessions/2026-03-04_14-30-15/llm.jsonl | grep "llm.prompt.generated"
```

### 2. Посмотреть ошибки сессии
```bash
cat logs/sessions/2026-03-04_14-30-15/common.log | grep '"level": "ERROR"'
```

### 3. Найти метрики успеха
```bash
cat logs/sessions/2026-03-04_14-30-15/metrics.jsonl | grep '"name": "success"'
```

### 4. Python: прочитать логи
```python
import json
from pathlib import Path

log_file = Path("logs/sessions/2026-03-04_14-30-15/common.log")

with open(log_file) as f:
    for line in f:
        event = json.loads(line)
        print(f"{event['timestamp']}: {event['message']}")
```

---

## Отличия от старой структуры

### ❌ БЫЛО (плохо):
```
logs/sessions/
├── {session_id}/           ← UUID (непонятно когда)
│   └── common.log
└── {session_id}_system/    ← ДУБЛИРОВАНИЕ!
    └── common.log
```

**Проблемы:**
- 2 папки на сессию (дублирование)
- UUID вместо даты (непонятно когда)
- LLM логи отдельно в `data/logs/`

### ✅ СТАЛО (хорошо):
```
logs/sessions/
└── 2026-03-04_14-30-15/    ← Дата и время!
    ├── common.log
    ├── llm.jsonl           ← LLM логи ЗДЕСЬ
    └── metrics.jsonl       ← Метрики ЗДЕСЬ
```

**Преимущества:**
- 1 папка на сессию
- Понятное имя (дата+время)
- Все логи в одном месте
- LLM и метрики легко найти

---

## API для работы с логами

### Создание обработчика
```python
from core.infrastructure.logging import create_session_log_handler

handler = create_session_log_handler(
    event_bus=event_bus,
    session_id="my_session",
    agent_id="agent_001"
)

info = handler.get_session_info()
print(f"Логи в: {info['session_folder']}")
```

### Чтение логов
```python
from pathlib import Path
import json

def read_session_logs(session_folder: str):
    logs_path = Path(f"logs/sessions/{session_folder}")
    
    # Общие логи
    with open(logs_path / "common.log") as f:
        common_logs = [json.loads(line) for line in f]
    
    # LLM логи
    with open(logs_path / "llm.jsonl") as f:
        llm_logs = [json.loads(line) for line in f]
    
    return common_logs, llm_logs
```

---

## Настройка уровня логирования

```python
from core.infrastructure.logging import set_terminal_level, set_file_level, LogLevel

# Терминал: только WARNING и выше
set_terminal_level(LogLevel.WARNING)

# Файл: все логи включая DEBUG
set_file_level(LogLevel.DEBUG)

# Включить DEBUG режим
enable_debug_mode()
```

---

## Частые вопросы

### ❓ Где логи промтов и ответов LLM?
**Ответ:** `logs/sessions/{дата_время}/llm.jsonl`

### ❓ Почему 2 папки на сессию?
**Ответ:** Теперь 1 папка! Старая структура упразднена.

### ❓ Как найти логи по имени агента?
**Ответ:** `data/logs/by_agent/{agent_id}/logs.json`

### ❓ Можно ли писать логи в консоль?
**Ответ:** Да, TerminalLogHandler выводит в консоль автоматически.

### ❓ Как отключить логирование?
**Ответ:** 
```python
from core.infrastructure.logging import LoggingConfig, LogLevel

config = LoggingConfig(
    terminal=TerminalOutputConfig(enabled=False),
    file=FileOutputConfig(enabled=False)
)
```
