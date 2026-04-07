"""
Юнит-тесты для ContextValidator.

ЗАПУСК:
```bash
pytest tests/unit/validation/test_context_validator.py -v
```
"""
import pytest
from core.components.services.validation.context_validator import (
    ContextValidator,
    ValidationResult,
)
from core.components.services.registry.component_registry import ComponentRegistry
from core.models.enums.common_enums import ComponentType
from core.agent.components.lifecycle import LifecycleMixin, ComponentState


class MockComponent(LifecycleMixin):
    """Mock компонент с состоянием для тестов."""
    
    def __init__(self, name: str, state: ComponentState = ComponentState.READY):
        super().__init__(name)
        # Устанавливаем состояние напрямую для тестов
        self._state = state


class TestValidationResult:
    """Тесты ValidationResult."""
    
    def test_is_valid_when_no_errors(self):
        """Тест: is_valid=True когда нет ошибок."""
        result = ValidationResult()
        
        assert result.is_valid is True
        assert result.has_warnings is False
    
    def test_is_valid_when_has_errors(self):
        """Тест: is_valid=False когда есть ошибки."""
        result = ValidationResult(errors=["Error 1"])
        
        assert result.is_valid is False
    
    def test_add_error(self):
        """Тест: добавление ошибки."""
        result = ValidationResult()
        result.add_error("Test error")
        
        assert len(result.errors) == 1
        assert result.errors[0] == "Test error"
        assert result.is_valid is False
    
    def test_add_warning(self):
        """Тест: добавление предупреждения."""
        result = ValidationResult()
        result.add_warning("Test warning")
        
        assert len(result.warnings) == 1
        assert result.warnings[0] == "Test warning"
        assert result.has_warnings is True
    
    def test_merge(self):
        """Тест: объединение результатов."""
        result1 = ValidationResult(errors=["Error 1"], warnings=["Warning 1"])
        result2 = ValidationResult(errors=["Error 2", "Error 3"], warnings=["Warning 2"])
        
        result1.merge(result2)
        
        assert len(result1.errors) == 3
        assert len(result1.warnings) == 2
    
    def test_repr(self):
        """Тест: строковое представление."""
        valid_result = ValidationResult()
        invalid_result = ValidationResult(errors=["Error"])
        
        assert "VALID" in repr(valid_result)
        assert "INVALID" in repr(invalid_result)


class TestContextValidator:
    """Тесты ContextValidator."""
    
    @pytest.fixture
    def registry(self):
        """Создать пустой реестр."""
        return ComponentRegistry()
    
    @pytest.fixture
    def validator(self, registry):
        """Создать валидатор."""
        return ContextValidator(registry)
    
    def test_validate_all_initialized_empty_registry(self, validator):
        """Тест: валидация пустого реестра."""
        result = validator.validate_all_initialized()
        
        assert result.is_valid is True
        assert len(result.errors) == 0
    
    def test_validate_all_initialized_with_ready_components(self, validator, registry):
        """Тест: все компоненты инициализированы."""
        registry.register(
            ComponentType.SERVICE,
            "service1",
            MockComponent("service1", ComponentState.READY)
        )
        registry.register(
            ComponentType.SKILL,
            "skill1",
            MockComponent("skill1", ComponentState.READY)
        )
        
        result = validator.validate_all_initialized()
        
        assert result.is_valid is True
        assert len(result.errors) == 0
    
    def test_validate_all_initialized_with_not_ready_component(self, validator, registry):
        """Тест: компонент не инициализирован."""
        registry.register(
            ComponentType.SERVICE,
            "service1",
            MockComponent("service1", ComponentState.CREATED)
        )
        
        result = validator.validate_all_initialized()
        
        assert result.is_valid is False
        assert len(result.errors) == 1
        assert "не инициализирован" in result.errors[0]
    
    def test_validate_no_failed_components_all_ready(self, validator, registry):
        """Тест: нет упавших компонентов."""
        registry.register(
            ComponentType.SERVICE,
            "service1",
            MockComponent("service1", ComponentState.READY)
        )
        
        result = validator.validate_no_failed_components()
        
        assert result.is_valid is True
    
    def test_validate_no_failed_components_with_failed(self, validator, registry):
        """Тест: есть упавший компонент."""
        registry.register(
            ComponentType.SERVICE,
            "service1",
            MockComponent("service1", ComponentState.FAILED)
        )
        
        result = validator.validate_no_failed_components()
        
        assert result.is_valid is False
        assert len(result.errors) == 1
        assert "FAILED" in result.errors[0]
    
    def test_validate_dependencies_no_dependencies(self, validator, registry):
        """Тест: компоненты без зависимостей."""
        registry.register(
            ComponentType.SERVICE,
            "service1",
            MockComponent("service1")
        )
        
        result = validator.validate_dependencies()
        
        assert result.is_valid is True
    
    def test_validate_registry_not_empty(self, validator, registry):
        """Тест: реестр не пуст."""
        registry.register(
            ComponentType.SERVICE,
            "service1",
            MockComponent("service1")
        )
        
        result = validator.validate_registry_not_empty()
        
        assert result.is_valid is True
        assert len(result.warnings) == 0
    
    def test_validate_registry_empty(self, validator, registry):
        """Тест: реестр пуст."""
        result = validator.validate_registry_not_empty()
        
        assert result.is_valid is True  # Пустой реестр — это warning, не error
        assert len(result.warnings) == 1
    
    def test_validate_all(self, validator, registry):
        """Тест: полная валидация."""
        registry.register(
            ComponentType.SERVICE,
            "service1",
            MockComponent("service1", ComponentState.READY)
        )
        
        result = validator.validate_all()
        
        # Пустой реестр даёт warning, но валидация проходит
        assert len(result.errors) == 0
    
    def test_validate_all_with_errors(self, validator, registry):
        """Тест: полная валидация с ошибками."""
        registry.register(
            ComponentType.SERVICE,
            "service1",
            MockComponent("service1", ComponentState.FAILED)
        )
        
        result = validator.validate_all()
        
        assert len(result.errors) > 0
    
    def test_repr(self, validator, registry):
        """Тест: строковое представление."""
        registry.register(
            ComponentType.SERVICE,
            "service1",
            MockComponent("service1")
        )
        
        repr_str = repr(validator)
        
        assert "ContextValidator" in repr_str
        assert "1" in repr_str  # Количество компонентов


class TestValidationResultEdgeCases:
    """Тесты граничных случаев ValidationResult."""
    
    def test_merge_with_empty(self):
        """Тест: объединение с пустым результатом."""
        result = ValidationResult(errors=["Error 1"])
        empty = ValidationResult()
        
        result.merge(empty)
        
        assert len(result.errors) == 1
    
    def test_multiple_add_error(self):
        """Тест: множественные ошибки."""
        result = ValidationResult()
        result.add_error("Error 1")
        result.add_error("Error 2")
        result.add_error("Error 3")
        
        assert len(result.errors) == 3
        assert result.is_valid is False
    
    def test_has_warnings_property(self):
        """Тест: has_warnings property."""
        result = ValidationResult()
        
        assert result.has_warnings is False
        
        result.add_warning("Warning")
        
        assert result.has_warnings is True
