#!/usr/bin/env python3
"""
Тестирование исправленной архитектуры ApplicationContext
"""

import asyncio
import sys
import os

# Добавляем путь к проекту
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.application.context.application_context import ApplicationContext
from core.config.app_config import AppConfig


async def test_with_mock_infrastructure():
    """Тестируем с фейковой инфраструктурой"""
    print("=== Тестирование с фейковой инфраструктурой ===")
    
    # Создаем минимальную конфигурацию
    app_config = AppConfig(
        config_id="test_config",
        prompt_versions={"test_capability": "v1.0.0"},
        input_contract_versions={"test_capability": "v1.0.0"},
        output_contract_versions={"test_capability": "v1.0.0"},
        service_configs={
            "prompt_service": {},
            "contract_service": {}
        }
    )
    
    # Создаем фейковый инфраструктурный контекст
    class FakeInfraContext:
        def __init__(self):
            self.id = "fake_infra_context"
            
        def get_prompt_storage(self):
            # Создаем фейковое хранилище
            class FakeStorage:
                async def exists(self, capability, version):
                    return True  # Предполагаем, что все версии существуют
                
                async def load(self, capability, version):
                    # Создаем фейковый объект промпта
                    class FakePrompt:
                        def __init__(self):
                            class Metadata:
                                class Status:
                                    value = "active"
                                status = Status()
                            self.metadata = Metadata()
                            self.content = f"Fake prompt for {capability} v{version}"
                    return FakePrompt()
            
            return FakeStorage()
            
        def get_contract_storage(self):
            # Создаем фейковое хранилище контрактов
            class FakeContractStorage:
                async def exists(self, capability, version, direction):
                    return True  # Предполагаем, что все версии существуют
                
                async def load(self, capability, version, direction):
                    # Создаем фейковый объект контракта
                    class FakeContract:
                        def __init__(self):
                            self.schema_data = {"type": "object", "properties": {}}
                    return FakeContract()
            
            return FakeContractStorage()
    
    fake_infra = FakeInfraContext()
    
    # Создаем прикладной контекст
    app_context = ApplicationContext(
        infrastructure_context=fake_infra,
        config=app_config,
        profile="prod"
    )
    
    print("Прикладной контекст создан")
    
    # Попробуем инициализировать
    try:
        success = await app_context.initialize()
        print(f"Инициализация успешна: {success}")
        
        if success:
            print(f"Количество компонентов: {len(app_context.components.all_components())}")
            from core.application.context.application_context import ComponentType
            services = app_context.components.all_of_type(ComponentType.SERVICE)
            print(f"Количество сервисов: {len(services)}")
        
    except Exception as e:
        print(f"Ошибка инициализации: {e}")
        import traceback
        traceback.print_exc()


async def test_resolve_component_class():
    """Тестируем метод разрешения классов компонентов"""
    print("\n=== Тестирование _resolve_component_class ===")
    
    # Создаем фейковый инфраструктурный контекст
    class FakeInfraContext:
        def __init__(self):
            self.id = "fake_infra_context"
            
        def get_prompt_storage(self):
            class FakeStorage:
                async def exists(self, capability, version):
                    return True
                async def load(self, capability, version):
                    class FakePrompt:
                        def __init__(self):
                            class Metadata:
                                class Status:
                                    value = "active"
                                status = Status()
                            self.metadata = Metadata()
                            self.content = f"Fake prompt for {capability} v{version}"
                    return FakePrompt()
            return FakeStorage()
            
        def get_contract_storage(self):
            class FakeContractStorage:
                async def exists(self, capability, version, direction):
                    return True
                async def load(self, capability, version, direction):
                    class FakeContract:
                        def __init__(self):
                            self.schema_data = {"type": "object", "properties": {}}
                    return FakeContract()
            return FakeContractStorage()
    
    fake_infra = FakeInfraContext()
    
    # Создаем минимальную конфигурацию
    app_config = AppConfig(config_id="test")
    
    app_context = ApplicationContext(
        infrastructure_context=fake_infra,
        config=app_config,
        profile="prod"
    )
    
    # Тестируем разрешение различных компонентов
    from core.application.context.application_context import ComponentType
    
    test_components = [
        ("prompt_service", ComponentType.SERVICE),
        ("contract_service", ComponentType.SERVICE),
        ("table_description_service", ComponentType.SERVICE),
    ]
    
    for name, comp_type in test_components:
        try:
            cls = app_context._resolve_component_class(comp_type, name)
            print(f"[OK] Класс для {name}: {cls}")
        except Exception as e:
            print(f"[ERROR] Ошибка при разрешении {name}: {e}")


async def main():
    """Основная функция тестирования"""
    print("Тестирование исправленной архитектуры ApplicationContext")
    
    await test_resolve_component_class()
    await test_with_mock_infrastructure()
    
    print("\n[SUCCESS] Тестирование завершено!")


if __name__ == "__main__":
    asyncio.run(main())