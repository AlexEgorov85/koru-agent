"""
Юнит-тесты для ResourceRegistry.

Тестирует:
- Регистрацию ресурсов
- Получение ресурсов по имени
- Получение всех ресурсов
"""
import pytest
from core.infrastructure.context.resource_registry import ResourceRegistry
from core.models.resource import ResourceInfo, ResourceType


def test_resource_registry_initially_empty():
    """Проверка: реестр ресурсов изначально пуст"""
    registry = ResourceRegistry()
    
    assert len(registry.get_all_names()) == 0
    assert len(registry.get_all_resources()) == 0


def test_register_resource_adds_to_registry():
    """Проверка: регистрация ресурса добавляет его в реестр"""
    registry = ResourceRegistry()
    
    # Создаем тестовый ресурс
    mock_instance = object()
    resource_info = ResourceInfo(
        name="test_resource",
        resource_type=ResourceType.LLM_PROVIDER,
        instance=mock_instance
    )
    
    # Регистрируем ресурс
    registry.register_resource(resource_info)
    
    # Проверяем, что ресурс добавлен
    assert "test_resource" in registry.get_all_names()
    assert len(registry.get_all_names()) == 1
    assert len(registry.get_all_resources()) == 1


def test_get_existing_resource_returns_correct_instance():
    """Проверка: получение существующего ресурса возвращает правильный экземпляр"""
    registry = ResourceRegistry()
    
    # Создаем тестовый ресурс
    mock_instance = object()
    resource_info = ResourceInfo(
        name="test_resource",
        resource_type=ResourceType.LLM_PROVIDER,
        instance=mock_instance
    )
    
    # Регистрируем ресурс
    registry.register_resource(resource_info)
    
    # Получаем ресурс
    retrieved = registry.get_resource("test_resource")
    
    assert retrieved is resource_info


def test_get_nonexistent_resource_returns_none():
    """Проверка: получение несуществующего ресурса возвращает None"""
    registry = ResourceRegistry()
    
    # Пытаемся получить несуществующий ресурс
    retrieved = registry.get_resource("nonexistent_resource")
    
    assert retrieved is None


def test_register_multiple_resources():
    """Проверка: регистрация нескольких ресурсов работает корректно"""
    registry = ResourceRegistry()
    
    # Создаем несколько тестовых ресурсов
    resource1 = ResourceInfo(
        name="resource1",
        resource_type=ResourceType.LLM_PROVIDER,
        instance=object()
    )
    
    resource2 = ResourceInfo(
        name="resource2",
        resource_type=ResourceType.DATABASE,
        instance=object()
    )
    
    # Регистрируем оба ресурса
    registry.register_resource(resource1)
    registry.register_resource(resource2)
    
    # Проверяем, что оба ресурса добавлены
    all_names = registry.get_all_names()
    assert "resource1" in all_names
    assert "resource2" in all_names
    assert len(all_names) == 2
    
    all_resources = registry.get_all_resources()
    assert len(all_resources) == 2


def test_overwrite_resource_with_same_name():
    """Проверка: перезапись ресурса с тем же именем заменяет старый"""
    registry = ResourceRegistry()
    
    # Создаем два ресурса с одинаковым именем
    instance1 = object()
    instance2 = object()
    
    resource1 = ResourceInfo(
        name="same_name",
        resource_type=ResourceType.LLM_PROVIDER,
        instance=instance1
    )
    
    resource2 = ResourceInfo(
        name="same_name",
        resource_type=ResourceType.DATABASE,
        instance=instance2
    )
    
    # Регистрируем первый ресурс
    registry.register_resource(resource1)
    assert registry.get_resource("same_name").instance is instance1
    
    # Регистрируем второй ресурс с тем же именем
    registry.register_resource(resource2)
    assert registry.get_resource("same_name").instance is instance2
    assert len(registry.get_all_names()) == 1  # Только один ресурс остался


def test_get_all_resources_returns_correct_list():
    """Проверка: получение всех ресурсов возвращает правильный список"""
    registry = ResourceRegistry()
    
    # Создаем несколько ресурсов
    resource1 = ResourceInfo(
        name="resource1",
        resource_type=ResourceType.LLM_PROVIDER,
        instance=object()
    )
    
    resource2 = ResourceInfo(
        name="resource2",
        resource_type=ResourceType.DATABASE,
        instance=object()
    )
    
    # Регистрируем ресурсы
    registry.register_resource(resource1)
    registry.register_resource(resource2)
    
    # Получаем все ресурсы
    all_resources = registry.get_all_resources()
    
    assert len(all_resources) == 2
    assert resource1 in all_resources
    assert resource2 in all_resources


def test_get_all_names_returns_correct_list():
    """Проверка: получение всех имен возвращает правильный список"""
    registry = ResourceRegistry()
    
    # Создаем несколько ресурсов
    resource1 = ResourceInfo(
        name="resource1",
        resource_type=ResourceType.LLM_PROVIDER,
        instance=object()
    )
    
    resource2 = ResourceInfo(
        name="resource2",
        resource_type=ResourceType.DATABASE,
        instance=object()
    )
    
    # Регистрируем ресурсы
    registry.register_resource(resource1)
    registry.register_resource(resource2)
    
    # Получаем все имена
    all_names = registry.get_all_names()
    
    assert len(all_names) == 2
    assert "resource1" in all_names
    assert "resource2" in all_names