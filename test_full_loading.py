#!/usr/bin/env python3
"""
Тестирование полной загрузки с правильной конфигурацией
"""

import asyncio
import sys
import os

# Добавляем путь к проекту
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.application.context.application_context import ApplicationContext
from core.config.app_config import AppConfig


async def test_full_loading():
    """Тестируем полную загрузку с правильной конфигурацией"""
    print("=== Тестирование полной загрузки с правильной конфигурацией ===")
    
    # Создаем конфигурацию со всеми необходимыми компонентами
    from core.config.component_config import ComponentConfig
    app_config = AppConfig(
        config_id="full_test_config",
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
            ),
            "file_tool": ComponentConfig(
                variant_id='test_file_tool',
                prompt_versions={"test": "v1.0.0"},
                input_contract_versions={"test": "v1.0.0"},
                output_contract_versions={"test": "v1.0.0"},
                side_effects_enabled=True,
                detailed_metrics=False
            )
        }
    )
    
    print(f"Конфигурация создана:")
    print(f"- Сервисов: {len(app_config.service_configs)}")
    print(f"- Инструментов: {len(app_config.tool_configs)}")
    
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
    
    print("\nПопробуем инициализировать...")
    
    # Попробуем инициализировать
    try:
        success = await app_context.initialize()
        print(f"Инициализация успешна: {success}")
        
        if success:
            from core.application.context.application_context import ComponentType
            services = app_context.components.all_of_type(ComponentType.SERVICE)
            tools = app_context.components.all_of_type(ComponentType.TOOL)
            skills = app_context.components.all_of_type(ComponentType.SKILL)
            strategies = app_context.components.all_of_type(ComponentType.STRATEGY)
            
            print(f"\nКоличество компонентов после инициализации:")
            print(f"- Сервисов: {len(services)}")
            print(f"- Инструментов: {len(tools)}")
            print(f"- Навыков: {len(skills)}")
            print(f"- Стратегий: {len(strategies)}")
            
            if services:
                print(f"\nСервисы:")
                for service in services:
                    print(f"  - {service.name} (инициализирован: {getattr(service, '_initialized', False)})")
            
            if tools:
                print(f"\nИнструменты:")
                for tool in tools:
                    print(f"  - {tool.name} (инициализирован: {getattr(tool, '_initialized', False)})")
        
    except Exception as e:
        print(f"Ошибка инициализации: {e}")
        import traceback
        traceback.print_exc()


async def main():
    """Основная функция тестирования"""
    print("Тестирование полной загрузки с правильной конфигурацией")
    
    await test_full_loading()
    
    print("\n[SUCCESS] Тестирование завершено!")


if __name__ == "__main__":
    asyncio.run(main())