# Расширенное логирование LLM вызовов

## Обзор

С введением `LLMOrchestrator` система логирования была значительно расширена для обеспечения полной прозрачности и возможности отладки всех вызовов LLM.

## Ключевые возможности

### 1. Централизованное логирование всех вызовов

`LLMOrchestrator` является единой точкой для всех LLM вызовов. Каждый вызов логируется с:

- **Уникальный correlation_id** - генерируется для каждого вызова
- **Входные данные** - промпт, параметры генерации, схема вывода
- **Контекст выполнения** - session_id, agent_id, step_number, phase
- **Результат** - успех/ошибка/таймаут, длительность, токены
- **Метрики** - время выполнения, статус, количество попыток

### 2. Структура CallRecord

```python
@dataclass
class CallRecord:
    """Запись об активном LLM вызове с полным контекстом."""
    call_id: str                          # Уникальный ID
    request: LLMRequest                   # Запрос
    status: CallStatus                    # Статус выполнения
    start_time: Optional[float]           # Время начала
    end_time: Optional[float]             # Время окончания
    timeout: Optional[float]              # Таймаут
    
    # Контекст для трассировки
    session_id: Optional[str]             # ID сессии
    agent_id: Optional[str]               # ID агента
    step_number: Optional[int]            # Номер шага
    phase: Optional[str]                  # "think", "act"
    goal: Optional[str]                   # Цель
```

### 3. События EventBus

#### LLM_PROMPT_GENERATED

Публикуется при начале вызова:

```python
{
    "call_id": "llm_1234567890_1",
    "session_id": "session_abc",
    "agent_id": "agent_001",
    "step_number": 5,
    "phase": "think",
    "goal": "Какие книги написал Пушкин?",
    "capability_name": "react_pattern.think",
    "prompt_length": 2500,
    "temperature": 0.3,
    "max_tokens": 1000,
    "timeout": 120.0
}
```

#### LLM_RESPONSE_RECEIVED

Публикуется при завершении вызова (успех или ошибка):

```python
# Успешный вызов
{
    "call_id": "llm_1234567890_1",
    "session_id": "session_abc",
    "agent_id": "agent_001",
    "step_number": 5,
    "phase": "think",
    "success": True,
    "duration_ms": 3450.5,
    "capability_name": "react_pattern.think",
    "response_length": 850,
    "tokens_used": 320,
    "model": "llama-model"
}

# Таймаут
{
    "call_id": "llm_1234567890_1",
    "session_id": "session_abc",
    "agent_id": "agent_001",
    "step_number": 5,
    "phase": "think",
    "success": False,
    "duration_ms": 120000.0,
    "capability_name": "react_pattern.think",
    "error_type": "timeout",
    "error_message": "LLM timeout после 120.00с (лимит: 120.0с)"
}

# Поздний ответ (после таймаута)
{
    "call_id": "llm_1234567890_1",
    "session_id": "session_abc",
    "agent_id": "agent_001",
    "step_number": 5,
    "phase": "think",
    "late_response": True,
    "duration_ms": 145000.0,
    "capability_name": "react_pattern.think",
    "orphaned": True
}
```

### 4. Формат логов

#### Начало вызова
```
🧩 LLM вызов | call_id=llm_1234567890_1 | session=session_abc | agent=agent_001 | step=5 | phase=think | prompt_len=2500 | timeout=120s
```

#### Успешное завершение
```
✅ LLM ответ | call_id=llm_1234567890_1 | session=session_abc | step=5 | response_len=850 | tokens=320 | duration=3.45s
```

#### Таймаут
```
⏰ LLM TIMEOUT | call_id=llm_1234567890_1 | session=session_abc | agent=agent_001 | step=5 | phase=think | elapsed=120.00s | timeout=120s | prompt_len=2500
```

#### Ошибка
```
❌ LLM ERROR | call_id=llm_1234567890_1 | session=session_abc | step=5 | ValueError: Model not loaded | elapsed=0.05s
```

#### "Брошенный" вызов
```
🗑️ ORPHANED CALL | call_id=llm_1234567890_1 | завершился через 145.00с после таймаута | session=session_abc | step=5 | capability=react_pattern.think
```

### 5. Интеграция с ReActPattern

```python
# В ReActPattern._perform_structured_reasoning():

response = await orchestrator.execute(
    request=llm_request,
    timeout=llm_timeout,
    provider=llm_provider,
    # Контекст для трассировки
    session_id=session_context.session_id,
    agent_id=session_context.agent_id,
    step_number=session_context.current_step,
    phase="think",
    goal=session_context.get_goal()
)
```

### 6. Метрики для мониторинга

```python
metrics = orchestrator.get_metrics()
print(metrics.to_dict())

# Результат:
{
    "total_calls": 150,
    "completed_calls": 142,
    "timed_out_calls": 5,
    "failed_calls": 3,
    "orphaned_calls": 2,
    "avg_generation_time": 4.35,
    "timeout_rate": 0.033,
    "orphan_rate": 0.013
}
```

### 7. Health Status

```python
status = orchestrator.get_health_status()
print(status)

# Результат:
{
    "status": "healthy",  # или "degraded", "unhealthy"
    "executor_running": True,
    "pending_calls": 2,
    "metrics": { ... },
    "recent_calls": [ ... ]
}
```

### 8. Асинхронность и производительность

Все операции логирования асинхронные и не блокируют выполнение:

- Публикация событий через `EventBus` (асинхронная очередь)
- Логирование через `EventBusLogger` (не блокирует основной поток)
- Метрики обновляются в памяти (без I/O операций)

### 9. Отладка проблем

#### Поиск медленных вызовов
```python
# В логах ищем:
"duration=" > 10s

# Или через метрики:
if metrics.avg_generation_time > 5.0:
    logger.warning("Среднее время генерации превышено")
```

#### Анализ таймаутов
```python
# В логах ищем:
"⏰ LLM TIMEOUT"

# Или через метрики:
if metrics.timeout_rate > 0.1:  # > 10%
    logger.error("Высокий процент таймаутов")
```

#### Отслеживание "брошенных" вызовов
```python
# В логах ищем:
"🗑️ ORPHANED CALL"

# Или через метрики:
if metrics.orphan_rate > 0.05:  # > 5%
    logger.warning("Много брошенных вызовов - увеличить таймаут")
```

### 10. Корреляция с сессией агента

Благодаря полям `session_id`, `agent_id`, `step_number`, `phase` можно:

1. **Восстановить полную историю вызовов** для конкретной сессии
2. **Анализировать производительность** по шагам агента
3. **Находить проблемные места** (какие шаги вызывают таймауты)
4. **Оптимизировать промпты** (анализ prompt_length vs duration)

### 11. Пример анализа сессии

```
Сессия: session_abc
Агент: agent_001
Цель: "Какие книги написал Пушкин?"

Шаг 1 (think):
  🧩 LLM вызов | call_id=llm_1_1 | prompt_len=2500 | timeout=120s
  ✅ LLM ответ | duration=3.45s | tokens=320

Шаг 2 (act - book_library.search_books):
  🧩 LLM вызов | call_id=llm_1_2 | prompt_len=1800 | timeout=120s
  ✅ LLM ответ | duration=2.10s | tokens=150

Шаг 3 (think):
  🧩 LLM вызов | call_id=llm_1_3 | prompt_len=3200 | timeout=120s
  ⏰ LLM TIMEOUT | elapsed=120.00s
  🗑️ ORPHANED CALL | завершился через 145.00с после таймаута

Итого:
  - Вызовов: 3
  - Успешных: 2
  - Таймаутов: 1
  - Брошенных: 1
```

## Рекомендации по использованию

### 1. Всегда передавайте контекст

```python
# ✅ Правильно
await orchestrator.execute(
    request=request,
    session_id=session_id,
    agent_id=agent_id,
    step_number=step,
    phase="think"
)

# ❌ Неправильно (теряется трассировка)
await orchestrator.execute(request=request)
```

### 2. Настраивайте таймауты разумно

```python
# Для быстрых запросов
timeout=30.0

# Для сложных рассуждений
timeout=120.0

# Для анализа больших контекстов
timeout=300.0
```

### 3. Мониторьте метрики

```python
# В цикле мониторинга
metrics = orchestrator.get_metrics()
if metrics.timeout_rate > 0.1:
    # Увеличить таймаут или уменьшить нагрузку
    logger.warning("Высокий процент таймаутов")
```

### 4. Анализируйте "брошенные" вызовы

```python
# Если много orphaned calls
if metrics.orphan_rate > 0.05:
    # Увеличить таймаут
    # или оптимизировать промпты
    # или уменьшить max_tokens
```

## Заключение

Расширенное логирование в `LLMOrchestrator` обеспечивает:

- ✅ Полную наблюдаемость всех LLM вызовов
- ✅ Трассировку по сессиям и шагам агента
- ✅ Быструю отладку проблем с производительностью
- ✅ Метрики для проактивного мониторинга
- ✅ Интеграцию с существующей системой событий

Это делает систему устойчивой к таймаутам и предоставляет все необходимые инструменты для анализа и оптимизации работы с LLM.
