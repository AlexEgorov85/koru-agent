#!/usr/bin/env python3
"""
Тестирование загрузки инструментов в ApplicationContext
"""

import asyncio
import sys
import os

# Добавляем путь к проекту
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.application.context.application_context import ApplicationContext
from core.config.app_config import AppConfig


async def test_tools_loading():
    """Тестируем загрузку инструментов"""
    print("=== Тестирование загрузки инструментов ===")
    
    # Создаем конфигурацию с инструментами
    app_config = AppConfig(
        config_id="tools_test_config",
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
        },
        tool_configs={
            "sql_tool": type('obj', (object,), {
                'variant_id': 'test_sql_tool',
                'prompt_versions': {"test": "v1.0.0"},
                'input_contract_versions': {"test": "v1.0.0"},
                'output_contract_versions': {"test": "v1.0.0"},
                'side_effects_enabled': True,
                'detailed_metrics': False
            })(),
            "file_tool": type('obj', (object,), {
                'variant_id': 'test_file_tool',
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
    
    print("Прикладной контекст создан с конфигурацией, содержащей инструменты")
    
    # Попробуем инициализировать
    try:
        success = await app_context.initialize()
        print(f"Инициализация успешна: {success}")
        
        if success:
            from core.application.context.application_context import ComponentType
            services = app_context.components.all_of_type(ComponentType.SERVICE)
            tools = app_context.components.all_of_type(ComponentType.TOOL)
            
            print(f"Количество сервисов: {len(services)}")
            print(f"Количество инструментов: {len(tools)}")
            
            # Выведем имена всех зарегистрированных сервисов
            print("Сервисы:")
            for service in services:
                print(f"  - {service.name}")
            
            # Выведем имена всех зарегистрированных инструментов
            print("Инструменты:")
            for tool in tools:
                print(f"  - {tool.name}")
        
    except Exception as e:
        print(f"Ошибка инициализации: {e}")
        import traceback
        traceback.print_exc()


async def test_tool_resolution():
    """Тестируем разрешение классов инструментов"""
    print("\n=== Тестирование разрешения классов инструментов ===")
    
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
    
    # Тестируем разрешение различных инструментов
    from core.application.context.application_context import ComponentType
    
    test_tools = [
        ("sql_tool", ComponentType.TOOL),
        ("file_tool", ComponentType.TOOL),
    ]
    
    print("Проверка разрешения классов инструментов:")
    for name, comp_type in test_tools:
        try:
            cls = app_context._resolve_component_class(comp_type, name)
            print(f"[OK] {name}: {cls.__name__}")
        except Exception as e:
            print(f"[INFO] {name}: {e} (ожидаемо, если инструмент не реализован)")


async def main():
    """Основная функция тестирования"""
    print("Тестирование загрузки инструментов в ApplicationContext")
    
    await test_tool_resolution()
    await test_tools_loading()
    
    print("\n[SUCCESS] Тестирование завершено!")


if __name__ == "__main__":
    asyncio.run(main())