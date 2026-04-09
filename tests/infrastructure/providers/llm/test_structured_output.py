"""
Тесты для structured output в LLM провайдерах.

Тестирует:
- Извлечение JSON из разных форматов ответа
- Создание Pydantic моделей из JSON Schema
- Валидацию данных
"""
import pytest
import json
from typing import Dict, Any


class TestExtractJsonFromResponse:
    """Тесты на извлечение JSON из ответов LLM."""

    def _extract_json(self, content: str) -> Dict[str, Any]:
        """Helper для извлечения JSON (копия из LlamaCppProvider)."""
        import re

        content = content.strip()

        # Попытка 1: Чистый JSON
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            pass

        # Попытка 2: JSON в markdown блоке
        markdown_pattern = r'```(?:json)?\s*({.*?})\s*```'
        match = re.search(markdown_pattern, content, re.DOTALL | re.IGNORECASE)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass

        # Попытка 3: Поиск первой { и последней }
        start_idx = content.find('{')
        end_idx = content.rfind('}') + 1
        if start_idx != -1 and end_idx > start_idx:
            json_str = content[start_idx:end_idx]
            try:
                return json.loads(json_str)
            except json.JSONDecodeError:
                pass

        raise json.JSONDecodeError(
            "Не удалось извлечь JSON из ответа",
            content,
            0
        )

    def test_clean_json(self):
        """Тест извлечения из чистого JSON."""
        content = '{"answer": "42", "confidence": 0.95}'
        result = self._extract_json(content)
        assert result == {"answer": "42", "confidence": 0.95}

    def test_json_in_markdown_block(self):
        """Тест извлечения из markdown блока."""
        content = 'Вот ответ:\n```json\n{"answer": "42", "confidence": 0.95}\n```'
        result = self._extract_json(content)
        assert result == {"answer": "42", "confidence": 0.95}

    def test_json_in_markdown_without_language(self):
        """Тест извлечения из markdown без указания языка."""
        content = '```\n{"answer": "42"}\n```'
        result = self._extract_json(content)
        assert result == {"answer": "42"}

    def test_json_with_text_before(self):
        """Тест извлечения с текстом перед JSON."""
        content = 'Я думаю что ответ такой: {"answer": "42"} потому что...'
        result = self._extract_json(content)
        assert result == {"answer": "42"}

    def test_json_with_text_after(self):
        """Тест извлечения с текстом после JSON."""
        content = '{"answer": "42"}\n\nЭто был мой ответ.'
        result = self._extract_json(content)
        assert result == {"answer": "42"}

    def test_nested_json(self):
        """Тест извлечения с вложенным JSON."""
        content = '''
        Вот результат:
        ```json
        {
            "plan": [
                {"step": 1, "action": "search"},
                {"step": 2, "action": "analyze"}
            ]
        }
        ```
        '''
        result = self._extract_json(content)
        assert "plan" in result
        assert len(result["plan"]) == 2
        assert result["plan"][0]["step"] == 1

    def test_json_with_cyrillic(self):
        """Тест извлечения с кириллицей."""
        content = '{"answer": "Привет мир", "status": "успех"}'
        result = self._extract_json(content)
        assert result == {"answer": "Привет мир", "status": "успех"}

    def test_invalid_json_raises(self):
        """Тест что невалидный JSON вызывает ошибку."""
        content = 'Это не JSON совсем'
        with pytest.raises(json.JSONDecodeError):
            self._extract_json(content)

    def test_malformed_json_raises(self):
        """Тест что malformed JSON вызывает ошибку."""
        content = '{"answer": "42",}'  # Лишняя запятая
        with pytest.raises(json.JSONDecodeError):
            self._extract_json(content)

    def test_empty_object(self):
        """Тест извлечения пустого объекта."""
        content = '{}'
        result = self._extract_json(content)
        assert result == {}

    def test_complex_nested_structure(self):
        """Тест извлечения сложной вложенной структуры."""
        content = '''
        Анализ завершён. Результат:
        ```json
        {
            "summary": "Данные обработаны",
            "metrics": {
                "accuracy": 0.95,
                "precision": 0.92,
                "recall": 0.89
            },
            "tags": ["ml", "analysis", "complete"],
            "metadata": {
                "version": "1.0",
                "processed": true
            }
        }
        ```
        Конец сообщения.
        '''
        result = self._extract_json(content)
        assert result["summary"] == "Данные обработаны"
        assert result["metrics"]["accuracy"] == 0.95
        assert "ml" in result["tags"]
        assert result["metadata"]["processed"] is True


class TestCreatePydanticFromSchema:
    """Тесты на создание Pydantic моделей из JSON Schema."""

    def _create_model(self, model_name: str, schema_def: Dict[str, Any]):
        """Helper для создания модели (копия из LlamaCppProvider)."""
        from pydantic import create_model, Field
        from typing import List, Optional, Any

        def build_field(field_schema: Dict) -> tuple:
            field_type = field_schema.get('type', 'string')
            description = field_schema.get('description', '')
            default = field_schema.get('default', ...)

            type_mapping = {
                'string': str,
                'integer': int,
                'number': float,
                'boolean': bool,
                'array': List[Any],
                'object': Dict[str, Any]
            }

            python_type = type_mapping.get(field_type, Any)

            if description:
                field_info = Field(default=default, description=description) if default is not ... else Field(description=description)
            else:
                field_info = Field(default=default) if default is not ... else Field()

            return (python_type, field_info)

        fields = {}
        properties = schema_def.get('properties', {})
        required = schema_def.get('required', [])

        for field_name, field_schema in properties.items():
            if field_name in required:
                fields[field_name] = build_field(field_schema)
            else:
                field_type, field_info = build_field(field_schema)
                fields[field_name] = (Optional[field_type], field_info)

        return create_model(model_name, **fields)

    def test_simple_string_fields(self):
        """Тест модели с простыми string полями."""
        schema = {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "description": {"type": "string"}
            },
            "required": ["name"]
        }

        Model = self._create_model("TestModel", schema)
        instance = Model(name="Test", description="A test model")

        assert instance.name == "Test"
        assert instance.description == "A test model"

    def test_mixed_types(self):
        """Тест модели со смешанными типами."""
        schema = {
            "type": "object",
            "properties": {
                "id": {"type": "integer"},
                "score": {"type": "number"},
                "active": {"type": "boolean"},
                "name": {"type": "string"}
            },
            "required": ["id", "name"]
        }

        Model = self._create_model("MixedModel", schema)
        instance = Model(id=42, score=3.14, active=True, name="Test")

        assert instance.id == 42
        assert abs(instance.score - 3.14) < 0.001
        assert instance.active is True
        assert instance.name == "Test"

    def test_optional_fields(self):
        """Тест модели с необязательными полями."""
        schema = {
            "type": "object",
            "properties": {
                "required_field": {"type": "string"},
                "optional_field": {"type": "string", "default": "default_value"}
            },
            "required": ["required_field"]
        }

        Model = self._create_model("OptionalModel", schema)
        instance = Model(required_field="value")

        assert instance.required_field == "value"
        assert instance.optional_field == "default_value"

    def test_with_descriptions(self):
        """Тест модели с описаниями полей."""
        schema = {
            "type": "object",
            "properties": {
                "email": {
                    "type": "string",
                    "description": "Email адрес пользователя"
                },
                "age": {
                    "type": "integer",
                    "description": "Возраст в годах"
                }
            },
            "required": ["email"]
        }

        Model = self._create_model("UserModel", schema)
        instance = Model(email="test@example.com", age=25)

        assert instance.email == "test@example.com"
        assert instance.age == 25

        # Проверяем что описания есть в модели
        fields = instance.model_fields
        assert "Email адрес пользователя" in fields["email"].description
        assert "Возраст в годах" in fields["age"].description

    def test_validation_error_on_missing_required(self):
        """Тест что отсутствует required поле вызывает ошибку."""
        schema = {
            "type": "object",
            "properties": {
                "name": {"type": "string"}
            },
            "required": ["name"]
        }

        Model = self._create_model("RequiredModel", schema)

        with pytest.raises(Exception):  # ValidationError
            Model()  # Без обязательного поля

    def test_nested_object_field(self):
        """Тест модели с вложенным объектом."""
        schema = {
            "type": "object",
            "properties": {
                "user": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "email": {"type": "string"}
                    }
                }
            },
            "required": ["user"]
        }

        Model = self._create_model("NestedModel", schema)
        instance = Model(user={"name": "John", "email": "john@example.com"})

        assert instance.user["name"] == "John"
        assert instance.user["email"] == "john@example.com"
