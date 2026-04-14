"""
Тесты для исправления отсутствующих запятых в JSON.
"""
import pytest
import json
from core.components.services.json_parsing.service import JsonParsingService
from core.infrastructure.providers.llm.json_parser import _fix_missing_commas as fix_commas_parser
from core.agent.strategies.react.validation import _fix_missing_commas_simple


class TestMissingCommasFix:
    """Тесты для функции исправления запятых в JsonParsingService."""

    def test_fix_missing_commas_string_values(self):
        """Исправление запятых между строковыми значениями."""
        broken = '''{
  "field1": "value1"
  "field2": "value2"
}'''
        expected = '''{
  "field1": "value1",
  "field2": "value2"
}'''
        service = JsonParsingService()
        fixed = service._fix_missing_commas(broken)
        assert fixed == expected
        
        # Проверяем что теперь парсится
        data = json.loads(fixed)
        assert data["field1"] == "value1"
        assert data["field2"] == "value2"

    def test_fix_missing_commas_mixed_types(self):
        """Исправление запятых между разными типами значений."""
        broken = '''{
  "name": "test"
  "count": 42
  "active": true
  "next": "value"
}'''
        service = JsonParsingService()
        fixed = service._fix_missing_commas(broken)
        
        data = json.loads(fixed)
        assert data["name"] == "test"
        assert data["count"] == 42
        assert data["active"] is True
        assert data["next"] == "value"

    def test_fix_missing_commas_nested_objects(self):
        """Исправление запятых после вложенных объектов."""
        broken = '''{
  "outer": {
    "inner": "value"
  }
  "next_field": "test"
}'''
        service = JsonParsingService()
        fixed = service._fix_missing_commas(broken)
        
        data = json.loads(fixed)
        assert data["outer"]["inner"] == "value"
        assert data["next_field"] == "test"

    def test_fix_missing_commas_arrays(self):
        """Исправление запятых после массивов."""
        broken = '''{
  "items": [1, 2, 3]
  "next": "value"
}'''
        service = JsonParsingService()
        fixed = service._fix_missing_commas(broken)
        
        data = json.loads(fixed)
        assert data["items"] == [1, 2, 3]
        assert data["next"] == "value"

    def test_fix_missing_commas_null_values(self):
        """Исправление запятых после null значений."""
        broken = '''{
  "field1": null
  "field2": "value"
}'''
        service = JsonParsingService()
        fixed = service._fix_missing_commas(broken)
        
        data = json.loads(fixed)
        assert data["field1"] is None
        assert data["field2"] == "value"

    def test_valid_json_unchanged(self):
        """Валидный JSON не должен изменяться."""
        valid = '''{
  "field1": "value1",
  "field2": "value2"
}'''
        service = JsonParsingService()
        fixed = service._fix_missing_commas(valid)
        
        # Валидный JSON не должен измениться (нет отсутствующих запятых)
        assert fixed == valid

    def test_fix_commas_parser_function(self):
        """Тест функции из json_parser.py."""
        broken = '''{
  "field1": "value1"
  "field2": "value2"
}'''
        fixed = fix_commas_parser(broken)
        
        data = json.loads(fixed)
        assert data["field1"] == "value1"
        assert data["field2"] == "value2"

    def test_fix_commas_validation_function(self):
        """Тест функции из validation.py."""
        broken = '''{
  "field1": "value1"
  "field2": "value2"
}'''
        fixed = _fix_missing_commas_simple(broken)
        
        data = json.loads(fixed)
        assert data["field1"] == "value1"
        assert data["field2"] == "value2"

    def test_multiple_missing_commas(self):
        """Множественные отсутствующие запятые."""
        broken = '''{
  "a": 1
  "b": 2
  "c": 3
  "d": 4
}'''
        service = JsonParsingService()
        fixed = service._fix_missing_commas(broken)
        
        data = json.loads(fixed)
        assert data == {"a": 1, "b": 2, "c": 3, "d": 4}

    def test_complex_nested_structure(self):
        """Сложная вложенная структура с отсутствующими запятыми."""
        broken = '''{
  "user": {
    "name": "John"
    "age": 30
  }
  "items": [
    {"id": 1}
    {"id": 2}
  ]
  "total": 100
}'''
        service = JsonParsingService()
        fixed = service._fix_missing_commas(broken)
        
        data = json.loads(fixed)
        assert data["user"]["name"] == "John"
        assert data["user"]["age"] == 30
        assert len(data["items"]) == 2
        assert data["total"] == 100


class TestJsonParsingWithCommaFix:
    """Интеграционные тесты парсинга с исправлением запятых."""

    @pytest.mark.asyncio
    async def test_parse_json_with_missing_commas(self):
        """Парсинг JSON с отсутствующими запятыми через сервис."""
        service = JsonParsingService()
        
        broken_json = '''{
  "name": "test"
  "value": 42
}'''
        
        result = await service.parse_json(broken_json)
        
        assert result["status"] == "success"
        assert result["parsed_data"]["name"] == "test"
        assert result["parsed_data"]["value"] == 42

    @pytest.mark.asyncio
    async def test_parse_json_valid_no_changes(self):
        """Парсинг валидного JSON без изменений."""
        service = JsonParsingService()
        
        valid_json = '''{
  "name": "test",
  "value": 42
}'''
        
        result = await service.parse_json(valid_json)
        
        assert result["status"] == "success"
        assert result["parsed_data"]["name"] == "test"
        assert result["parsed_data"]["value"] == 42
