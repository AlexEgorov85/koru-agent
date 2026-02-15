#!/usr/bin/env python3
"""
Тестирование инициализации инструментов с подробной отладкой
"""

import asyncio
import sys
import os

# Добавляем путь к проекту
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.application.context.application_context import ApplicationContext
from core.config.app_config import AppConfig


async def detailed_debug():
    """Подробная отладка инициализации"""
    print("=== Подробная отладка инициализации ===")
    
    # Создаем конфигурацию с инструментами
    from core.config.component_config import ComponentConfig
    app_config = AppConfig(
        config_id="detailed_debug_config",
        prompt_versions={"test": "v1.0.0"},
        input_contract_versions={"test": "v1.0.0"},
        output_contract_versions={"test": "v1.0.0"},
        service_configs={
            "prompt_service": ComponentConfig(
                variant_id='test_prompt',
                prompt_versions={"test": "v1.0.0"},
                input_contract_versions={"test": "v1.0.0"},
                output_contract_versions={"test": "v1.0.0"},
                side_effects_enabled=True,
                detailed_metrics=False
            ),
            "contract_service": ComponentConfig(
                variant_id='test_contract',
                prompt_versions={"test": "v1.0.0"},
                input_contract_versions={"test": "v1.0.0"},
                output_contract_versions={"test": "v1.0.0"},
                side_effects_enabled=True,
                detailed_metrics=False
            )
        },
        tool_configs={
            "sql_tool": ComponentConfig(
                variant_id='test_sql_tool',
                prompt_versions={"test": "v1.0.0"},
                input_contract_versions={"test": "v1.0.0"},
                output_contract_versions={"test": "v1.0.0"},
                side_effects_enabled=True,
                detailed_metrics=False
            )
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
        
        def get_provider(self, name):
            if name == "default_db":
                class FakeDBProvider:
                    async def execute(self, query, params=None, max_rows=1000):
                        class Result:
                            def __init__(self):
                                self.rows = [["test_value"]]
                                self.columns = ["test_column"]
                                self.rowcount = 1
                        return Result()
                return FakeDBProvider()
            return None
    
    fake_infra = FakeInfraContext()
    
    # Создаем прикладной контекст
    app_context = ApplicationContext(
        infrastructure_context=fake_infra,
        config=app_config,
        profile="prod"
    )
    
    # Проверим, какие компоненты должны быть загружены
    print("\n1. Проверка конфигурации компонентов:")
    component_configs = app_context._resolve_component_configs()
    for comp_type, configs in component_configs.items():
        print(f"  {comp_type.value}: {len(configs)} компонентов")
        for name in configs.keys():
            print(f"    - {name}")
    
    # Попробуем создать компоненты по одному
    print("\n2. Пошаговое создание компонентов:")
    for comp_type, configs in component_configs.items():
        for name, config in configs.items():
            print(f"  Создание {comp_type.value}.{name}...")
            try:
                component = await app_context._create_component(comp_type, name, config)
                print(f"    [OK] Создан: {type(component)}")
                
                # Попробуем инициализировать
                if hasattr(component, 'initialize') and callable(component.initialize):
                    init_result = await component.initialize()
                    print(f"    [OK] Инициализация: {init_result}, _initialized: {getattr(component, '_initialized', 'N/A')}")
                else:
                    print(f"    [INFO] Нет метода initialize")
                    
            except Exception as e:
                print(f"    [ERROR] Ошибка: {e}")
                import traceback
                traceback.print_exc()
    
    print("\n3. Попробуем полную инициализацию:")
    try:
        success = await app_context.initialize()
        print(f"  Инициализация контекста: {success}")
        
        if success:
            from core.application.context.application_context import ComponentType
            services = app_context.components.all_of_type(ComponentType.SERVICE)
            tools = app_context.components.all_of_type(ComponentType.TOOL)
            
            print(f"  Загружено сервисов: {len(services)}")
            print(f"  Загружено инструментов: {len(tools)}")
            
            for tool in tools:
                print(f"    - {tool.name}: инициализирован={getattr(tool, '_initialized', False)}")
        
    except Exception as e:
        print(f"  [ERROR] Ошибка полной инициализации: {e}")
        import traceback
        traceback.print_exc()


async def main():
    """Основная функция"""
    await detailed_debug()
    print("\n[SUCCESS] Подробная отладка завершена!")


if __name__ == "__main__":
    asyncio.run(main())