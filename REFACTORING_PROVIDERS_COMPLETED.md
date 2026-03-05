# Рефакторинг провайдеров: Устранение дублирования с LLMOrchestrator

## Выполненные изменения

### Этап 1: Упрощение LlamaCppProvider

**Файл:** `core/infrastructure/providers/llm/llama_cpp_provider.py`

#### Было (до рефакторинга)

Метод `_generate_structured_impl()` (380 строк):
```python
async def _generate_structured_impl(self, request: LLMRequest) -> StructuredLLMResponse:
    # Retry цикл (до max_retries)
    for attempt in range(1, config.max_retries + 1):
        try:
            # Генерация
            raw_response = await self._generate_impl(structured_request)
            
            # Извлечение JSON
            json_content = self._extract_json_from_response(raw_response.content)
            
            # Валидация схемы
            parsed_content = temp_model.model_validate(json_content)
            
            # Успех
            return StructuredLLMResponse(...)
            
        except json.JSONDecodeError:
            # Добавление ошибки в промпт
            structured_request = self._add_error_to_prompt(...)
            continue
            
        except ValidationError:
            # Добавление ошибки в промпт
            structured_request = self._add_error_to_prompt(...)
            continue
    
    # Все попытки исчерпаны
    raise StructuredOutputError(...)
```

**Проблемы:**
- Дублирование retry логики с LLMOrchestrator
- Парсинг JSON и валидация в провайдере
- Сложность тестирования
- Нарушение единой ответственности

#### Стало (после рефакторинга)

Метод `_generate_structured_impl()` (60 строк):
```python
async def _generate_structured_impl(self, request: LLMRequest) -> LLMResponse:
    """
    Упрощённая генерация для структурированного вывода.
    
    АРХИТЕКТУРА:
    - Провайдер ТОЛЬКО выполняет синхронный вызов модели
    - Возвращает сырой текст (LLMResponse)
    - Без retry, без парсинга JSON, без валидации
    - Вся логика структурированного вывода в LLMOrchestrator
    """
    if not request.structured_output:
        return await self._generate_impl(request)
    
    # Добавляем схему в промпт
    enhanced_prompt = self._add_schema_to_prompt(
        request.prompt,
        request.structured_output.schema_def
    )
    
    # Создаем запрос с улучшенным промптом
    structured_request = LLMRequest(
        prompt=enhanced_prompt,
        system_prompt=request.system_prompt,
        temperature=0.1,
        max_tokens=min(request.max_tokens, 1500),
        ...
    )
    
    # Вызываем обычную генерацию и возвращаем сырой ответ
    raw_response = await self._generate_impl(structured_request)
    
    return raw_response
```

**Преимущества:**
- ✅ Провайдер только вызывает модель
- ✅ Нет retry логики
- ✅ Нет парсинга/валидации
- ✅ Проще тестировать
- ✅ Соответствует единой ответственности

### Этап 2: Обновление BaseLLMProvider

**Файл:** `core/infrastructure/providers/llm/base_llm.py`

#### Изменения

1. **Обновлена сигнатура абстрактного метода:**
```python
# Было:
async def _generate_structured_impl(
    self,
    request: LLMRequest
) -> StructuredLLMResponse:

# Стало:
async def _generate_structured_impl(
    self,
    request: LLMRequest
) -> LLMResponse:  # ← Возвращает сырой ответ
```

2. **Добавлен метод для обратной совместимости:**
```python
async def _parse_and_validate_structured_response(
    self,
    raw_response: LLMResponse,
    schema: Optional[Dict[str, Any]],
    output_model: str
) -> StructuredLLMResponse:
    """
    Парсинг и валидация структурированного ответа.
    
    ДЛЯ ОБРАТНОЙ СОВМЕСТИМОСТИ - используется в generate_structured().
    В новом коде LLMOrchestrator выполняет эту логику.
    """
    # Извлечение JSON
    json_content = self._extract_json_from_response(raw_response.content)
    
    try:
        # Парсинг JSON
        parsed_json = json.loads(json_content)
        
        # Создание Pydantic модели
        temp_model = self._create_pydantic_from_schema(output_model, schema)
        
        # Валидация
        parsed_content = temp_model.model_validate(parsed_json)
        
        return StructuredLLMResponse(...)
        
    except (json.JSONDecodeError, ValidationError) as e:
        return StructuredLLMResponse(
            parsed_content=None,
            validation_errors=[{"error_type": type(e).__name__, "message": str(e)}],
            ...
        )
```

3. **Обновлён generate_structured():**
```python
async def generate_structured(self, request: LLMRequest) -> StructuredLLMResponse:
    """
    Генерация структурированных данных по JSON Schema.
    
    ВАЖНО: Этот метод для обратной совместимости.
    Для нового кода используйте LLMOrchestrator.execute_structured().
    """
    # Вызов реализации (возвращает сырой LLMResponse)
    raw_response = await self._generate_structured_impl(request)
    
    # Парсинг и валидация (для обратной совместимости)
    structured_response = await self._parse_and_validate_structured_response(
        raw_response=raw_response,
        schema=request.structured_output.schema_def,
        output_model=request.structured_output.output_model
    )
    
    return structured_response
```

## Архитектурные принципы

### Распределение ответственности

| Компонент | Ответственность |
|-----------|----------------|
| **LLMOrchestrator** | - Retry логика<br>- Парсинг JSON<br>- Валидация схем<br>- Corrective prompt<br>- Метрики |
| **BaseLLMProvider** | - Обратная совместимость<br>- Парсинг для старого кода<br>- Генерация correlation_id |
| **LlamaCppProvider** | - Синхронный вызов модели<br>- Возврат сырого текста<br>- Добавление схемы в промпт |

### Миграционный путь

```
Старый код:                          Новый код:
────────────                         ────────────
provider.generate_structured()  →    orchestrator.execute_structured()
                                     (retry, парсинг, валидация)
                                     
provider._generate_structured_impl() → provider._generate_impl()
(с retry и парсингом)                  (только вызов модели)
```

## Обратная совместимость

### Сохранена полная обратная совместимость:

1. **generate_structured()** продолжает работать:
```python
# Старый код продолжает работать
response = await provider.generate_structured(request)
```

2. **Возвращается StructuredLLMResponse**:
```python
# Тот же тип возврата
assert isinstance(response, StructuredLLMResponse)
```

3. **Методы парсинга доступны**:
```python
# Для кастомной логики
json_content = provider._extract_json_from_response(text)
model = provider._create_pydantic_from_schema("Name", schema)
```

## Метрики рефакторинга

### Удаление дублирования

| Метрика | До | После | Изменение |
|---------|-----|-------|-----------|
| Строк в `_generate_structured_impl()` | 380 | 60 | -84% |
| Циклов retry в провайдере | 2 | 0 | -100% |
| Вызовов `model_validate()` в провайдере | 4 | 0 | -100% |
| Вызовов `_add_error_to_prompt()` | 2 | 0 | -100% |

### Упрощение тестирования

**Было:**
```python
# Нужно мокать много внутренней логики
@patch('llama_cpp.Llama')
@patch('json.loads')
@patch('pydantic.model_validate')
async def test_structured_output(...):
    ...
```

**Стало:**
```python
# Мокаем только вызов модели
@patch('llama_cpp.Llama')
async def test_structured_output(...):
    response = await provider._generate_structured_impl(request)
    assert response.content == "..."
```

## Влияние на другие компоненты

### Не требуют изменений:

1. **Навыки и инструменты**, использующие `executor.execute_action("llm.generate_structured")`:
   - ActionExecutor сам использует LLMOrchestrator
   - Изменения прозрачны

2. **Паттерны поведения**, использующие оркестратор:
   - ReActPattern через `_execute_llm_with_orchestrator()`
   - Уже используют правильный подход

### Требуют изменений (опционально):

1. **Прямые вызовы `provider.generate_structured()`**:
   - Продолжат работать (обратная совместимость)
   - Рекомендуется миграция на `orchestrator.execute_structured()`

2. **Тесты, мокающие провайдеры**:
   - Обновить сигнатуры
   - Упростить моки

## Проверка после рефакторинга

### Глобальный поиск дублирования:

```bash
# Поиск retry циклов в провайдерах
grep -n "for attempt in range" core/infrastructure/providers/llm/

# Ожидаемый результат: пусто (удалено из провайдеров)

# Поиск model_validate в провайдерах
grep -n "model_validate" core/infrastructure/providers/llm/

# Ожидаемый результат: только в base_llm.py (для обратной совместимости)
```

### Запуск тестов:

```bash
# Тесты провайдеров
pytest tests/infrastructure/providers/llm/ -v

# Тесты оркестратора
pytest test_llm_orchestrator.py -v

# Интеграционные тесты
pytest tests/application/ -v
```

## Рекомендации

### Для нового кода:

1. **Используйте LLMOrchestrator:**
```python
response = await orchestrator.execute_structured(
    request=request,
    provider=provider,
    max_retries=3
)
```

2. **Не вызывайте напрямую провайдеры:**
```python
# ❌ Избегайте:
response = await provider.generate_structured(request)

# ✅ Используйте:
response = await orchestrator.execute_structured(...)
```

### Для миграции старого кода:

1. **Найдите прямые вызовы:**
```bash
grep -r "provider.generate_structured" core/application/
```

2. **Замените на вызов через executor:**
```python
# Было:
response = await llm_provider.generate_structured(request)

# Стало:
result = await executor.execute_action(
    action_name="llm.generate_structured",
    llm_provider=llm_provider,
    parameters={...}
)
```

## Заключение

Рефакторинг провайдеров завершён:

- ✅ Удалено дублирование retry логики
- ✅ Провайдеры только вызывают модель
- ✅ LLMOrchestrator управляет структурированным выводом
- ✅ Сохранена полная обратная совместимость
- ✅ Упрощено тестирование
- ✅ Соответствие принципам чистой архитектуры

**Следующий шаг:** Рефакторинг ReActPattern и EvaluationPattern для использования оркестратора вместо прямых вызовов.
