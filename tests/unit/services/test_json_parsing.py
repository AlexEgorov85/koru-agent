"""
Юнит-тесты для JsonParsingService.

ПРОВЕРКИ:
1. Извлечение JSON из markdown блоков
2. Извлечение JSON по скобкам
3. Парсинг валидного/невалидного JSON
4. Создание Pydantic модели из схемы
5. Вложенные объекты и $ref
6. Обработка ошибок валидации
"""
import pytest
import asyncio
from typing import Optional, Any, Dict
from unittest.mock import AsyncMock

from core.components.services.json_parsing.service import JsonParsingService
from core.components.services.json_parsing.types import JsonParseResult, JsonParseStatus
from core.config.component_config import ComponentConfig


# ============================================================================
# Фикстуры
# ============================================================================

@pytest.fixture
def mock_executor():
    """Создать мок executor."""
    executor = AsyncMock()
    return executor


@pytest.fixture
def json_service(mock_executor):
    """Создать JsonParsingService с мок executor."""
    config = ComponentConfig(name="json_parsing", variant_id="default")
    service = JsonParsingService(
        name="json_parsing",
        component_config=config,
        executor=mock_executor,
        application_context=None
    )
    return service


@pytest.fixture
def simple_schema():
    """Простая схема для тестов."""
    return {
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "age": {"type": "integer"},
            "active": {"type": "boolean"}
        },
        "required": ["name"]
    }


@pytest.fixture
def nested_schema():
    """Схема с вложенными объектами."""
    return {
        "type": "object",
        "properties": {
            "thought": {"type": "string"},
            "analysis": {
                "type": "object",
                "properties": {
                    "goal": {"type": "string"},
                    "complexity": {"type": "integer"}
                },
                "required": ["goal"]
            },
            "confidence": {"type": "number"}
        },
        "required": ["thought", "analysis"]
    }


@pytest.fixture
def ref_schema():
    """Схема с $ref ссылками."""
    return {
        "type": "object",
        "properties": {
            "action": {"type": "string"},
            "params": {"$ref": "#/$defs/ParamsDef"}
        },
        "required": ["action", "params"],
        "$defs": {
            "ParamsDef": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "limit": {"type": "integer"}
                },
                "required": ["query"]
            }
        }
    }


# ============================================================================
# Тесты: extract_json
# ============================================================================

@pytest.mark.asyncio
async def test_extract_json_from_markdown_json_block(json_service):
    """Извлечение JSON из ```json блока."""
    content = '''Вот мой ответ:
```json
{"name": "Test", "age": 25}
```
Конец.'''
    result = await json_service._action_extract_json({"content": content})
    assert result["status"] == "success"
    assert '"name": "Test"' in result["extracted_json"]


@pytest.mark.asyncio
async def test_extract_json_from_plain_markdown_block(json_service):
    """Извлечение JSON из ``` блока без указания языка."""
    content = '''Ответ:
```
{"key": "value"}
```
'''
    result = await json_service._action_extract_json({"content": content})
    assert result["status"] == "success"
    assert result["extracted_json"] == '{"key": "value"}'


@pytest.mark.asyncio
async def test_extract_json_from_braces(json_service):
    """Извлечение JSON по скобкам {}."""
    content = 'Некий текст {"action": "test", "params": {}} и ещё текст'
    result = await json_service._action_extract_json({"content": content})
    assert result["status"] == "success"
    assert result["extracted_json"] == '{"action": "test", "params": {}}'


@pytest.mark.asyncio
async def test_extract_json_from_brackets(json_service):
    """Извлечение JSON по скобкам []."""
    content = 'Массив: [1, 2, 3] конец'
    result = await json_service._action_extract_json({"content": content})
    assert result["status"] == "success"
    assert result["extracted_json"] == '[1, 2, 3]'


@pytest.mark.asyncio
async def test_extract_json_no_json_found(json_service):
    """Ошибка когда JSON не найден."""
    content = 'Просто текст без какого-либо JSON'
    result = await json_service._action_extract_json({"content": content})
    assert result["status"] == JsonParseStatus.EXTRACT_ERROR.value
    assert result["error_type"] == "no_json_found"


@pytest.mark.asyncio
async def test_extract_json_empty_input(json_service):
    """Ошибка при пустом входе."""
    result = await json_service._action_extract_json({"content": ""})
    assert result["status"] == JsonParseStatus.EXTRACT_ERROR.value
    assert result["error_type"] == "empty_input"


# ============================================================================
# Тесты: parse_json
# ============================================================================

@pytest.mark.asyncio
async def test_parse_json_valid(json_service):
    """Парсинг валидного JSON."""
    raw = '{"name": "Alice", "age": 30, "active": true}'
    result = await json_service._action_parse_json({"raw": raw})
    assert result["status"] == "success"
    assert result["parsed_data"]["name"] == "Alice"
    assert result["parsed_data"]["age"] == 30


@pytest.mark.asyncio
async def test_parse_json_array(json_service):
    """Парсинг JSON массива."""
    raw = '[1, 2, 3, 4, 5]'
    result = await json_service._action_parse_json({"raw": raw})
    assert result["status"] == "success"
    assert result["parsed_data"] == [1, 2, 3, 4, 5]


@pytest.mark.asyncio
async def test_parse_json_invalid(json_service):
    """Парсинг невалидного JSON."""
    raw = '{"name": "Alice", age: 30}'  # Без кавычек у ключа
    result = await json_service._action_parse_json({"raw": raw})
    assert result["status"] == JsonParseStatus.PARSE_ERROR.value
    assert result["error_type"] == "json_decode_error"
    assert result["error_details"] is not None


@pytest.mark.asyncio
async def test_parse_json_empty(json_service):
    """Парсинг пустой строки."""
    result = await json_service._action_parse_json({"raw": ""})
    assert result["status"] == JsonParseStatus.PARSE_ERROR.value


# ============================================================================
# Тесты: parse_to_model
# ============================================================================

@pytest.mark.asyncio
async def test_parse_to_model_simple(json_service, simple_schema):
    """Полный цикл с простой схемой."""
    raw_response = '{"name": "Bob", "age": 25, "active": true}'
    result = await json_service._action_parse_to_model({
        "raw_response": raw_response,
        "schema_def": simple_schema,
        "model_name": "SimpleModel"
    })
    assert result["status"] == "success"
    assert result["parsed_data"]["name"] == "Bob"
    assert result["pydantic_model_data"] is not None  # Сериализованная модель


@pytest.mark.asyncio
async def test_parse_to_model_nested(json_service, nested_schema):
    """Полный цикл с вложенными объектами."""
    raw_response = '''
```json
{"thought": "Think...", "analysis": {"goal": "Find books", "complexity": 5}, "confidence": 0.9}
```
'''
    result = await json_service._action_parse_to_model({
        "raw_response": raw_response,
        "schema_def": nested_schema,
        "model_name": "NestedModel"
    })
    assert result["status"] == "success"
    assert result["parsed_data"]["thought"] == "Think..."
    assert result["parsed_data"]["analysis"]["goal"] == "Find books"


@pytest.mark.asyncio
async def test_parse_to_model_with_ref(json_service, ref_schema):
    """Полный цикл с $ref ссылками."""
    raw_response = '{"action": "search", "params": {"query": "books", "limit": 10}}'
    result = await json_service._action_parse_to_model({
        "raw_response": raw_response,
        "schema_def": ref_schema,
        "model_name": "RefModel"
    })
    assert result["status"] == "success"
    assert result["parsed_data"]["action"] == "search"
    assert result["parsed_data"]["params"]["query"] == "books"


@pytest.mark.asyncio
async def test_parse_to_model_validation_error(json_service, simple_schema):
    """Ошибка валидации — обязательное поле отсутствует."""
    raw_response = '{"age": 25}'  # Нет обязательного "name"
    result = await json_service._action_parse_to_model({
        "raw_response": raw_response,
        "schema_def": simple_schema,
        "model_name": "SimpleModel"
    })
    assert result["status"] == JsonParseStatus.VALIDATION_ERROR.value
    assert result["error_type"] == "validation_error"
    assert result["error_details"] is not None
    assert len(result["error_details"]) > 0


@pytest.mark.asyncio
async def test_parse_to_model_wrong_type(json_service, simple_schema):
    """Ошибка валидации — неправильный тип поля."""
    raw_response = '{"name": "Bob", "age": "not_a_number"}'
    result = await json_service._action_parse_to_model({
        "raw_response": raw_response,
        "schema_def": simple_schema,
        "model_name": "SimpleModel"
    })
    assert result["status"] == JsonParseStatus.VALIDATION_ERROR.value


@pytest.mark.asyncio
async def test_parse_to_model_no_schema(json_service):
    """Без схемы — возвращает сырые данные."""
    raw_response = '{"key": "value", "nested": {"a": 1}}'
    result = await json_service._action_parse_to_model({
        "raw_response": raw_response,
        "schema_def": {},
        "model_name": "AnyModel"
    })
    assert result["status"] == "success"
    assert result["parsed_data"]["key"] == "value"


@pytest.mark.asyncio
async def test_parse_to_model_processing_steps(json_service, simple_schema):
    """Проверка что processing_steps заполняется."""
    raw_response = '{"name": "Test"}'
    result = await json_service._action_parse_to_model({
        "raw_response": raw_response,
        "schema_def": simple_schema,
        "model_name": "SimpleModel"
    })
    assert len(result["processing_steps"]) > 0
    # Проверяем что шаги содержат осмысленную информацию
    steps_str = " ".join(result["processing_steps"])
    assert "Вход:" in steps_str or "симв" in steps_str


# ============================================================================
# Тесты: Model caching
# ============================================================================

@pytest.mark.asyncio
async def test_model_caching(json_service, simple_schema):
    """Кэш моделей работает — вторая попытка быстрее."""
    raw_response = '{"name": "CacheTest", "age": 1}'
    
    # Первый вызов — модель создаётся
    result1 = await json_service._action_parse_to_model({
        "raw_response": raw_response,
        "schema_def": simple_schema,
        "model_name": "CachedModel"
    })
    assert result1["status"] == "success"
    
    # Второй вызов — модель из кэша
    result2 = await json_service._action_parse_to_model({
        "raw_response": raw_response,
        "schema_def": simple_schema,
        "model_name": "CachedModel"
    })
    assert result2["status"] == "success"
    assert len(json_service._model_cache) == 1


# ============================================================================
# Тесты: JsonParseResult.to_dict()
# ============================================================================

def test_parse_result_to_dict():
    """Сериализация JsonParseResult."""
    result = JsonParseResult(
        status=JsonParseStatus.SUCCESS,
        raw_input='{"test": 1}',
        extracted_json='{"test": 1}',
        parsed_data={"test": 1},
        processing_steps=["step1", "step2"]
    )
    d = result.to_dict()
    assert d["status"] == "success"
    assert d["parsed_data"] == {"test": 1}
    assert d["processing_steps"] == ["step1", "step2"]
    assert "pydantic_model" not in d  # Исключено из сериализации
