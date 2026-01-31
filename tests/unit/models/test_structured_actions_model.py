"""
Тесты для модели StructuredActions (ActionSchema, ActionSchemaRegistry, ActionValidator).
"""
import pytest
from models.structured_actions import ActionSchema, ActionSchemaRegistry, ActionValidator, StructuredActionError


class TestActionSchemaModel:
    """Тесты для модели ActionSchema."""
    
    def test_action_schema_creation(self):
        """Тест создания ActionSchema."""
        schema = ActionSchema(
            name="test_action",
            description="Тестовое действие",
            parameters_schema={
                "param1": {"type": "string", "description": "Строковый параметр"},
                "param2": {"type": "number", "description": "Числовой параметр"}
            },
            required_fields=["param1"]
        )
        
        assert schema.name == "test_action"
        assert schema.description == "Тестовое действие"
        assert schema.parameters_schema == {
            "param1": {"type": "string", "description": "Строковый параметр"},
            "param2": {"type": "number", "description": "Числовой параметр"}
        }
        assert schema.required_fields == ["param1"]
    
    def test_action_schema_with_optional_fields(self):
        """Тест создания ActionSchema с опциональными полями."""
        schema = ActionSchema(
            name="advanced_action",
            description="Продвинутое действие",
            parameters_schema={"param": "value"},
            required_fields=["param"],
            examples=[
                {"param": "example1"},
                {"param": "example2"}
            ],
            category="test_category",
            version="1.0.0"
        )
        
        assert schema.examples == [{"param": "example1"}, {"param": "example2"}]
        assert schema.category == "test_category"
        assert schema.version == "1.0.0"
    
    def test_action_schema_default_values(self):
        """Тест значений по умолчанию для ActionSchema."""
        schema = ActionSchema(
            name="minimal_action",
            description="Минимальное действие",
            parameters_schema={},
            required_fields=[]
        )
        
        assert schema.examples == []          # значение по умолчанию
        assert schema.category is None        # значение по умолчанию
        assert schema.version is None         # значение по умолчанию
        assert schema.deprecated is False     # значение по умолчанию
    
    def test_action_schema_equality(self):
        """Тест равенства ActionSchema."""
        schema1 = ActionSchema(
            name="test_action",
            description="Тестовое действие",
            parameters_schema={"param": "value"},
            required_fields=["param"]
        )
        
        schema2 = ActionSchema(
            name="test_action",
            description="Тестовое действие",
            parameters_schema={"param": "value"},
            required_fields=["param"]
        )
        
        schema3 = ActionSchema(
            name="different_action",  # другое имя
            description="Тестовое действие",
            parameters_schema={"param": "value"},
            required_fields=["param"]
        )
        
        assert schema1 == schema2  # одинаковые по значению
        assert schema1 != schema3  # разные name
        assert schema2 != schema3  # разные name
    
    def test_action_schema_serialization(self):
        """Тест сериализации ActionSchema."""
        schema = ActionSchema(
            name="serialize_action",
            description="Действие для сериализации",
            parameters_schema={"serialize_param": "serialize_value"},
            required_fields=["serialize_param"],
            examples=[{"serialize_param": "test"}],
            category="serialize_category",
            version="1.0.0"
        )
        
        data = schema.model_dump()
        
        assert data["name"] == "serialize_action"
        assert data["description"] == "Действие для сериализации"
        assert data["parameters_schema"] == {"serialize_param": "serialize_value"}
        assert data["required_fields"] == ["serialize_param"]
        assert data["examples"] == [{"serialize_param": "test"}]
        assert data["category"] == "serialize_category"
        assert data["version"] == "1.0.0"
    
    def test_action_schema_from_dict(self):
        """Тест создания ActionSchema из словаря."""
        data = {
            "name": "dict_action",
            "description": "Действие из словаря",
            "parameters_schema": {"dict_param": "dict_value"},
            "required_fields": ["dict_param"],
            "examples": [{"dict_param": "example"}],
            "category": "dict_category",
            "version": "2.0.0"
        }
        
        schema = ActionSchema.model_validate(data)
        
        assert schema.name == "dict_action"
        assert schema.description == "Действие из словаря"
        assert schema.parameters_schema == {"dict_param": "dict_value"}
        assert schema.required_fields == ["dict_param"]
        assert schema.examples == [{"dict_param": "example"}]
        assert schema.category == "dict_category"
        assert schema.version == "2.0.0"


class TestActionSchemaRegistryModel:
    """Тесты для модели ActionSchemaRegistry."""
    
    def test_registry_initialization(self):
        """Тест инициализации ActionSchemaRegistry."""
        registry = ActionSchemaRegistry()
        
        assert registry.schemas == {}
        assert isinstance(registry.schemas, dict)
    
    def test_register_schema(self):
        """Тест регистрации схемы."""
        registry = ActionSchemaRegistry()
        
        schema = ActionSchema(
            name="test_action",
            description="Тестовое действие",
            parameters_schema={"param": "value"},
            required_fields=["param"]
        )
        
        registry.register_schema(schema)
        
        assert "test_action" in registry.schemas
        assert registry.schemas["test_action"] == schema
    
    def test_register_schema_duplicate_name(self):
        """Тест регистрации схемы с дублирующимся именем."""
        registry = ActionSchemaRegistry()
        
        schema1 = ActionSchema(
            name="duplicate_action",
            description="Первая схема",
            parameters_schema={"param1": "value1"},
            required_fields=["param1"]
        )
        
        schema2 = ActionSchema(
            name="duplicate_action",
            description="Вторая схема",
            parameters_schema={"param2": "value2"},
            required_fields=["param2"]
        )
        
        registry.register_schema(schema1)
        
        # Регистрируем схему с тем же именем - должна заменить предыдущую
        registry.register_schema(schema2)
        
        assert registry.schemas["duplicate_action"] == schema2  # последняя должна остаться
    
    def test_get_schema_found(self):
        """Тест получения схемы - схема найдена."""
        registry = ActionSchemaRegistry()
        
        schema = ActionSchema(
            name="found_action",
            description="Найденная схема",
            parameters_schema={"param": "value"},
            required_fields=["param"]
        )
        
        registry.register_schema(schema)
        
        retrieved_schema = registry.get_schema("found_action")
        
        assert retrieved_schema == schema
    
    def test_get_schema_not_found(self):
        """Тест получения схемы - схема не найдена."""
        registry = ActionSchemaRegistry()
        
        retrieved_schema = registry.get_schema("nonexistent_action")
        
        assert retrieved_schema is None
    
    def test_get_schema_case_insensitive(self):
        """Тест получения схемы - регистронезависимый поиск."""
        registry = ActionSchemaRegistry()
        
        schema = ActionSchema(
            name="case_sensitive_action",
            description="Схема с регистрозависимым именем",
            parameters_schema={"param": "value"},
            required_fields=["param"]
        )
        
        registry.register_schema(schema)
        
        retrieved_schema = registry.get_schema("CASE_SENSITIVE_ACTION")
        
        assert retrieved_schema == schema
    
    def test_list_all_schemas(self):
        """Тест получения списка всех схем."""
        registry = ActionSchemaRegistry()
        
        # Регистрируем несколько схем
        schema1 = ActionSchema(
            name="action1",
            description="Первое действие",
            parameters_schema={"param1": "value1"},
            required_fields=["param1"]
        )
        
        schema2 = ActionSchema(
            name="action2",
            description="Второе действие",
            parameters_schema={"param2": "value2"},
            required_fields=["param2"]
        )
        
        registry.register_schema(schema1)
        registry.register_schema(schema2)
        
        all_schemas = registry.list_all_schemas()
        
        assert len(all_schemas) == 2
        assert "action1" in all_schemas
        assert "action2" in all_schemas
        assert all_schemas["action1"] == schema1
        assert all_schemas["action2"] == schema2
    
    def test_list_all_schemas_empty(self):
        """Тест получения списка всех схем - реестр пуст."""
        registry = ActionSchemaRegistry()
        
        all_schemas = registry.list_all_schemas()
        
        assert all_schemas == {}


class TestActionValidatorModel:
    """Тесты для модели ActionValidator."""
    
    def test_validator_initialization(self):
        """Тест инициализации ActionValidator."""
        validator = ActionValidator()
        
        assert validator.schema_registry is not None
        assert isinstance(validator.schema_registry, ActionSchemaRegistry)
    
    def test_validate_action_with_valid_data(self):
        """Тест валидации действия с корректными данными."""
        validator = ActionValidator()
        
        # Создаем схему для валидации
        schema = ActionSchema(
            name="valid_action",
            description="Валидное действие",
            parameters_schema={
                "name": {"type": "string", "description": "Имя пользователя"},
                "age": {"type": "number", "description": "Возраст пользователя"}
            },
            required_fields=["name"]
        )
        
        validator.schema_registry.register_schema(schema)
        
        # Валидные данные
        action_data = {
            "name": "John Doe",
            "age": 30
        }
        
        result = validator.validate_action("valid_action", action_data)
        
        assert result.is_valid is True
        assert result.errors == []
    
    def test_validate_action_missing_required_field(self):
        """Тест валидации действия с отсутствующим обязательным полем."""
        validator = ActionValidator()
        
        # Создаем схему с обязательным полем
        schema = ActionSchema(
            name="required_field_action",
            description="Действие с обязательным полем",
            parameters_schema={
                "name": {"type": "string", "description": "Имя пользователя"},
                "age": {"type": "number", "description": "Возраст пользователя"}
            },
            required_fields=["name"]
        )
        
        validator.schema_registry.register_schema(schema)
        
        # Данные без обязательного поля
        action_data = {
            "age": 30
        }
        
        result = validator.validate_action("required_field_action", action_data)
        
        assert result.is_valid is False
        assert len(result.errors) >= 1
        assert "name" in result.errors[0]  # Ошибка должна указывать на отсутствующее поле
    
    def test_validate_action_invalid_type(self):
        """Тест валидации действия с неправильным типом данных."""
        validator = ActionValidator()
        
        # Создаем схему с определенными типами
        schema = ActionSchema(
            name="typed_action",
            description="Действие с типизированными параметрами",
            parameters_schema={
                "count": {"type": "number", "description": "Число"},
                "name": {"type": "string", "description": "Имя"}
            },
            required_fields=["count"]
        )
        
        validator.schema_registry.register_schema(schema)
        
        # Данные с неправильным типом
        action_data = {
            "count": "not_a_number",  # строка вместо числа
            "name": "John"
        }
        
        result = validator.validate_action("typed_action", action_data)
        
        assert result.is_valid is False
        assert len(result.errors) >= 1
        # Ошибка должна указывать на неправильный тип
    
    def test_validate_action_schema_not_found(self):
        """Тест валидации действия для несуществующей схемы."""
        validator = ActionValidator()
        
        action_data = {
            "param": "value"
        }
        
        with pytest.raises(ValueError, match="Схема действия 'nonexistent_action' не найдена"):
            validator.validate_action("nonexistent_action", action_data)
    
    def test_validate_action_with_complex_schema(self):
        """Тест валидации действия со сложной схемой."""
        validator = ActionValidator()
        
        # Создаем сложную схему
        complex_schema = ActionSchema(
            name="complex_action",
            description="Сложное действие",
            parameters_schema={
                "user": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "email": {"type": "string", "format": "email"},
                        "preferences": {
                            "type": "object",
                            "properties": {
                                "newsletter": {"type": "boolean"},
                                "notifications": {"type": "boolean"}
                            }
                        }
                    },
                    "required": ["name", "email"]
                },
                "action": {"type": "string", "enum": ["create", "update", "delete"]}
            },
            required_fields=["user", "action"]
        )
        
        validator.schema_registry.register_schema(complex_schema)
        
        # Валидные данные
        valid_data = {
            "user": {
                "name": "John Doe",
                "email": "john@example.com",
                "preferences": {
                    "newsletter": True,
                    "notifications": False
                }
            },
            "action": "create"
        }
        
        result = validator.validate_action("complex_action", valid_data)
        
        assert result.is_valid is True
        assert result.errors == []
    
    def test_register_action_schema(self):
        """Тест метода register_action_schema."""
        validator = ActionValidator()
        
        schema = ActionSchema(
            name="register_test_action",
            description="Тест действия для регистрации",
            parameters_schema={"param": "value"},
            required_fields=["param"]
        )
        
        validator.register_action_schema(schema)
        
        # Проверяем, что схема зарегистрирована
        registered_schema = validator.schema_registry.get_schema("register_test_action")
        assert registered_schema == schema


def test_structured_action_error_creation():
    """Тест создания StructuredActionError."""
    error = StructuredActionError(message="Тестовая ошибка", error_type="validation")
    
    assert str(error) == "StructuredActionError[type=validation]: Тестовая ошибка"
    
    # Проверяем, что это исключение
    assert isinstance(error, Exception)


def test_structured_action_error_with_cause():
    """Тест StructuredActionError с причиной."""
    original_error = ValueError("Оригинальная ошибка")
    error = StructuredActionError(message="Обертка ошибки", error_type="wrapping", cause=original_error)
    
    assert "Обертка ошибки" in str(error)
    assert error.cause == original_error