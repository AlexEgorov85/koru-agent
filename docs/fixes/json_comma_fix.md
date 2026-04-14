# Исправление ошибки парсера JSON с отсутствующими запятыми

## Проблема

LLM иногда генерирует JSON **без запятых между полями**, например:

```json
{
  "field1": "value1"
  "field2": "value2"
}
```

Вместо правильного:

```json
{
  "field1": "value1",
  "field2": "value2"
}
```

Это вызывает ошибку `json.decoder.JSONDecodeError: Expecting ',' delimiter`.

## Решение

Добавлена автоматическая предобработка JSON с исправлением отсутствующих запятых.

### Изменённые файлы

#### 1. `core/infrastructure/providers/llm/json_parser.py`
- Добавлена функция `_fix_missing_commas()` для исправления запятых
- Обрабатывает случаи:
  - После строкового значения идёт новый ключ
  - После закрывающей скобки `}` или `]` идёт новый ключ
  - После числа/булева/null идёт новый ключ
  - Объекты внутри массивов без запятых

#### 2. `core/components/services/json_parsing/service.py`
- Добавлен метод `_fix_missing_commas()` в `JsonParsingService`
- В `_action_parse_json()` добавлена логика:
  1. Сначала пробуем распарсить как есть
  2. При ошибке пытаемся исправить запятые
  3. Если исправление помогло - логируем успех
  4. Если не помогло - возвращаем ошибку как раньше

#### 3. `core/agent/strategies/react/validation.py`
- Добавлена функция `_fix_missing_commas_simple()`
- В `parse_llm_json_response()` добавлена попытка исправления запятых

#### 4. `core/components/services/json_parsing/types.py`
- Исправлен `to_dict()` для правильной сериализации `pydantic_model`
- Добавлено поле `pydantic_model_data` когда есть модель

### Как это работает

**Алгоритм исправления:**

1. Ищем паттерны где после значения отсутствует запятая перед новым ключом:
   - `"value"\n"key"` → `"value",\n"key"`
   - `}\n"key"` → `},\n"key"`  
   - `]\n"key"` → `],\n"key"`
   - `123\n"key"` → `123,\n"key"`
   - `true\n"key"` → `true,\n"key"`
   - `false\n"key"` → `false,\n"key"`
   - `null\n"key"` → `null,\n"key"`
   - `}\n{` → `},\n{` (объекты в массивах)

2. Применяем исправления через regex

3. Пробуем распарсить исправленный JSON

4. Логируем результат (успех/неудача)

### Логирование

При успешном исправлении:
```
🔧 [JsonParsing.parse_json] Применено исправление отсутствующих запятых
✅ [JsonParsing.parse_json] JSON распарсен после исправления запятых: 123 симв., ключи=['field1', 'field2']
```

При неудаче:
```
⚠️ [JsonParsing.parse_json] Ошибка парсинга, попытка исправления: JSONDecodeError: ...
❌ [JsonParsing.parse_json] Исправление запятых не помогло
❌ [JsonParsing.parse_json] Ошибка парсинга JSON: JSONDecodeError: ...
```

### Тесты

Создан файл `tests/unit/json_comma_fix_test.py` с 11 тестами:
- ✅ Исправление запятых между строковыми значениями
- ✅ Исправление запятых между разными типами значений
- ✅ Исправление запятых после вложенных объектов
- ✅ Исправление запятых после массивов
- ✅ Исправление запятых после null значений
- ✅ Множественные отсутствующие запятые
- ✅ Сложная вложенная структура
- ✅ Валидный JSON не изменяется
- ✅ Функция из json_parser.py
- ✅ Функция из validation.py
- ✅ JSON только с newline между полями

Все тесты прошли успешно: **367 passed**

### Обратная совместимость

✅ **Полностью обратная совместима:**
- Валидный JSON не изменяется
- Исправления применяются только при ошибке парсинга
- Все существующие тесты проходят
- API не изменился

### Примеры

**До исправления:**
```python
broken = '{"name": "test"\n"value": 42}'
json.loads(broken)  # JSONDecodeError
```

**После исправления:**
```python
from core.infrastructure.providers.llm.json_parser import _fix_missing_commas

broken = '{"name": "test"\n"value": 42}'
fixed = _fix_missing_commas(broken)  # '{"name": "test",\n"value": 42}'
data = json.loads(fixed)  # ✅ {"name": "test", "value": 42}
```
