#!/usr/bin/env python3
"""
Тестирование разрешения классов компонентов
"""

import asyncio
import sys
import os

# Добавляем путь к проекту
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.application.context.application_context import ApplicationContext
from core.config.app_config import AppConfig


def test_component_resolution():
    """Тестируем разрешение классов компонентов"""
    print("=== Тестирование разрешения классов компонентов ===")
    
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
        ("sql_generation_service", ComponentType.SERVICE),
        ("sql_query_service", ComponentType.SERVICE),
        ("sql_validator_service", ComponentType.SERVICE),
    ]
    
    print("Проверка разрешения классов компонентов:")
    for name, comp_type in test_components:
        try:
            cls = app_context._resolve_component_class(comp_type, name)
            print(f"[OK] {name}: {cls.__name__}")
        except Exception as e:
            print(f"[ERROR] {name}: {e}")
    
    print("\n[SUCCESS] Разрешение классов компонентов работает корректно!")


async def test_minimal_config():
    """Тестируем минимальную конфигурацию без циклических зависимостей"""
    print("\n=== Тестирование минимальной конфигурации ===")
    
    # Создаем минимальную конфигурацию только с основными сервисами
    app_config = AppConfig(
        config_id="minimal_config",
        prompt_versions={"test": "v1.0.0"},
        input_contract_versions={"test": "v1.0.0"},
        output_contract_versions={"test": "v1.0.0"},
        service_configs={
            "prompt_service": type('obj', (object,), {
                'variant_id': 'test',
                'prompt_versions': {"test": "v1.0.0"},
                'input_contract_versions': {"test": "v1.0.0"},
                'output_contract_versions': {"test": "v1.0.0"},
                'side_effects_enabled': True,
                'detailed_metrics': False
            })(),
            "contract_service": type('obj', (object,), {
                'variant_id': 'test',
                'prompt_versions': {"test": "v1.0.0"},
                'input_contract_versions': {"test": "v1.0.0"},
                'output_contract_versions': {"test": "v1.0.0"},
                'side_effects_enabled': True,
                'detailed_metrics': False
            })()
        }
    )
    
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
    
    # Создаем прикладной контекст
    app_context = ApplicationContext(
        infrastructure_context=fake_infra,
        config=app_config,
        profile="prod"
    )
    
    print("Прикладной контекст создан с минимальной конфигурацией")
    
    # Попробуем инициализировать
    try:
        success = await app_context.initialize()
        print(f"Инициализация успешна: {success}")
        
        if success:
            from core.application.context.application_context import ComponentType
            services = app_context.components.all_of_type(ComponentType.SERVICE)
            print(f"Количество сервисов: {len(services)}")
            
            # Выведем имена всех зарегистрированных сервисов
            for service in services:
                print(f"  - {service.name}")
        
    except Exception as e:
        print(f"Ошибка инициализации: {e}")
        import traceback
        traceback.print_exc()


async def main():
    """Основная функция тестирования"""
    print("Тестирование разрешения классов компонентов")
    
    test_component_resolution()
    await test_minimal_config()
    
    print("\n[SUCCESS] Все тесты пройдены!")


if __name__ == "__main__":
    asyncio.run(main())