"""
Модульные тесты для ValidationService.

ЗАПУСК:
    pytest tests/unit/services/test_validation_service.py -v
"""
import pytest
from pydantic import BaseModel, Field

from core.services.validation_service import ValidationService, ValidationResult


# Тестовые схемы
class UserSchema(BaseModel):
    """Тестовая схема пользователя."""
    name: str = Field(..., min_length=1)
    age: int = Field(..., ge=0, le=150)
    email: str = Field(..., pattern=r'^[\w\.-]+@[\w\.-]+\.\w+$')


class ProductSchema(BaseModel):
    """Тестовая схема товара."""
    id: int
    title: str
    price: float = Field(..., ge=0)


class TestValidationService:
    """Тесты для ValidationService."""

    @pytest.fixture
    def service(self):
        """Создание сервиса."""
        return ValidationService()

    # ========================================================================
    # Тесты validate()
    # ========================================================================

    def test_validate_success(self, service):
        """Успешная валидация."""
        data = {"name": "John", "age": 30, "email": "john@example.com"}
        
        result = service.validate(UserSchema, data)
        
        assert result.is_valid is True
        assert result.validated_data is not None
        assert isinstance(result.validated_data, UserSchema)
        assert result.validated_data.name == "John"
        assert result.validated_data.age == 30
        assert result.error is None

    def test_validate_failure(self, service):
        """Валидация с ошибкой."""
        data = {"name": "", "age": -5, "email": "invalid"}
        
        result = service.validate(UserSchema, data)
        
        assert result.is_valid is False
        assert result.validated_data is None
        assert result.error is not None
        assert "error" in result.error.lower()

    def test_validate_missing_fields(self, service):
        """Валидация с отсутствующими полями."""
        data = {"name": "John"}  # Нет age и email
        
        result = service.validate(UserSchema, data)
        
        assert result.is_valid is False
        assert "error" in result.error.lower()

    def test_validate_extra_fields(self, service):
        """Валидация с лишними полями (Pydantic игнорирует)."""
        data = {
            "name": "John",
            "age": 30,
            "email": "john@example.com",
            "extra_field": "should be ignored"
        }
        
        result = service.validate(UserSchema, data)
        
        assert result.is_valid is True
        assert not hasattr(result.validated_data, 'extra_field')

    def test_validate_type_conversion(self, service):
        """Валидация с конвертацией типов."""
        data = {"name": "John", "age": "30", "email": "john@example.com"}  # age как строка
        
        result = service.validate(UserSchema, data)
        
        assert result.is_valid is True
        assert isinstance(result.validated_data.age, int)
        assert result.validated_data.age == 30

    # ========================================================================
    # Тесты is_valid()
    # ========================================================================

    def test_is_valid_true(self, service):
        """Быстрая проверка - валидно."""
        data = {"name": "John", "age": 30, "email": "john@example.com"}
        
        assert service.is_valid(UserSchema, data) is True

    def test_is_valid_false(self, service):
        """Быстрая проверка - не валидно."""
        data = {"name": "", "age": -5}
        
        assert service.is_valid(UserSchema, data) is False

    # ========================================================================
    # Тесты validate_dict()
    # ========================================================================

    def test_validate_dict_success(self, service):
        """Валидация словаря - успех."""
        data = {"key": "value", "number": 42}
        
        result = service.validate_dict(data)
        
        assert result.is_valid is True
        assert result.validated_data == data
        assert result.error is None

    def test_validate_dict_none(self, service):
        """Валидация None - ошибка."""
        result = service.validate_dict(None)
        
        assert result.is_valid is False
        assert "none" in result.error.lower()

    def test_validate_dict_not_dict(self, service):
        """Валидация не-dict - ошибка."""
        result = service.validate_dict("string")
        
        assert result.is_valid is False
        assert "dict" in result.error.lower()

    # ========================================================================
    # Тесты validate_batch()
    # ========================================================================

    def test_validate_batch_all_valid(self, service):
        """Пакетная валидация - все валидны."""
        items = [
            {"name": "John", "age": 30, "email": "john@example.com"},
            {"name": "Jane", "age": 25, "email": "jane@example.com"}
        ]
        
        results = service.validate_batch(UserSchema, items)
        
        assert len(results) == 2
        assert all(r.is_valid for r in results)
        assert results[0].validated_data.name == "John"
        assert results[1].validated_data.name == "Jane"

    def test_validate_batch_mixed(self, service):
        """Пакетная валидация - смешанные результаты."""
        items = [
            {"name": "John", "age": 30, "email": "john@example.com"},  # valid
            {"name": "", "age": -5},  # invalid
            {"name": "Jane", "age": 25, "email": "jane@example.com"}  # valid
        ]
        
        results = service.validate_batch(UserSchema, items)
        
        assert len(results) == 3
        assert results[0].is_valid is True
        assert results[1].is_valid is False
        assert results[2].is_valid is True
        
        # Фильтрация валидных
        valid_items = [r.validated_data for r in results if r.is_valid]
        assert len(valid_items) == 2

    # ========================================================================
    # Тесты ValidationResult
    # ========================================================================

    def test_validation_result_bool(self):
        """Тест __bool__ метода."""
        result_valid = ValidationResult(is_valid=True)
        result_invalid = ValidationResult(is_valid=False)
        
        assert bool(result_valid) is True
        assert bool(result_invalid) is False

    def test_validation_result_model_dump(self):
        """Тест сериализации."""
        result = ValidationResult(
            is_valid=True,
            validated_data=UserSchema(name="John", age=30, email="john@example.com"),
            error=None
        )
        
        dumped = result.model_dump()
        
        assert dumped["is_valid"] is True
        assert dumped["validated_data"]["name"] == "John"
        assert dumped["error"] is None

    # ========================================================================
    # Тесты с другими схемами
    # ========================================================================

    def test_validate_product_schema(self, service):
        """Валидация схемы товара."""
        data = {"id": 1, "title": "Widget", "price": 19.99}
        
        result = service.validate(ProductSchema, data)
        
        assert result.is_valid is True
        assert result.validated_data.title == "Widget"
        assert result.validated_data.price == 19.99

    def test_validate_negative_price(self, service):
        """Валидация с отрицательной ценой."""
        data = {"id": 1, "title": "Widget", "price": -10}
        
        result = service.validate(ProductSchema, data)
        
        assert result.is_valid is False
        assert result.error is not None
        assert "error" in result.error.lower()


# Интеграционные тесты вынесены в tests/integration/test_validation_integration.py
