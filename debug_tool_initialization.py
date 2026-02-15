#!/usr/bin/env python3
"""
Диагностика проблемы с инициализацией инструментов
"""

import asyncio
import sys
import os

# Добавляем путь к проекту
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.application.context.application_context import ApplicationContext
from core.config.app_config import AppConfig


async def debug_tool_initialization():
    """Диагностика инициализации инструментов"""
    print("=== Диагностика инициализации инструментов ===")
    
    # Создаем конфигурацию с минимальными требованиями
    from core.config.component_config import ComponentConfig
    app_config = AppConfig(
        config_id="debug_config",
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
    
    print(f"Конфигурация создана с {len(app_config.tool_configs)} инструментом")
    
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
    
    # Попробуем создать инструмент вручную для диагностики
    print("\nПопробуем создать инструмент вручную...")
    
    try:
        from core.application.tools.sql_tool import SQLTool
        from core.application.context.application_context import ComponentType
        
        # Создаем конфигурацию для инструмента
        tool_config = app_config.tool_configs["sql_tool"]
        
        # Создаем инструмент напрямую
        sql_tool = SQLTool(
            name="sql_tool",
            application_context=app_context,
            component_config=tool_config
        )
        
        print(f"Инструмент создан: {sql_tool.name}")
        print(f"Тип инструмента: {type(sql_tool)}")
        
        # Попробуем инициализировать
        init_result = await sql_tool.initialize()
        print(f"Результат инициализации инструмента: {init_result}")
        print(f"Флаг инициализации: {getattr(sql_tool, '_initialized', 'не найден')}")
        
        # Проверим, есть ли кэши
        print(f"Кэш промптов: {hasattr(sql_tool, '_cached_prompts')}")
        print(f"Кэш входных контрактов: {hasattr(sql_tool, '_cached_input_contracts')}")
        print(f"Кэш выходных контрактов: {hasattr(sql_tool, '_cached_output_contracts')}")
        
    except Exception as e:
        print(f"Ошибка при ручном создании инструмента: {e}")
        import traceback
        traceback.print_exc()
    
    print("\nПопробуем полную инициализацию контекста...")
    
    # Попробуем инициализировать контекст
    try:
        success = await app_context.initialize()
        print(f"Инициализация контекста успешна: {success}")
        
        if success:
            from core.application.context.application_context import ComponentType
            tools = app_context.components.all_of_type(ComponentType.TOOL)
            print(f"Количество загруженных инструментов: {len(tools)}")
            
            for tool in tools:
                print(f"- {tool.name}: инициализирован={getattr(tool, '_initialized', False)}")
        
    except Exception as e:
        print(f"Ошибка инициализации контекста: {e}")
        import traceback
        traceback.print_exc()


async def main():
    """Основная функция диагностики"""
    print("Диагностика проблемы с инициализацией инструментов")
    
    await debug_tool_initialization()
    
    print("\n[SUCCESS] Диагностика завершена!")


if __name__ == "__main__":
    asyncio.run(main())