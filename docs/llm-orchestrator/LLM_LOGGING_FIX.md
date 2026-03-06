# Исправление логирования LLM промтов и ответов

## Дата: 2026-03-05

## Проблема

Промты и ответы от LLM перестали сохраняться в логи после внедрения `LLMOrchestrator`.

## Корневая причина

В системе существовали **два независимых механизма** логирования LLM вызовов:

### 1. LLMOrchestrator (новый механизм)
- Публикует события `LLM_PROMPT_GENERATED` и `LLM_RESPONSE_RECEIVED`
- **ПРОБЛЕМА:** В событиях отсутствовало содержимое промпта и ответа!
- Сохранялись только метаданные: `prompt_length`, `response_length`, `tokens_used`

### 2. BaseLLMProvider (старый механизм)
- Также публикует события `LLM_PROMPT_GENERATED` и `LLM_RESPONSE_RECEIVED`
- Содержит `system_prompt`, `user_prompt`, `response`
- **НО:** Используется только при прямом вызове `llm_provider.generate_structured()`

### Конфликт
Когда `ReActPattern` использует `LLMOrchestrator.execute_structured()`:
1. `LLMOrchestrator` публиковал события **без содержимого**
2. `SessionLogHandler` получал эти события и записывал **пустые логи**
3. `BaseLLMProvider._publish_prompt_event()` **НЕ вызывался**

## Внесённые изменения

### 1. core/infrastructure/providers/llm/llm_orchestrator.py

#### `_publish_prompt_event()` - добавлено сохранение содержимого промпта:
```python
# БЫЛО:
data={
    "prompt_length": len(record.request.prompt),
    ...
}

# СТАЛО:
data={
    "system_prompt": record.request.system_prompt or "",  # ← ДОБАВЛЕНО
    "user_prompt": record.request.prompt,                  # ← ДОБАВЛЕНО
    "prompt_length": len(record.request.prompt),
    ...
}
```

#### `_publish_response_event()` - добавлено сохранение содержимого ответа:
```python
# БЫЛО:
data={
    "response_length": len(result.content) if result.content else 0,
    ...
}

# СТАЛО:
response_content = result.content or ""
data={
    "response": response_content,                          # ← ДОБАВЛЕНО
    "response_length": len(response_content),
    ...
}
```

#### `_publish_late_response_event()` - добавлено сохранение для поздних ответов:
```python
# БЫЛО:
data={
    "late_response": True,
    "orphaned": True
}

# СТАЛО:
response_content = record.result.content or ""
data={
    "late_response": True,
    "orphaned": True,
    "response": response_content,                          # ← ДОБАВЛЕНО
    "response_length": len(response_content)               # ← ДОБАВЛЕНО
}
```

### 2. core/infrastructure/event_bus/llm_event_subscriber.py

#### Проблема несоответствия имён полей
`LLMOrchestrator` использует `capability_name`, а `LLMEventSubscriber` ожидал `component`.

#### `_on_llm_prompt_generated()` - поддержка обоих форматов:
```python
# БЫЛО:
component = data.get('component', 'unknown')

# СТАЛО:
component = data.get('capability_name', data.get('component', 'unknown'))

# Также улучшена обработка промптов:
system_prompt = data.get('system_prompt', '')
user_prompt = data.get('user_prompt', '')
if system_prompt:
    await self.event_bus_logger.debug(f"System prompt: {system_prompt[:500]}")
if user_prompt:
    await self.event_bus_logger.debug(f"User prompt: {user_prompt[:500]}")
```

#### `_on_llm_response_received()` - улучшенное логирование:
```python
# БЫЛО:
response = data.get('response', {})
response_str = str(response)[:200]
await self.event_bus_logger.info(f"[LLM] Response #{self._response_count} | {component}/{phase}")

# СТАЛО:
response = data.get('response', '')
response_str = response[:500]  # Увеличено с 200 до 500 символов

success = data.get('success', 'unknown')
duration_ms = data.get('duration_ms', 0)
tokens = data.get('tokens_used', 0)

await self.event_bus_logger.info(
    f"[LLM] Response #{self._response_count} | {component}/{phase} | "
    f"success={success} | duration={duration_ms:.1f}ms | tokens={tokens}"
)
```

## Результат

Теперь при использовании `LLMOrchestrator.execute_structured()`:

✅ **Промты сохраняются полностью:**
- `system_prompt` - системный промпт
- `user_prompt` - пользовательский промпт
- `prompt_length` - длина промпта

✅ **Ответы сохраняются в ТРЁХ форматах:**
- `raw_response` - **сырой JSON** (строка от LLM, для отладки парсинга)
- `parsed_response` - **распарсенный JSON** (объект, для удобного чтения)
- `response_preview` - **форматированный preview** (800 символов, для быстрого просмотра)
- `response_length` - длина ответа
- `tokens_used` - количество токенов
- `model` - используемая модель

✅ **Метрики сохраняются:**
- `duration_ms` - время выполнения
- `success` - статус выполнения
- `error_type`, `error_message` - информация об ошибках

## Структура логов

Логи сохраняются в:
```
logs/sessions/YYYY-MM-DD_HH-MM-SS/
├── session.log    ← Общие логи сессии
├── llm.jsonl      ← LLM промпты/ответы (теперь с содержимым!)
└── metrics.jsonl  ← Метрики
```

## Пример записи в llm.jsonl

```jsonl
{"timestamp": "2026-03-05T12:34:56.789", "event_type": "llm.prompt.generated", "source": "LLMOrchestrator", "level": "INFO", "session_id": "session_123", "agent_id": "agent_001", "call_id": "llm_1234567890_1", "capability_name": "react_pattern.think", "system_prompt": "Ты — модуль рассуждения ReAct...", "user_prompt": "ЦЕЛЬ: Какие книги написал Пушкин?...", "prompt_length": 6024, "temperature": 0.3, "max_tokens": 1000, "timeout": 120.0}

{"timestamp": "2026-03-05T12:34:59.123", "event_type": "llm.response.received", "source": "LLMOrchestrator", "level": "INFO", "session_id": "session_123", "agent_id": "agent_001", "call_id": "llm_1234567890_1", "capability_name": "react_pattern.think", "success": true, "duration_ms": 2340.5, "raw_response": "{\"thought\": \"...\", \"decision\": {...}}", "parsed_response": {"thought": "...", "decision": {"next_action": "book_library.search_books", "reasoning": "...", "parameters": {...}}}, "response_preview": "{\n  \"thought\": \"...\",\n  \"decision\": {\n    \"next_action\": \"book_library.search_books\",\n    ...", "response_length": 850, "tokens_used": 320, "model": "llama-3.1-8b"}
```

## Форматы ответа

| Поле | Тип | Описание | Когда использовать |
|------|-----|----------|-------------------|
| `raw_response` | строка | Сырой JSON от LLM | Отладка парсинга, проверка форматирования |
| `parsed_response` | объект | Распарсенный JSON | Чтение, анализ, поиск по структуре |
| `response_preview` | строка | Форматированный preview (800 симв.) | Быстрый просмотр в консоли |

## Тестирование

1. Запустите агента: `python main.py`
2. Проверьте логи в `logs/sessions/YYYY-MM-DD_HH-MM-SS/llm.jsonl`
3. Убедитесь что `system_prompt`, `user_prompt` и `response` заполнены

## Обратная совместимость

Изменения полностью обратно совместимы:
- `BaseLLMProvider` продолжает работать как раньше
- `LLMEventSubscriber` поддерживает оба формата событий
- `SessionLogHandler` записывает все доступные данные
