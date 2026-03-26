"""
Юнит-тесты для ComponentRegistry.

ЗАПУСК:
```bash
pytest tests/unit/registry/test_component_registry.py -v
```
"""
import pytest
from core.services.registry.component_registry import ComponentRegistry
from core.models.enums.common_enums import ComponentType


class MockComponent:
    """Mock компонент для тестов."""
    
    def __init__(self, name: str):
        self.name = name
    
    def __repr__(self):
        return f"MockComponent({self.name})"


class TestComponentRegistry:
    """Тесты ComponentRegistry."""
    
    @pytest.fixture
    def registry(self):
        """Создать пустой реестр."""
        return ComponentRegistry()
    
    def test_register_and_get(self, registry):
        """Тест: регистрация и получение компонента."""
        component = MockComponent("test_service")
        
        registry.register(ComponentType.SERVICE, "test", component)
        result = registry.get(ComponentType.SERVICE, "test")
        
        assert result is component
        assert result.name == "test_service"
    
    def test_get_nonexistent(self, registry):
        """Тест: получение несуществующего компонента."""
        result = registry.get(ComponentType.SERVICE, "nonexistent")
        
        assert result is None
    
    def test_register_duplicate_raises_error(self, registry):
        """Тест: повторная регистрация вызывает ошибку."""
        component = MockComponent("test")
        
        registry.register(ComponentType.SERVICE, "test", component)
        
        with pytest.raises(ValueError, match="уже зарегистрирован"):
            registry.register(ComponentType.SERVICE, "test", component)
    
    def test_all_of_type(self, registry):
        """Тест: получение всех компонентов типа."""
        registry.register(ComponentType.SERVICE, "service1", MockComponent("s1"))
        registry.register(ComponentType.SERVICE, "service2", MockComponent("s2"))
        registry.register(ComponentType.SKILL, "skill1", MockComponent("sk1"))
        
        services = registry.all_of_type(ComponentType.SERVICE)
        
        assert len(services) == 2
        assert all(isinstance(c, MockComponent) for c in services)
    
    def test_all_components(self, registry):
        """Тест: получение всех компонентов."""
        registry.register(ComponentType.SERVICE, "s1", MockComponent("s1"))
        registry.register(ComponentType.SKILL, "sk1", MockComponent("sk1"))
        registry.register(ComponentType.TOOL, "t1", MockComponent("t1"))
        
        all_components = registry.all_components()
        
        assert len(all_components) == 3
    
    def test_clear(self, registry):
        """Тест: очистка реестра."""
        registry.register(ComponentType.SERVICE, "s1", MockComponent("s1"))
        registry.register(ComponentType.SKILL, "sk1", MockComponent("sk1"))
        
        registry.clear()
        
        assert registry.count() == 0
        assert registry.get(ComponentType.SERVICE, "s1") is None
    
    def test_count_all(self, registry):
        """Тест: подсчёт всех компонентов."""
        registry.register(ComponentType.SERVICE, "s1", MockComponent("s1"))
        registry.register(ComponentType.SERVICE, "s2", MockComponent("s2"))
        registry.register(ComponentType.SKILL, "sk1", MockComponent("sk1"))
        
        total = registry.count()
        
        assert total == 3
    
    def test_count_by_type(self, registry):
        """Тест: подсчёт компонентов по типу."""
        registry.register(ComponentType.SERVICE, "s1", MockComponent("s1"))
        registry.register(ComponentType.SERVICE, "s2", MockComponent("s2"))
        registry.register(ComponentType.SKILL, "sk1", MockComponent("sk1"))
        
        service_count = registry.count(ComponentType.SERVICE)
        skill_count = registry.count(ComponentType.SKILL)
        tool_count = registry.count(ComponentType.TOOL)
        
        assert service_count == 2
        assert skill_count == 1
        assert tool_count == 0
    
    def test_exists(self, registry):
        """Тест: проверка наличия компонента."""
        registry.register(ComponentType.SERVICE, "s1", MockComponent("s1"))
        
        assert registry.exists(ComponentType.SERVICE, "s1") is True
        assert registry.exists(ComponentType.SERVICE, "nonexistent") is False
        assert registry.exists(ComponentType.SKILL, "s1") is False
    
    def test_repr(self, registry):
        """Тест: строковое представление."""
        registry.register(ComponentType.SERVICE, "s1", MockComponent("s1"))
        registry.register(ComponentType.SKILL, "sk1", MockComponent("sk1"))
        
        repr_str = repr(registry)
        
        assert "ComponentRegistry" in repr_str
        assert "service" in repr_str.lower() or "SERVICE" in repr_str
        assert "skill" in repr_str.lower() or "SKILL" in repr_str
    
    def test_register_different_types(self, registry):
        """Тест: регистрация компонентов разных типов."""
        service = MockComponent("service")
        skill = MockComponent("skill")
        tool = MockComponent("tool")
        
        registry.register(ComponentType.SERVICE, "svc", service)
        registry.register(ComponentType.SKILL, "skl", skill)
        registry.register(ComponentType.TOOL, "tl", tool)
        
        assert registry.get(ComponentType.SERVICE, "svc") is service
        assert registry.get(ComponentType.SKILL, "skl") is skill
        assert registry.get(ComponentType.TOOL, "tl") is tool
    
    def test_empty_registry_operations(self, registry):
        """Тест: операции с пустым реестром."""
        assert registry.count() == 0
        assert registry.all_components() == []
        assert registry.all_of_type(ComponentType.SERVICE) == []
        assert registry.get(ComponentType.SERVICE, "anything") is None
        assert registry.exists(ComponentType.SERVICE, "anything") is False
