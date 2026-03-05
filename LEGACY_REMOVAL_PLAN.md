# План удаления Legacy-кода LLMOrchestrator

**Дата создания:** 2026-03-05  
**Статус:** Готов к выполнению  
**Приоритет:** Средний (технический долг)  
**Ожидаемое время:** 5-7 дней  

---

## 📋 Содержание

1. [Обоснование](#обоснование)
2. [Аудит текущего состояния](#аудит-текущего-состояния)
3. [Этап 1: Подготовка инфраструктуры](#этап-1-подготовка-инфраструктуры)
4. [Этап 2: Удаление generate_structured()](#этап-2-удаление-generate_structured-из-basellmprovider)
5. [Этап 3: Удаление fallback-путей](#этап-3-удаление-fallback-путей)
6. [Этап 4: Финальная очистка](#этап-4-финальная-очистка)
7. [Этап 5: Тестирование и валидация](#этап-5-тестирование-и-валидация)
8. [Контрольный список качества](#контрольный-список-качества)
9. [План отката](#план-отката)

---

## Обоснование

После внедрения `LLMOrchestrator` в проекте остался значительный объем legacy-кода для обратной совместимости:

### Проблемы текущего состояния

| Проблема | Влияние | Пример |
|----------|---------|--------|
| **Дублирование функциональности** | Усложнение поддержки | 2 API для одного действия |
| **Дублирование логики** | Риск рассинхронизации | Парсинг JSON в 2 местах |
| **Fallback-пути** | Усложнение тестирования | Нужно тестировать оба пути |
| **Запутанность для разработчиков** | Ошибки использования | Неясно, какой API выбирать |

### Цели удаления

- ✅ **Единый API** — только `LLMOrchestrator.execute_structured()`
- ✅ **Удаление ~400 строк** legacy-кода
- ✅ **Упрощение тестирования** — один путь выполнения
- ✅ **Улучшение наблюдаемости** — централизованное логирование

---

## Аудит текущего состояния

### Компоненты с дублированием

```
┌─────────────────────────────────────────────────────────────────┐
│                    LLM ВЫЗОВ (СТРУКТУРИРОВАННЫЙ)                │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  СТАРЫЙ ПУТЬ (LEGACY):                                          │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ BaseLLMProvider.generate_structured()                   │   │
│  │   ├─ _publish_prompt_event()       ← ДУБЛИКАТ           │   │
│  │   ├─ _generate_structured_impl()   ← НЕ ИСПОЛЬЗУЕТСЯ    │   │
│  │   ├─ _parse_and_validate()         ← ДУБЛИКАТ           │   │
│  │   └─ _publish_response_event()     ← ДУБЛИКАТ           │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  НОВЫЙ ПУТЬ (ПРАВИЛЬНЫЙ):                                       │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ LLMOrchestrator.execute_structured()                    │   │
│  │   ├─ _publish_prompt_event()       ← ИСПОЛЬЗУЕТСЯ       │   │
│  │   ├─ _execute_structured_attempt() ← ИСПОЛЬЗУЕТСЯ       │   │
│  │   ├─ _validate_structured_response() ← ИСПОЛЬЗУЕТСЯ     │   │
│  │   └─ _publish_response_event()     ← ИСПОЛЬЗУЕТСЯ       │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  FALLBACK-ПУТИ (УДАЛИТЬ):                                       │
│  ├─ ReActPattern._perform_structured_reasoning() (строки 895+) │
│  └─ ActionExecutor._llm_generate_structured() (строки 645+)    │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Файлы для изменения

| Файл | Изменения | Строк | Приоритет |
|------|-----------|-------|-----------|
| `base_llm.py` | Удаление методов | ~293 | 🔴 Критично |
| `pattern.py` | Удаление fallback | ~75 | 🔴 Критично |
| `action_executor.py` | Удаление fallback | ~35 | 🔴 Критично |
| `json_parser.py` | **Создать** | ~100 | 🔴 Критично |
| Тесты | Обновление вызовов | ~50 | 🟡 Важно |

---

## Этап 1: Подготовка инфраструктуры

**Время:** 1 день  
**Риск:** Низкий  

### Шаг 1.1: Создание json_parser.py

**Файл:** `core/infrastructure/providers/llm/json_parser.py`

```python
"""
JSON Parser для валидации структурированных ответов LLM.

ИСПОЛЬЗУЕТСЯ:
- LLMOrchestrator._validate_structured_response()
- (BaseLLMProvider — до удаления)

ПРИМЕР:
    result = validate_structured_response(raw_content, schema)
    if result['success']:
        parsed = result['parsed']
"""
import json
from typing import Dict, Any, Optional, Type, List
from pydantic import ValidationError, create_model


def validate_structured_response(
    raw_content: str,
    schema: Optional[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Валидация структурированного ответа.
    
    ПРОВЕРКИ:
    1. JSON парсинг
    2. Соответствие схеме через Pydantic (если указана)
    3. Полнота ответа (не обрезан ли)
    
    ПАРАМЕТРЫ:
    - raw_content: Сырой текст ответа
    - schema: JSON Schema для валидации (опционально)
    
    ВОЗВРАЩАЕТ:
    - Dict с полями:
      - success: bool — прошла ли валидация
      - error_type: str | None — тип ошибки
      - error_message: str | None — сообщение об ошибке
      - parsed: Any | None — распарсенные данные
    """
    # Проверка 1: JSON парсинг
    try:
        parsed = json.loads(raw_content)
    except json.JSONDecodeError as e:
        return {
            "success": False,
            "error_type": "json_error",
            "error_message": f"JSON парсинг не удался: {str(e)}",
            "parsed": None
        }
    
    # Проверка 2: Соответствие схеме через Pydantic
    if schema:
        try:
            # Создаём динамическую Pydantic модель из схемы
            DynamicModel = schema_to_pydantic_model(schema, "StructuredOutput")
            
            # Валидируем через Pydantic
            parsed_content = DynamicModel.model_validate(parsed)
            
            return {
                "success": True,
                "error_type": None,
                "error_message": None,
                "parsed": parsed_content
            }
            
        except ValidationError as e:
            error_details = []
            for error in e.errors():
                field = ".".join(str(x) for x in error.get('loc', []))
                msg = error.get('msg', 'validation error')
                error_details.append(f"{field}: {msg}")
            
            return {
                "success": False,
                "error_type": "validation_error",
                "error_message": f"Валидация схемы не пройдена: {'; '.join(error_details)}",
                "parsed": None
            }
            
        except Exception as e:
            return {
                "success": False,
                "error_type": "validation_error",
                "error_message": f"Ошибка валидации схемы: {type(e).__name__}: {str(e)}",
                "parsed": None
            }
    
    # Схема не указана — только JSON парсинг
    return {
        "success": True,
        "error_type": None,
        "error_message": None,
        "parsed": parsed
    }


def schema_to_pydantic_model(
    schema: Dict[str, Any],
    model_name: str = "DynamicModel"
) -> Type:
    """
    Создаёт Pydantic модель из JSON Schema.
    
    ПАРАМЕТРЫ:
    - schema: JSON Schema dict
    - model_name: Имя создаваемой модели
    
    ВОЗВРАЩАЕТ:
    - Pydantic model class
    """
    def schema_field_to_type(field_schema: Dict[str, Any], field_name: str = "field"):
        """Преобразует JSON Schema поле в Python тип."""
        field_type = field_schema.get('type')
        
        if field_type == 'string':
            return str
        elif field_type == 'integer':
            return int
        elif field_type == 'number':
            return float
        elif field_type == 'boolean':
            return bool
        elif field_type == 'array':
            items = field_schema.get('items', {})
            item_type = schema_field_to_type(items, f"{field_name}_item")
            return List[item_type]
        elif field_type == 'object':
            nested_model = schema_to_pydantic_model(field_schema, f"{field_name.title()}Object")
            return nested_model
        else:
            return Any
    
    properties = schema.get('properties', {})
    required = set(schema.get('required', []))
    
    fields = {}
    for field_name, field_schema in properties.items():
        field_type = schema_field_to_type(field_schema, field_name)
        is_required = field_name in required
        
        if is_required:
            fields[field_name] = (field_type, ...)
        else:
            fields[field_name] = (Optional[field_type], None)
    
    return create_model(model_name, **fields)


def extract_json_from_response(content: str) -> str:
    """
    Извлечение JSON из текста ответа (если есть обёртка).
    
    ПАРАМЕТРЫ:
    - content: Текст ответа LLM
    
    ВОЗВРАЩАЕТ:
    - JSON строка
    """
    # Попытка найти JSON в тексте
    start = content.find('{')
    end = content.rfind('}') + 1
    
    if start != -1 and end > start:
        return content[start:end]
    
    return content
```

---

### Шаг 1.2: Интеграция json_parser в LLMOrchestrator

**Файл:** `core/infrastructure/providers/llm/llm_orchestrator.py`

**Добавить импорт в начало файла:**
```python
from core.infrastructure.providers.llm.json_parser import (
    validate_structured_response,
    schema_to_pydantic_model,
    extract_json_from_response
)
```

**Заменить метод `_validate_structured_response` (строки ~720-850):**

```python
def _validate_structured_response(
    self,
    raw_content: str,
    schema: Optional[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Валидация структурированного ответа.
    
    ДЕЛЕГИРОВАНИЕ: Вызывает функции из json_parser.py
    """
    # Делегируем логику в json_parser
    return validate_structured_response(raw_content, schema)
```

---

### Шаг 1.3: Проверка качества этапа 1

```bash
# 1. Проверка синтаксиса
python -m py_compile core/infrastructure/providers/llm/json_parser.py
python -m py_compile core/infrastructure/providers/llm/llm_orchestrator.py

# 2. Запуск тестов на парсинг
pytest tests/infrastructure/providers/llm/test_structured_output.py -v

# 3. Проверка импортов
python -c "from core.infrastructure.providers.llm.json_parser import validate_structured_response; print('OK')"

# 4. Интеграционный тест
python main.py
# Проверить что агент запускается и логи сохраняются
```

**Критерии завершения этапа 1:**
- [ ] `json_parser.py` создан и проходит синтаксическую проверку
- [ ] `LLMOrchestrator` использует функции из `json_parser`
- [ ] Все тесты проходят
- [ ] Агент запускается без ошибок

---

## Этап 2: Удаление generate_structured() из BaseLLMProvider

**Время:** 2 дня  
**Риск:** Средний  

### Шаг 2.1: Удаление методов из base_llm.py

**Файл:** `core/infrastructure/providers/llm/base_llm.py`

#### 2.1.1 Удалить методы логирования (строки 109-177)

```python
# ❌ УДАЛИТЬ ЦЕЛИКОМ (68 строк):

async def _publish_prompt_event(
    self,
    request: LLMRequest,
    correlation_id: str
):
    """Публикация события о генерации промпта."""
    # ... весь метод ...

async def _publish_response_event(
    self,
    response: StructuredLLMResponse,
    correlation_id: str,
    elapsed_time: float
):
    """Публикация события о получении ответа."""
    # ... весь метод ...

async def _publish_error_event(
    self,
    error: Exception,
    correlation_id: str,
    elapsed_time: float
):
    """Публикация события об ошибке LLM вызова."""
    # ... весь метод ...
```

#### 2.1.2 Удалить _generate_structured_impl() (строки 344-363)

```python
# ❌ УДАЛИТЬ ЦЕЛИКОМ (19 строк):

async def _generate_structured_impl(
    self,
    request: LLMRequest
) -> LLMResponse:
    """
    Реализация структурированной генерации.
    Переопределяется в подклассах.
    """
    raise NotImplementedError()
```

#### 2.1.3 Удалить generate_structured() (строки 365-453)

```python
# ❌ УДАЛИТЬ ЦЕЛИКОМ (88 строк):

async def generate_structured(
    self,
    request: LLMRequest
) -> StructuredLLMResponse:
    """
    Генерация структурированных данных по JSON Schema.
    
    ВАЖНО: Этот метод для обратной совместимости.
    Для нового кода используйте LLMOrchestrator.execute_structured().
    """
    # ... весь метод ...
```

#### 2.1.4 Удалить _parse_and_validate_structured_response() (строки 455-540)

```python
# ❌ УДАЛИТЬ ЦЕЛИКОМ (85 строк):

async def _parse_and_validate_structured_response(
    self,
    raw_response: LLMResponse,
    schema: Optional[Dict[str, Any]],
    output_model: str
) -> StructuredLLMResponse:
    """
    Парсинг и валидация структурированного ответа.
    
    ДЛЯ ОБРАТНОЙ СОВМЕСТИМОСТИ - используется в generate_structured().
    """
    # ... весь метод ...
```

#### 2.1.5 Удалить generate_for_capability() (строки 542-575)

```python
# ❌ УДАЛИТЬ ЦЕЛИКОМ (33 строки):

async def generate_for_capability(
    self,
    system_prompt: str,
    user_input: str,
    capabilities
) -> tuple:
    """Генерация для конкретной capability."""
    # ... весь метод ...
```

---

### Шаг 2.2: Обновление подклассов BaseLLMProvider

**Файл:** `core/infrastructure/providers/llm/llama_cpp_provider.py`

**Проверить наличие переопределений:**
```bash
grep -n "_generate_structured_impl\|generate_structured" core/infrastructure/providers/llm/llama_cpp_provider.py
```

**Если найдены — удалить переопределения.**

---

**Файл:** `core/infrastructure/providers/llm/mock_provider.py`

**Проверить наличие переопределений:**
```bash
grep -n "_generate_structured_impl\|generate_structured" core/infrastructure/providers/llm/mock_provider.py
```

**Если найдены — удалить переопределения.**

---

### Шаг 2.3: Обновление документации класса

**Файл:** `core/infrastructure/providers/llm/base_llm.py`

**Обновить docstring класса:**

```python
class BaseLLMProvider(BaseProvider, ABC):
    """
    Базовый класс для всех LLM-провайдеров.
    
    АРХИТЕКТУРНЫЕ ПРИНЦИПЫ:
    1. Инверсия зависимостей: Зависит только от абстракций (LLMPort)
    2. Единый контракт: Все методы имеют стандартизированную сигнатуру
    3. Безопасность по умолчанию: Встроенные ограничения и валидация
    4. Наблюдаемость: Автоматическое логирование и метрики
    5. Отказоустойчивость: Грациозная деградация при ошибках
    
    ИЗМЕНЕНИЯ (2026-03-05):
    - ❌ УДАЛЁН: generate_structured() — перенесён в LLMOrchestrator
    - ❌ УДАЛЁН: _generate_structured_impl() — не используется
    - ❌ УДАЛЁН: _parse_and_validate_structured_response() — в json_parser.py
    - ❌ УДАЛЁН: _publish_*_event() — дублируют LLMOrchestrator
    - ❌ УДАЛЁН: generate_for_capability() — устаревший метод
    
    ИСПОЛЬЗОВАНИЕ:
    # Для структурированной генерации используйте LLMOrchestrator:
    orchestrator = app_context.llm_orchestrator
    response = await orchestrator.execute_structured(
        request=request,
        provider=llm_provider,
        max_retries=3
    )
    """
```

---

### Шаг 2.4: Проверка качества этапа 2

```bash
# 1. Проверка синтаксиса
python -m py_compile core/infrastructure/providers/llm/base_llm.py
python -m py_compile core/infrastructure/providers/llm/llama_cpp_provider.py
python -m py_compile core/infrastructure/providers/llm/mock_provider.py

# 2. Поиск остаточных вызовов
grep -r "generate_structured" core/infrastructure/providers/llm/
# Ожидается: только в тестах и документации

# 3. Запуск unit-тестов
pytest tests/unit/infrastructure/providers/llm/ -v

# 4. Проверка что методы удалены
python -c "
from core.infrastructure.providers.llm.base_llm import BaseLLMProvider
assert not hasattr(BaseLLMProvider, 'generate_structured'), 'generate_structured ещё существует!'
assert not hasattr(BaseLLMProvider, '_generate_structured_impl'), '_generate_structured_impl ещё существует!'
print('✅ Методы удалены корректно')
"
```

**Критерии завершения этапа 2:**
- [ ] Все 5 методов удалены из `base_llm.py`
- [ ] Подклассы обновлены (нет переопределений)
- [ ] Документация обновлена
- [ ] Все тесты проходят
- [ ] Поиск `grep` не находит вызовов в production-коде

---

## Этап 3: Удаление fallback-путей

**Время:** 2 дня  
**Риск:** Средний  

### Шаг 3.1: Обновление action_executor.py

**Файл:** `core/application/agent/components/action_executor.py`

#### 3.1.1 Удалить fallback в _llm_generate_structured() (строки ~645-680)

**Заменить:**

```python
# БЫЛО:
async def _llm_generate_structured(
    self,
    llm_provider,
    parameters: Dict[str, Any],
    orchestrator: Any = None,
    context: ExecutionContext = None
) -> ActionResult:
    # ... создание request ...
    
    # Вызов через оркестратор если доступен
    if orchestrator:
        response = await orchestrator.execute_structured(...)
        # ... обработка успеха ...
    else:
        # ❌ FALLBACK: прямой вызов через провайдер
        from core.infrastructure.providers.llm.llama_cpp_provider import StructuredOutputError
        
        try:
            response = await llm_provider.generate_structured(request)
            return ActionResult(success=True, data={...})
        except Exception as e:
            return ActionResult(success=False, error=str(e))

# СТАЛО:
async def _llm_generate_structured(
    self,
    llm_provider,
    parameters: Dict[str, Any],
    orchestrator: Any = None,
    context: ExecutionContext = None
) -> ActionResult:
    """
    Структурированная генерация через LLM с JSON Schema.
    
    ТРЕБОВАНИЯ:
    - LLMOrchestrator ОБЯЗАТЕЛЕН (fallback не поддерживается)
    """
    from core.models.types.llm_types import LLMRequest, StructuredOutputConfig
    
    prompt = parameters.get("prompt", "")
    if not prompt:
        return ActionResult(success=False, error="Параметр 'prompt' обязателен")
    
    structured_output = parameters.get("structured_output")
    if not structured_output:
        return ActionResult(success=False, error="Параметр 'structured_output' обязателен")
    
    if isinstance(structured_output, dict):
        structured_output = StructuredOutputConfig(**structured_output)
    
    request = LLMRequest(
        prompt=prompt,
        system_prompt=parameters.get("system_prompt"),
        temperature=parameters.get("temperature", 0.1),
        max_tokens=parameters.get("max_tokens", 1000),
        structured_output=structured_output
    )
    
    # ✅ LLMOrchestrator ОБЯЗАТЕЛЕН
    if not orchestrator:
        return ActionResult(
            success=False,
            error="LLMOrchestrator недоступен — требуется для структурированной генерации"
        )
    
    response = await orchestrator.execute_structured(
        request=request,
        provider=llm_provider,
        max_retries=parameters.get("max_retries", 3),
        attempt_timeout=parameters.get("attempt_timeout"),
        total_timeout=parameters.get("total_timeout"),
        session_id=parameters.get('session_id'),
        agent_id=parameters.get('agent_id'),
        step_number=parameters.get('step_number'),
        phase=parameters.get('phase', 'unknown')
    )
    
    # Проверка успеха
    if response.success:
        return ActionResult(
            success=True,
            data={
                "parsed_content": response.parsed_content.model_dump() if hasattr(response.parsed_content, 'model_dump') else response.parsed_content,
                "raw_content": response.raw_response.content
            },
            metadata={
                "model": response.raw_response.model,
                "tokens_used": response.raw_response.tokens_used,
                "generation_time": response.raw_response.generation_time,
                "parsing_attempts": response.parsing_attempts,
                "success": response.success
            }
        )
    else:
        return ActionResult(
            success=False,
            error=f"Structured output failed after {response.parsing_attempts} attempts",
            metadata={
                "validation_errors": response.validation_errors,
                "parsing_attempts": response.parsing_attempts,
                "error_type": "StructuredOutputError"
            }
        )
```

---

### Шаг 3.2: Обновление ReActPattern

**Файл:** `core/application/behaviors/react/pattern.py`

#### 3.2.1 Удалить fallback в _perform_structured_reasoning() (строки ~895-970)

**Найти блок:**
```python
else:
    # === FALLBACK: ПРЯМОЙ ВЫЗОВ БЕЗ ORCHESTRATOR ===
    # Для обратной совместимости если оркестратор не доступен
    await self._log("debug", f"[Попытка {retry_count + 1}] LLMOrchestrator недоступен, прямой вызов...")
    
    try:
        await self._log("info", f"[Попытка {retry_count + 1}] ВЫЗОВ llm_provider.generate_structured()...")
        response = await asyncio.wait_for(
            llm_provider.generate_structured(llm_request),
            timeout=llm_timeout
        )
        await self._log("info", f"[Попытка {retry_count + 1}/{max_retries}] LLM ответ ПОЛУЧЕН!")
        break
    except (AsyncTimeoutError, TimeoutError) as e:
        # ...
```

**Заменить на:**
```python
else:
    # === ORCHESTRATOR НЕ ДОСТУПЕН — КРИТИЧЕСКАЯ ОШИБКА ===
    error_msg = "LLMOrchestrator недоступен — критическая ошибка инфраструктуры"
    await self._log("error", error_msg)
    
    # Возвращаем fallback вместо попытки прямого вызова
    return {
        "analysis": {
            "current_situation": "LLMOrchestrator недоступен",
            "progress_assessment": "Неизвестно",
            "confidence": 0.0,
            "errors_detected": True,
            "consecutive_errors": self.error_count + 1,
            "execution_time": context_analysis.get("execution_time_seconds", 0),
            "no_progress_steps": context_analysis.get("no_progress_steps", 0)
        },
        "decision": {
            "next_action": "final_answer.generate",
            "reasoning": "Инфраструктурная ошибка — используем fallback",
            "parameters": {"query": session_context.get_goal() or "Продолжить"}
        },
        "available_capabilities": available_capabilities,
        "needs_rollback": False
    }
```

#### 3.2.2 Упростить _execute_llm_with_orchestrator() (строки 97-167)

**Заменить:**

```python
# БЫЛО (70 строк):
async def _execute_llm_with_orchestrator(
    self,
    llm_request: LLMRequest,
    llm_provider: Any,
    timeout: float,
    session_context: 'SessionContext'
) -> tuple[bool, Any, str]:
    """
    Выполнение LLM вызова через LLMOrchestrator.
    
    АРХИТЕКТУРНОЕ ПРЕИМУЩЕСТВО:
    - При таймауте не бросает исключение, а возвращает LLMResponse с error
    - Фоновый поток завершается корректно, результат не теряется
    - Метрики и мониторинг "брошенных" вызовов
    """
    orchestrator = self.llm_orchestrator
    
    if not orchestrator:
        # ❌ Fallback: прямой вызов без оркестратора (для обратной совместимости)
        await self._log("debug", "LLMOrchestrator недоступен, используем прямой вызов")
        return False, None, "orchestrator_not_available"
    
    try:
        # ...
    except Exception as e:
        # ...

# СТАЛО (35 строк):
async def _execute_llm_with_orchestrator(
    self,
    llm_request: LLMRequest,
    llm_provider: Any,
    timeout: float,
    session_context: 'SessionContext'
) -> tuple[bool, Any, str]:
    """
    Выполнение LLM вызова через LLMOrchestrator.
    
    АРХИТЕКТУРНОЕ ПРЕИМУЩЕСТВО:
    - При таймауте не бросает исключение, а возвращает LLMResponse с error
    - Фоновый поток завершается корректно, результат не теряется
    - Метрики и мониторинг "брошенных" вызовов
    
    ТРЕБОВАНИЯ:
    - LLMOrchestrator ОБЯЗАТЕЛЕН (fallback не поддерживается)
    """
    orchestrator = self.llm_orchestrator
    
    if not orchestrator:
        return False, None, "orchestrator_not_available"
    
    try:
        response = await orchestrator.execute(
            request=llm_request,
            timeout=timeout,
            provider=llm_provider,
            capability_name="react_pattern.think"
        )
        
        # Проверка на ошибку в ответе
        if response.finish_reason == "error":
            error_msg = "Неизвестная ошибка LLM"
            if response.metadata:
                if isinstance(response.metadata, dict):
                    error_msg = response.metadata.get('error', error_msg)
                elif isinstance(response.metadata, str):
                    error_msg = response.metadata
            
            await self._log("error", f"LLM вызов через оркестратор вернул ошибку: {error_msg}")
            return False, None, error_msg
        
        # Успешный ответ
        await self._log("info", "LLM вызов через оркестратор завершён успешно")
        
        # Оборачиваем в формат ожидаемый _perform_structured_reasoning
        structured_response = {
            'raw_response': response,
            'content': response.content,
            'metadata': response.metadata
        }
        
        return True, structured_response, ""
        
    except Exception as e:
        error_msg = f"Исключение из LLMOrchestrator: {type(e).__name__}: {str(e)}"
        await self._log("error", error_msg)
        return False, None, error_msg
```

---

### Шаг 3.3: Проверка качества этапа 3

```bash
# 1. Проверка синтаксиса
python -m py_compile core/application/agent/components/action_executor.py
python -m py_compile core/application/behaviors/react/pattern.py

# 2. Поиск остаточных fallback
grep -n "FALLBACK\|fallback\|прямой вызов" core/application/agent/components/action_executor.py
grep -n "FALLBACK\|fallback\|прямой вызов" core/application/behaviors/react/pattern.py
# Ожидается: только в комментариях

# 3. Проверка что generate_structured не вызывается
grep -r "llm_provider.generate_structured\|provider.generate_structured" core/application/
# Ожидается: только в тестах

# 4. Запуск интеграционных тестов
pytest tests/integration/test_stage7_integration.py -v

# 5. Проверка что orchestrator обязателен
python -c "
import ast
import sys

with open('core/application/agent/components/action_executor.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Проверка что есть проверка на None
if 'if not orchestrator:' in content:
    print('✅ Проверка на orchestrator существует')
else:
    print('❌ Проверка на orchestrator отсутствует!')
    sys.exit(1)

# Проверка что нет fallback
if 'llm_provider.generate_structured' in content:
    print('❌ Найден fallback вызов generate_structured!')
    sys.exit(1)
else:
    print('✅ Fallback вызовы удалены')
"
```

**Критерии завершения этапа 3:**
- [ ] Fallback удалён из `action_executor.py`
- [ ] Fallback удалён из `pattern.py`
- [ ] `_execute_llm_with_orchestrator()` упрощён
- [ ] Все тесты проходят
- [ ] Поиск `grep` не находит fallback-путей

---

## Этап 4: Финальная очистка

**Время:** 1 день  
**Риск:** Низкий  

### Шаг 4.1: Аудит неиспользуемого кода

```bash
# Поиск всех ссылок на удалённые методы
grep -r "generate_structured" core/ --include="*.py" | grep -v test | grep -v __pycache__
grep -r "_generate_structured_impl" core/ --include="*.py" | grep -v test | grep -v __pycache__
grep -r "_parse_and_validate" core/ --include="*.py" | grep -v test | grep -v __pycache__
```

**Ожидается:** Только в документации и импортах

---

### Шаг 4.2: Обновление тестов

**Файлы для обновления:**

#### tests/unit/infrastructure/providers/llm/test_correlation_id.py

**Заменить:**
```python
# БЫЛО:
response = await mock_provider.generate_structured(request)

# СТАЛО:
response = await mock_orchestrator.execute_structured(
    request=request,
    provider=mock_provider
)
```

#### tests/infrastructure/providers/llm/test_structured_output.py

**Заменить все вызовы `generate_structured()` на `execute_structured()`.**

#### tests/react/test_react_invariants.py

**Обновить моки:**
```python
# БЫЛО:
mock_llm.generate_structured = AsyncMock(return_value={...})

# СТАЛО:
mock_orchestrator.execute_structured = AsyncMock(return_value={...})
```

---

### Шаг 4.3: Проверка качества этапа 4

```bash
# 1. Запуск всех тестов
pytest tests/ -v --tb=short

# 2. Проверка что нет битых импортов
python -c "
from core.infrastructure.providers.llm.base_llm import BaseLLMProvider
from core.infrastructure.providers.llm.llm_orchestrator import LLMOrchestrator
from core.infrastructure.providers.llm.json_parser import validate_structured_response
print('✅ Все импорты работают')
"

# 3. Проверка размера файлов
wc -l core/infrastructure/providers/llm/base_llm.py
# Ожидается: ~280 строк (было ~575)

# 4. Интеграционный тест
python main.py
# Проверить что агент запускается и работает
```

**Критерии завершения этапа 4:**
- [ ] Все тесты обновлены и проходят
- [ ] Нет битых импортов
- [ ] Нет ссылок на удалённые методы в production-коде
- [ ] Агент запускается без ошибок

---

## Этап 5: Тестирование и валидация

**Время:** 1 день  
**Риск:** Низкий  

### Шаг 5.1: Полный прогон тестов

```bash
# 1. Unit тесты
pytest tests/unit/ -v --tb=short

# 2. Интеграционные тесты
pytest tests/integration/ -v --tb=short

# 3. E2E тесты
pytest tests/e2e/ -v --tb=short

# 4. Тесты ReAct
pytest tests/react/ -v --tb=short

# 5. Тесты LLM
pytest tests/infrastructure/providers/llm/ -v --tb=short
```

**Ожидаемый результат:** Все тесты проходят ✅

---

### Шаг 5.2: Проверка логирования

```bash
# 1. Запуск агента
python main.py

# 2. Проверка логов
ls -la logs/sessions/
cat logs/sessions/*/llm.jsonl | head -20

# 3. Проверка что сохраняются промпты и ответы
python -c "
import json
import glob

llm_files = glob.glob('logs/sessions/*/llm.jsonl')
if not llm_files:
    print('❌ LLM логи не найдены!')
    exit(1)

with open(llm_files[-1], 'r', encoding='utf-8') as f:
    for line in f:
        event = json.loads(line)
        if event.get('event_type') == 'llm.prompt.generated':
            assert 'system_prompt' in event, 'system_prompt отсутствует'
            assert 'user_prompt' in event, 'user_prompt отсутствует'
            print('✅ Промпт сохранён корректно')
            break
    
    for line in f:
        event = json.loads(line)
        if event.get('event_type') == 'llm.response.received':
            assert 'raw_response' in event, 'raw_response отсутствует'
            assert 'response_length' in event, 'response_length отсутствует'
            print('✅ Ответ сохранён корректно')
            break

print('✅ Логирование работает корректно')
"
```

---

### Шаг 5.3: Проверка метрик

```python
# test_metrics.py
import asyncio
from core.config import get_config
from core.infrastructure.context.infrastructure_context import InfrastructureContext
from core.application.context.application_context import ApplicationContext

async def test_metrics():
    config = get_config(profile='dev')
    infrastructure_context = InfrastructureContext(config)
    await infrastructure_context.initialize()
    
    app_config = AppConfig.from_discovery(
        profile="prod",
        data_dir=str(getattr(infrastructure_context.config, 'data_dir', 'data')),
        discovery=infrastructure_context.get_resource_discovery()
    )
    application_context = ApplicationContext(
        infrastructure_context=infrastructure_context,
        config=app_config,
        profile="prod"
    )
    
    await application_context.initialize()
    
    orchestrator = application_context.llm_orchestrator
    metrics = orchestrator.get_metrics()
    
    print("Метрики LLMOrchestrator:")
    print(json.dumps(metrics.to_dict(), indent=2, ensure_ascii=False))
    
    # Проверка что метрики собираются
    assert metrics.total_calls >= 0, "total_calls не корректен"
    assert metrics.structured_success_rate >= 0, "structured_success_rate не корректен"
    
    print("✅ Метрики работают корректно")
    
    await application_context.shutdown()
    await infrastructure_context.shutdown()

asyncio.run(test_metrics())
```

---

### Шаг 5.4: Финальная проверка

```bash
# 1. Подсчёт удалённых строк
echo "=== Статистика изменений ==="
echo "base_llm.py:"
git diff HEAD -- core/infrastructure/providers/llm/base_llm.py | grep -c "^-"
echo "pattern.py:"
git diff HEAD -- core/application/behaviors/react/pattern.py | grep -c "^-"
echo "action_executor.py:"
git diff HEAD -- core/application/agent/components/action_executor.py | grep -c "^-"

# 2. Проверка что json_parser.py создан
ls -la core/infrastructure/providers/llm/json_parser.py

# 3. Финальный запуск
python main.py
```

---

## Контрольный список качества

### Перед каждым этапом

- [ ] Создан backup текущей версии (`git commit -am "Before stage X"`)
- [ ] Все тесты проходят (`pytest tests/ -v`)
- [ ] Агент запускается (`python main.py`)

### После каждого этапа

- [ ] Синтаксическая проверка (`python -m py_compile <файл>`)
- [ ] Unit-тесты проходят
- [ ] Интеграционные тесты проходят
- [ ] Агент запускается без ошибок
- [ ] Логи сохраняются корректно

### После всех этапов

- [ ] Все 5 этапов выполнены
- [ ] Все тесты проходят (`pytest tests/ -v`)
- [ ] Агент запускается (`python main.py`)
- [ ] Логи сохраняются (`logs/sessions/*/llm.jsonl`)
- [ ] Документация обновлена
- [ ] Удалено >350 строк legacy-кода
- [ ] Создан `json_parser.py` (~100 строк)
- [ ] Чистая экономия: ~250-300 строк

---

## План отката

### Если что-то пошло не так

#### Этап 1 (создание json_parser)
```bash
git revert HEAD
# или
rm core/infrastructure/providers/llm/json_parser.py
git checkout core/infrastructure/providers/llm/llm_orchestrator.py
```

#### Этап 2 (удаление методов)
```bash
git revert HEAD
# или
git checkout core/infrastructure/providers/llm/base_llm.py
git checkout core/infrastructure/providers/llm/llama_cpp_provider.py
git checkout core/infrastructure/providers/llm/mock_provider.py
```

#### Этап 3 (удаление fallback)
```bash
git revert HEAD
# или
git checkout core/application/agent/components/action_executor.py
git checkout core/application/behaviors/react/pattern.py
```

#### Этап 4-5 (финальная очистка и тесты)
```bash
git revert HEAD
# или
git checkout tests/
```

### Экстренный откат всех изменений

```bash
# Откат к последнему стабильному коммиту
git stash
git checkout main
git pull origin main

# Или восстановление из backup
git checkout <commit-hash-before-changes>
```

---

## Приложения

### A. Список файлов для изменения

```
core/infrastructure/providers/llm/
├── base_llm.py              # ❌ Удалить ~293 строки
├── json_parser.py           # ✅ Создать (~100 строк)
├── llm_orchestrator.py      # ⚙️ Обновить импорты
├── llama_cpp_provider.py    # ⚙️ Удалить переопределения
└── mock_provider.py         # ⚙️ Удалить переопределения

core/application/
├── behaviors/react/pattern.py                    # ❌ Удалить ~35 строк
└── agent/components/action_executor.py           # ❌ Удалить ~35 строк

tests/
├── unit/infrastructure/providers/llm/test_correlation_id.py    # ⚙️ Обновить
├── infrastructure/providers/llm/test_structured_output.py      # ⚙️ Обновить
└── react/test_react_invariants.py                              # ⚙️ Обновить
```

### B. Команды для проверки

```bash
# Поиск вызовов удалённых методов
grep -r "generate_structured" core/ --include="*.py" | grep -v test
grep -r "_generate_structured_impl" core/ --include="*.py" | grep -v test

# Подсчёт строк
wc -l core/infrastructure/providers/llm/base_llm.py
wc -l core/infrastructure/providers/llm/json_parser.py

# Запуск тестов
pytest tests/ -v --tb=short
pytest tests/infrastructure/providers/llm/ -v
pytest tests/react/ -v

# Проверка логирования
python main.py
cat logs/sessions/*/llm.jsonl | head -20
```

### C. Ожидаемые результаты

**До изменений:**
```
base_llm.py:              575 строк
pattern.py:              1377 строк
action_executor.py:       683 строки
json_parser.py:            0 строк (не существует)
Итого:                   2635 строк
```

**После изменений:**
```
base_llm.py:              282 строки  (-293)
pattern.py:              1342 строки  (-35)
action_executor.py:       648 строк   (-35)
json_parser.py:           100 строк   (+100)
Итого:                   2372 строки  (-263)
```

**Чистая экономия: ~263 строки**

---

**Документ утверждён:** 2026-03-05  
**Готов к выполнению:** ✅  
**Следующий шаг:** Начало Этапа 1
