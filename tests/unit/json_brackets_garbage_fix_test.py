"""
Тесты для исправления отсутствующих закрывающих скобок и мусора в JSON.
"""
import pytest
import json
from core.infrastructure.providers.llm.json_parser import (
    _fix_missing_closing_brackets,
    _fix_json_trailing_garbage,
    _fix_missing_commas
)
from core.agent.strategies.react.validation import (
    _fix_missing_closing_brackets_simple,
    _fix_json_trailing_garbage_simple,
    _fix_missing_commas_simple
)


class TestMissingClosingBrackets:
    """Тесты для функции исправления отсутствующих закрывающих скобок."""

    def test_fix_missing_closing_brace(self):
        """Исправление отсутствующей закрывающей скобки объекта."""
        broken = '{"key": "value"'
        fixed = _fix_missing_closing_brackets(broken)
        
        assert fixed == '{"key": "value"}'
        data = json.loads(fixed)
        assert data["key"] == "value"

    def test_fix_missing_closing_bracket(self):
        """Исправление отсутствующей закрывающей скобки массива."""
        broken = '{"arr": [1, 2, 3'
        fixed = _fix_missing_closing_brackets(broken)
        
        assert fixed == '{"arr": [1, 2, 3]}'
        data = json.loads(fixed)
        assert data["arr"] == [1, 2, 3]

    def test_fix_nested_missing_brackets(self):
        """Исправление вложенных отсутствующих скобок."""
        broken = '{"obj": {"inner": "value"'
        fixed = _fix_missing_closing_brackets(broken)
        
        assert fixed == '{"obj": {"inner": "value"}}'
        data = json.loads(fixed)
        assert data["obj"]["inner"] == "value"

    def test_fix_complex_nested(self):
        """Исправление сложной вложенной структуры."""
        broken = '''{
  "user": {
    "name": "John",
    "items": [
      {"id": 1},
      {"id": 2}
    ]
  }
'''
        fixed = _fix_missing_closing_brackets(broken)
        
        # В этом случае скобки уже закрыты, ничего не добавится
        data = json.loads(fixed)
        assert data["user"]["name"] == "John"
        assert len(data["user"]["items"]) == 2
        assert data["user"]["items"][1]["id"] == 2

    def test_valid_json_unchanged(self):
        """Валидный JSON не должен изменяться."""
        valid = '{"key": "value", "arr": [1, 2, 3]}'
        fixed = _fix_missing_closing_brackets(valid)
        
        assert fixed == valid

    def test_fix_with_trailing_whitespace(self):
        """Исправление с trailing пробелами и переносами."""
        broken = '{"key": "value"\n\n\n   '
        fixed = _fix_missing_closing_brackets(broken)
        
        assert fixed == '{"key": "value"}'
        data = json.loads(fixed)
        assert data["key"] == "value"

    def test_fix_simple_function(self):
        """Тест упрощённой функции из validation.py."""
        broken = '{"key": "value"'
        fixed = _fix_missing_closing_brackets_simple(broken)
        
        assert fixed == '{"key": "value"}'
        data = json.loads(fixed)
        assert data["key"] == "value"


class TestTrailingGarbage:
    """Тесты для функции удаления мусора в конце JSON."""

    def test_remove_trailing_newlines(self):
        """Удаление trailing переносов."""
        dirty = '{"key": "value"}\n\n\n\n'
        clean = _fix_json_trailing_garbage(dirty)
        
        assert clean == '{"key": "value"}'
        data = json.loads(clean)
        assert data["key"] == "value"

    def test_remove_trailing_spaces(self):
        """Удаление trailing пробелов."""
        dirty = '{"key": "value"}      '
        clean = _fix_json_trailing_garbage(dirty)
        
        assert clean == '{"key": "value"}'

    def test_remove_trailing_dots(self):
        """Удаление точек после JSON."""
        dirty = '{"key": "value"}.....'
        clean = _fix_json_trailing_garbage(dirty)
        
        assert clean == '{"key": "value"}'

    def test_remove_mixed_garbage(self):
        """Удаление смешанного мусора."""
        dirty = '{"key": "value"}\n\n  \n.....  '
        clean = _fix_json_trailing_garbage(dirty)
        
        assert clean == '{"key": "value"}'

    def test_no_garbage_unchanged(self):
        """JSON без мусора не изменяется."""
        clean_json = '{"key": "value"}'
        result = _fix_json_trailing_garbage(clean_json)
        
        assert result == clean_json

    def test_simple_function(self):
        """Тест упрощённой функции из validation.py."""
        dirty = '{"key": "value"}\n\n\n'
        clean = _fix_json_trailing_garbage_simple(dirty)
        
        assert clean == '{"key": "value"}'


class TestCombinedFixes:
    """Тесты комбинированного исправления всех проблем."""

    def test_commas_and_brackets(self):
        """Отсутствующие запятые И закрывающие скобки."""
        broken = '''{
  "field1": "value1"
  "field2": "value2"
'''
        # Применяем все исправления
        fixed = _fix_missing_commas(broken)
        fixed = _fix_missing_closing_brackets(fixed)
        
        data = json.loads(fixed)
        assert data["field1"] == "value1"
        assert data["field2"] == "value2"

    def test_all_three_fixes(self):
        """Все три типа исправлений: запятые, скобки, мусор."""
        broken = '''{
  "name": "test"
  "value": 42
'''
        fixed = _fix_missing_commas(broken)
        fixed = _fix_missing_closing_brackets(fixed)
        fixed = _fix_json_trailing_garbage(fixed)
        
        data = json.loads(fixed)
        assert data["name"] == "test"
        assert data["value"] == 42

    def test_heavily_broken_json(self):
        """Сильно сломанный JSON от LLM."""
        broken = '''{
  "thought": "Let me think"
  "value": 42
'''
        fixed = _fix_missing_commas(broken)
        fixed = _fix_missing_closing_brackets(fixed)
        fixed = _fix_json_trailing_garbage(fixed)
        
        data = json.loads(fixed)
        assert data["thought"] == "Let me think"
        assert data["value"] == 42

    def test_validation_integration(self):
        """Интеграция с функциями из validation.py."""
        broken = '''{
  "key1": "val1"
  "key2": "val2"
'''
        fixed = _fix_missing_commas_simple(broken)
        fixed = _fix_missing_closing_brackets_simple(fixed)
        
        data = json.loads(fixed)
        assert data["key1"] == "val1"
        assert data["key2"] == "val2"

    def test_array_missing_brackets_and_commas(self):
        """Массив с отсутствующими скобками и запятыми."""
        broken = '[1, 2, 3'
        fixed = _fix_missing_closing_brackets(broken)
        
        data = json.loads(fixed)
        assert data == [1, 2, 3]

    def test_truncated_json(self):
        """Обрезанный JSON без конца."""
        broken = '{"user": {"name": "John", "age": 30, "email": "john@example.com"'
        fixed = _fix_missing_closing_brackets(broken)
        
        data = json.loads(fixed)
        assert data["user"]["name"] == "John"
        assert data["user"]["age"] == 30
        assert data["user"]["email"] == "john@example.com"
