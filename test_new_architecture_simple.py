#!/usr/bin/env python3
"""
Простое тестирование новой архитектуры ApplicationContext с единым реестром компонентов.
"""

import asyncio
import sys
import os

# Добавляем путь к проекту
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.application.context.application_context import ApplicationContext, ComponentType, ComponentRegistry
from core.config.app_config import AppConfig


def test_component_registry():
    """Тестируем ComponentRegistry"""
    print("=== Тестирование ComponentRegistry ===")
    
    registry = ComponentRegistry()
    
    # Создаем фейковый компонент для тестирования
    class FakeComponent:
        def __init__(self, name):
            self.name = name
    
    # Регистрируем компонент
    fake_service = FakeComponent("test_service")
    registry.register(ComponentType.SERVICE, "test_service", fake_service)
    
    # Проверяем, что компонент зарегистрирован
    retrieved = registry.get(ComponentType.SERVICE, "test_service")
    assert retrieved is not None, "Компонент должен быть найден"
    assert retrieved.name == "test_service", "Имя компонента должно совпадать"
    
    # Проверяем получение всех компонентов одного типа
    services = registry.all_of_type(ComponentType.SERVICE)
    assert len(services) == 1, "Должен быть один сервис"
    assert services[0].name == "test_service", "Имя сервиса должно совпадать"
    
    # Проверяем получение всех компонентов
    all_components = registry.all_components()
    assert len(all_components) == 1, "Должен быть один компонент"
    
    print("ComponentRegistry работает корректно")
    print("=== Тестирование ComponentRegistry завершено ===")


async def test_application_context_structure():
    """Тестируем структуру ApplicationContext"""
    print("\n=== Тестирование структуры ApplicationContext ===")
    
    # Создаем минимальную конфигурацию для тестирования
    app_config = AppConfig(
        config_id="test_config",
        prompt_versions={"test_cap": "v1.0.0"},
        input_contract_versions={"test_cap": "v1.0.0"},
        output_contract_versions={"test_cap": "v1.0.0"}
    )
    
    # Создаем фейковый инфраструктурный контекст
    class FakeInfraContext:
        def __init__(self):
            self.id = "fake_infra_context"
            
        def get_prompt_storage(self):
            return None
            
        def get_contract_storage(self):
            return None
    
    fake_infra = FakeInfraContext()
    
    # Создаем прикладной контекст
    app_context = ApplicationContext(
        infrastructure_context=fake_infra,
        config=app_config,
        profile="sandbox"
    )
    
    # Проверяем, что у контекста есть компонент реестр
    assert hasattr(app_context, 'components'), "ApplicationContext должен иметь атрибут components"
    assert isinstance(app_context.components, ComponentRegistry), "components должен быть экземпляром ComponentRegistry"
    
    # Проверяем методы доступа к компонентам
    assert hasattr(app_context, 'get_service'), "Должен быть метод get_service"
    assert hasattr(app_context, 'get_skill'), "Должен быть метод get_skill"
    assert hasattr(app_context, 'get_tool'), "Должен быть метод get_tool"
    assert hasattr(app_context, 'get_strategy'), "Должен быть метод get_strategy"
    
    print("Структура ApplicationContext корректна")
    print("=== Тестирование структуры ApplicationContext завершено ===")


def test_component_type_enum():
    """Тестируем ComponentType enum"""
    print("\n=== Тестирование ComponentType enum ===")
    
    from core.application.context.application_context import ComponentType
    
    # Проверяем, что все типы компонентов определены
    assert hasattr(ComponentType, 'SERVICE'), "Должен быть тип SERVICE"
    assert hasattr(ComponentType, 'SKILL'), "Должен быть тип SKILL"
    assert hasattr(ComponentType, 'TOOL'), "Должен быть тип TOOL"
    assert hasattr(ComponentType, 'STRATEGY'), "Должен быть тип STRATEGY"
    
    # Проверяем значения
    assert ComponentType.SERVICE.value == "service"
    assert ComponentType.SKILL.value == "skill"
    assert ComponentType.TOOL.value == "tool"
    assert ComponentType.STRATEGY.value == "strategy"
    
    print("ComponentType enum корректен")
    print("=== Тестирование ComponentType enum завершено ===")


async def main():
    """Основная функция тестирования"""
    print("Тестирование новой архитектуры ApplicationContext")
    
    test_component_type_enum()
    test_component_registry()
    await test_application_context_structure()
    
    print("\n[SUCCESS] Все тесты пройдены успешно!")
    print("Новая архитектура ApplicationContext с единым реестром компонентов работает корректно.")


if __name__ == "__main__":
    asyncio.run(main())