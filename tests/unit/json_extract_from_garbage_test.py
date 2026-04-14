"""
Тесты для функции извлечения валидного JSON из мусора.
"""
import pytest
import json
from core.infrastructure.providers.llm.json_parser import _extract_and_fix_json
from core.components.services.json_parsing.service import JsonParsingService


class TestExtractAndFixJson:
    """Тесты для функции извлечения JSON из строки с мусором."""

    def test_extract_json_with_trailing_text(self):
        """Извлечение JSON с trailing текстом после."""
        dirty = '{"key": "value"} extra text here'
        result = _extract_and_fix_json(dirty)
        
        assert result == '{"key": "value"}'
        data = json.loads(result)
        assert data["key"] == "value"

    def test_extract_json_with_multiple_objects(self):
        """Извлечение первого валидного JSON из нескольких."""
        dirty = '{"first": 1} {"second": 2}'
        result = _extract_and_fix_json(dirty)
        
        # Должен извлечь первый объект
        assert result == '{"first": 1}'
        data = json.loads(result)
        assert data["first"] == 1

    def test_extract_json_with_garbage_inside(self):
        """JSON с мусором внутри (незакрытые скобки)."""
        dirty = '{"key": "value"} random {"garbage": true}'
        result = _extract_and_fix_json(dirty)
        
        # Должен извлечь первый валидный JSON
        assert result == '{"key": "value"}'
        data = json.loads(result)
        assert data["key"] == "value"

    def test_extract_nested_json(self):
        """Извлечение вложенного JSON."""
        dirty = '{"user": {"name": "John"}} garbage text'
        result = _extract_and_fix_json(dirty)
        
        assert result == '{"user": {"name": "John"}}'
        data = json.loads(result)
        assert data["user"]["name"] == "John"

    def test_extract_json_with_array(self):
        """Извлечение JSON с массивом."""
        dirty = '{"items": [1, 2, 3]} extra'
        result = _extract_and_fix_json(dirty)
        
        assert result == '{"items": [1, 2, 3]}'
        data = json.loads(result)
        assert data["items"] == [1, 2, 3]

    def test_extract_valid_json_unchanged(self):
        """Валидный JSON без мусора не изменяется."""
        clean = '{"key": "value"}'
        result = _extract_and_fix_json(clean)
        
        assert result == clean

    def test_extract_with_newlines_garbage(self):
        """Извлечение с мусором из переносов."""
        dirty = '{"key": "value"}\n\n\nsome\ngarbage\nhere'
        result = _extract_and_fix_json(dirty)
        
        assert result == '{"key": "value"}'

    def test_extract_with_special_characters(self):
        """Извлечение JSON со специальными символами в строках."""
        dirty = '{"text": "Hello {world}"} garbage'
        result = _extract_and_fix_json(dirty)
        
        assert result == '{"text": "Hello {world}"}'
        data = json.loads(result)
        assert data["text"] == "Hello {world}"

    def test_extract_with_escaped_quotes(self):
        """Извлечение JSON с экранированными кавычками."""
        dirty = '{"text": "He said \\"hello\\""} garbage'
        result = _extract_and_fix_json(dirty)
        
        assert result == '{"text": "He said \\"hello\\""}'
        data = json.loads(result)
        assert data["text"] == 'He said "hello"'

    def test_extract_missing_closing_brace(self):
        """Извлечение с отсутствующей закрывающей скобкой."""
        dirty = '{"key": "value"\n\n\n'
        result = _extract_and_fix_json(dirty)
        
        # Должен добавить }
        assert result == '{"key": "value"}'
        data = json.loads(result)
        assert data["key"] == "value"

    def test_extract_complex_nested_missing_brackets(self):
        """Извлечение сложной структуры с мусором."""
        dirty = '{"user": {"name": "John"}, "items": [1, 2, 3]} extra text'
        result = _extract_and_fix_json(dirty)
        
        # Должен извлечь валидный JSON
        data = json.loads(result)
        assert data["user"]["name"] == "John"
        assert data["items"] == [1, 2, 3]

    def test_extract_empty_object(self):
        """Извлечение пустого объекта."""
        dirty = '{} garbage'
        result = _extract_and_fix_json(dirty)
        
        assert result == '{}'
        data = json.loads(result)
        assert data == {}

    def test_extract_empty_array(self):
        """Извлечение пустого массива."""
        dirty = '[] garbage'
        result = _extract_and_fix_json(dirty)
        
        assert result == '[]'
        data = json.loads(result)
        assert data == []

    def test_extract_no_brackets(self):
        """Строка без скобок возвращает None."""
        dirty = 'just plain text'
        result = _extract_and_fix_json(dirty)
        
        assert result is None

    def test_extract_empty_string(self):
        """Пустая строка возвращает None."""
        result = _extract_and_fix_json('')
        assert result is None

    def test_complex_real_world_case(self):
        """Реальный кейс: LLM зациклился с мусором."""
        dirty = '''{"thought": "Let me analyze this",
"confidence": 0.85,
"items": [
  {"id": 1, "name": "Item 1"},
  {"id": 2, "name": "Item 2"}
]}

I think this is correct. Let me add some more explanation...
The analysis shows that...

random text here
more garbage
'''
        result = _extract_and_fix_json(dirty)
        
        # Должен извлечь только JSON
        data = json.loads(result)
        assert data["thought"] == "Let me analyze this"
        assert data["confidence"] == 0.85
        assert len(data["items"]) == 2
        assert data["items"][0]["name"] == "Item 1"


class TestJsonParsingServiceWithExtraction:
    """Интеграционные тесты сервиса с извлечением JSON."""

    @pytest.mark.asyncio
    async def test_parse_json_with_garbage(self):
        """Парсинг JSON с мусором через сервис."""
        # Создаём мок сервиса без component_config
        # Тестируем только метод извлечения напрямую
        from core.infrastructure.providers.llm.json_parser import (
            _extract_and_fix_json,
            _fix_missing_commas,
            _fix_missing_closing_brackets
        )
        
        dirty = '{"name": "test"} extra garbage'
        
        # Извлекаем
        extracted = _extract_and_fix_json(dirty)
        assert extracted == '{"name": "test"}'
        
        # Парсим
        data = json.loads(extracted)
        assert data["name"] == "test"

    @pytest.mark.asyncio
    async def test_parse_heavily_broken_json(self):
        """Парсинг сильно сломанного JSON."""
        from core.infrastructure.providers.llm.json_parser import (
            _fix_missing_commas,
            _fix_missing_closing_brackets
        )
        
        dirty = '''{
  "name": "test"
  "value": 42
  "nested": {"key": "val"}
} garbage random text'''
        
        # Применяем все исправления
        extracted = _extract_and_fix_json(dirty)
        fixed = _fix_missing_commas(extracted)
        fixed = _fix_missing_closing_brackets(fixed)
        
        data = json.loads(fixed)
        assert data["name"] == "test"
        assert data["value"] == 42
        assert data["nested"]["key"] == "val"
