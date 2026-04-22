"""
Тесты для исправления отсутствующих запятых в JSON.
"""
import pytest
import json
from core.infrastructure.providers.llm.json_parser import _fix_missing_commas as fix_commas_parser
from core.agent.behaviors.react.validation import _fix_missing_commas_simple


class TestMissingCommasFix:
    """Тесты для функции исправления запятых."""

    def test_fix_missing_commas_string_values(self):
        """Исправление запятых между строковыми значениями."""
        broken = '''{
  "field1": "value1"
  "field2": "value2"
}'''
        
        # Проверяем что теперь парсится
        fixed = fix_commas_parser(broken)
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
        
        fixed = fix_commas_parser(broken)
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
        
        fixed = fix_commas_parser(broken)
        data = json.loads(fixed)
        assert data["outer"]["inner"] == "value"
        assert data["next_field"] == "test"

    def test_fix_missing_commas_arrays(self):
        """Исправление запятых после массивов."""
        broken = '''{
  "items": [1, 2, 3]
  "next": "value"
}'''
        
        fixed = fix_commas_parser(broken)
        data = json.loads(fixed)
        assert data["items"] == [1, 2, 3]
        assert data["next"] == "value"

    def test_fix_missing_commas_null_values(self):
        """Исправление запятых после null значений."""
        broken = '''{
  "field1": null
  "field2": "value"
}'''
        
        fixed = fix_commas_parser(broken)
        data = json.loads(fixed)
        assert data["field1"] is None
        assert data["field2"] == "value"

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
        
        fixed = fix_commas_parser(broken)
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
        
        fixed = fix_commas_parser(broken)
        data = json.loads(fixed)
        assert data["user"]["name"] == "John"
        assert data["user"]["age"] == 30
        assert len(data["items"]) == 2
        assert data["total"] == 100

    def test_valid_json_unchanged(self):
        """Валидный JSON не должен изменяться (нет отсутствующих запятых)."""
        valid = '''{
  "field1": "value1",
  "field2": "value2"
}'''
        
        fixed = fix_commas_parser(valid)
        
        # Валидный JSON с запятыми не должен измениться
        assert fixed == valid
        data = json.loads(fixed)
        assert data["field1"] == "value1"
        assert data["field2"] == "value2"

    def test_json_with_only_newlines_between_fields(self):
        """JSON где поля разделены только newline без запятых."""
        broken = '{"key1":"val1"\n"key2":"val2"\n"key3":"val3"}'
        
        fixed = fix_commas_parser(broken)
        data = json.loads(fixed)
        
        assert data["key1"] == "val1"
        assert data["key2"] == "val2"
        assert data["key3"] == "val3"
