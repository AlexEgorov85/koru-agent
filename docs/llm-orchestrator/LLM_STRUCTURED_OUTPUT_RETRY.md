# Структурированный вывод с повторными попытками

## Обзор

`LLMOrchestrator` реализует централизованную логику получения валидных структурированных ответов от LLM с автоматическими повторными попытками при ошибках.

## Архитектура

### Цикл повторных попыток (Retry Loop)

```
┌─────────────────────────────────────────────────────────────┐
│              execute_structured()                            │
│                                                              │
│  1. Первичный запрос с JSON схемой                          │
│     │                                                        │
│     ▼                                                        │
│  2. Выполнение попытки (_execute_structured_attempt)         │
│     │                                                        │
│     ▼                                                        │
│  3. Валидация (_validate_structured_response)                │
│     │                                                        │
│     ├─► Успех ──────► Возврат StructuredLLMResponse         │
│     │                                                        │
│     └─► Ошибка                                              │
│          │                                                   │
│          ▼                                                   │
│  4. Формирование corrective prompt                           │
│     (_build_corrective_prompt)                               │
│     │                                                        │
│     ▼                                                        │
│  5. Если attempts < max_retries ──► Шаг 2                   │
│     │                                                        │
│     └─► Иначе ──────► Возврат ошибки с историей             │
└─────────────────────────────────────────────────────────────┘
```

## Типы ошибок

### 1. JSON парсинг (`json_error`)
- Невалидный JSON синтаксис
- Отсутствие закрывающих скобок
- Неправильные кавычки

### 2. Валидация схемы (`validation_error`)
- Отсутствуют обязательные поля
- Неверные типы данных
- Несоответствие формату

### 3. Неполный ответ (`incomplete`)
- Ответ обрезан из-за `max_tokens`
- Отсутствует закрывающая скобка `}`
- Эвристика по длине ответа

### 4. Таймаут (`timeout`)
- Превышение времени на попытку
- LLM не ответил вовремя

### 5. Ошибка LLM (`llm_error`)
- Провайдер вернул ошибку
- Модель недоступна

## Corrective Prompt

При ошибке формируется новый промпт с обратной связью:

```
{исходный запрос}

---
ПРЕДЫДУЩАЯ ПОПЫТКА НЕ УДАЛАСЬ
---

Ошибка: {описание ошибки}

Ваш ответ: {неудачный ответ}

---
ИНСТРУКЦИЯ
---
Пожалуйста, исправьте ответ и верните ТОЛЬКО валидный JSON,
соответствующий ожидаемой схеме.
Не добавляйте никаких пояснений, только JSON.
```

### Адаптация параметров

Для повторной попытки:
- `temperature` снижается до `0.1` (для точности)
- `max_tokens` увеличивается в 1.5 раза (до 2000)
- Сохраняется оригинальная схема

## Пример использования

```python
from core.models.types.llm_types import LLMRequest, StructuredOutputConfig
from core.infrastructure.providers.llm.llm_orchestrator import LLMOrchestrator

# Создание оркестратора
orchestrator = LLMOrchestrator(event_bus=event_bus)
await orchestrator.initialize()

# Запрос со структурированным выводом
request = LLMRequest(
    prompt="Проанализируй книгу и верни оценку",
    system_prompt="Ты — литературный критик",
    temperature=0.7,
    max_tokens=500,
    structured_output=StructuredOutputConfig(
        output_model="BookReview",
        schema_def={
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "rating": {"type": "integer", "minimum": 1, "maximum": 5},
                "summary": {"type": "string"}
            },
            "required": ["title", "rating", "summary"]
        },
        max_retries=3
    )
)

# Выполнение с повторными попытками
response = await orchestrator.execute_structured(
    request=request,
    provider=llm_provider,
    max_retries=3,
    attempt_timeout=60.0,      # 60с на попытку
    total_timeout=300.0,       # 5мин на всё
    session_id="session_123",
    agent_id="agent_001",
    step_number=5,
    phase="think"
)

# Проверка результата
if response.success:
    print(f"Успех с {response.parsing_attempts} попытки")
    print(f"Ответ: {response.parsed_content}")
else:
    print(f"Неудача после {response.parsing_attempts} попыток")
    for error in response.validation_errors:
        print(f"  Попытка {error['attempt']}: {error['error']} - {error['message']}")
```

## Логирование

### Начало структурированного вызова
```
📋 Structured LLM | call_id=llm_123 | session=session_abc | max_retries=3 | schema=BookReview
```

### Успешная попытка
```
✅ Structured SUCCESS | call_id=llm_123 | session=session_abc | attempt=2 | duration=3.45s
```

### Неудачная попытка (с повтором)
```
🔄 Structured RETRY | call_id=llm_123 | attempt=1 | error=json_error | message=JSON парсинг не удался | will_retry=True
```

### Неудачная попытка (последняя)
```
⚠️ Structured RETRY | call_id=llm_123 | attempt=3 | error=validation_error | message=Отсутствует поле rating | will_retry=False
```

### Исчерпание попыток
```
❌ Structured EXHAUSTED | call_id=llm_123 | session=session_abc | total_attempts=3 | last_error=Отсутствует поле rating
```

## Метрики

```python
metrics = orchestrator.get_metrics()
print(metrics.to_dict())

# Пример:
{
    "structured_calls": 100,
    "structured_success": 92,
    "structured_success_rate": 0.92,
    "total_retry_attempts": 115,
    "avg_retries_per_call": 1.15
}
```

### Интерпретация метрик

- **structured_success_rate < 0.8**: Низкий процент успеха — проверить промпты или схему
- **avg_retries_per_call > 2.0**: Много повторных попыток — упростить схему или увеличить max_tokens
- **total_retry_attempts >> structured_calls**: Система работает, но требует оптимизации

## Обработка обрезанных ответов

Если ответ обрезан (`incomplete`):

1. **Эвристика**: Проверка на закрывающую `}`
2. **Действие**: Увеличение `max_tokens` в 1.5 раза
3. **Повтор**: Запрос полного ответа заново

### Пример
```
Попытка 1: max_tokens=500 → Ответ обрезан на 480 токенах
Попытка 2: max_tokens=750 → Полный ответ
```

## Настройка стратегии

### Консервативная (быстрая)
```python
response = await orchestrator.execute_structured(
    request=request,
    max_retries=1,              # Только одна попытка
    attempt_timeout=30.0        # 30с на попытку
)
```

### Стандартная (рекомендуемая)
```python
response = await orchestrator.execute_structured(
    request=request,
    max_retries=3,              # До 3 попыток
    attempt_timeout=60.0,       # 60с на попытку
    total_timeout=300.0         # 5мин всего
)
```

### Агрессивная (максимальное качество)
```python
response = await orchestrator.execute_structured(
    request=request,
    max_retries=5,              # До 5 попыток
    attempt_timeout=90.0,       # 90с на попытку
    total_timeout=600.0         # 10мин всего
)
```

## Преимущества

### 1. Единообразие
Все паттерны получают одинаковый механизм структурированного вывода.

### 2. Улучшение качества
Обратная связь позволяет LLM исправлять ошибки.

### 3. Прозрачность
Детальное логирование каждой попытки.

### 4. Гибкость
Настройка стратегии в одном месте.

### 5. Надёжность
Агент не падает при ошибках парсинга — получает структурированную ошибку.

## Рекомендации

### 1. Выбор max_retries
- Для простых схем: 1-2 попытки
- Для сложных схем: 3-5 попыток
- Максимум: 5 (дальше малоэффективно)

### 2. Настройка timeout
- attempt_timeout: 30-90с в зависимости от сложности
- total_timeout: attempt_timeout × max_retries × 1.5

### 3. Проектирование схем
- Минимизировать обязательные поля
- Использовать простые типы (string, integer, boolean)
- Избегать вложенных структур

### 4. Мониторинг
```python
if metrics.structured_success_rate < 0.8:
    logger.warning("Низкий процент успеха структурированных вызовов")
if metrics.avg_retries_per_call > 2.0:
    logger.warning("Много повторных попыток — проверить схемы")
```

## Заключение

Централизованная логика повторных попыток в `LLMOrchestrator`:
- ✅ Решает проблему "потерянных" ответов
- ✅ Повышает качество структурированного вывода
- ✅ Устраняет дублирование кода в паттернах
- ✅ Соответствует принципам чистой архитектуры
