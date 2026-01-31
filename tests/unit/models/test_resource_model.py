"""
Тесты для модели Resource (ResourceType, ResourceHealth).
"""
import pytest
from models.resource import ResourceType, ResourceHealth


def test_resource_type_enum_values():
    """Тест значений ResourceType enum."""
    assert ResourceType.LLM_PROVIDER.value == "llm_provider"
    assert ResourceType.DATABASE.value == "database"
    assert ResourceType.TOOL.value == "tool"
    assert ResourceType.SKILL.value == "skill"
    assert ResourceType.SERVICE.value == "service"
    assert ResourceType.CACHE.value == "cache"
    assert ResourceType.CONFIG.value == "config"
    
    # Проверяем, что можем получить все значения
    all_types = [resource_type.value for resource_type in ResourceType]
    expected_types = ["llm_provider", "database", "tool", "skill", "service", "cache", "config"]
    assert set(all_types) == set(expected_types)


def test_resource_health_enum_values():
    """Тест значений ResourceHealth enum."""
    assert ResourceHealth.HEALTHY.value == "healthy"
    assert ResourceHealth.DEGRADED.value == "degraded"
    assert ResourceHealth.UNHEALTHY.value == "unhealthy"
    assert ResourceHealth.INITIALIZING.value == "initializing"
    
    # Проверяем, что можем получить все значения
    all_health_states = [health.value for health in ResourceHealth]
    expected_health_states = ["healthy", "degraded", "unhealthy", "initializing"]
    assert set(all_health_states) == set(expected_health_states)