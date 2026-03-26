#!/usr/bin/env python3
"""
Тест для проверки исправления инициализации sql_tool
"""
import asyncio
import sys
import os

# Добавляем путь к проекту
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

async def test_sql_tool_initialization():
    """Тестируем инициализацию sql_tool после исправления"""
    
    try:
        # Импортируем необходимые модули
        from core.config.app_config import AppConfig
        from core.application_context.application_context import ApplicationContext
        from core.infrastructure_context.infrastructure_context import InfrastructureContext
        from core.config.models import SystemConfig, LLMProviderConfig, DBProviderConfig
        
        
        # Создаем минимальную системную конфигурацию
        system_config = SystemConfig(
            llm_providers={
                "default_llm": LLMProviderConfig(
                    provider_type="llama_cpp",
                    model_name="test-model",
                    parameters={"model_path": "test"},
                    enabled=True
                )
            },
            db_providers={
                "default_db": DBProviderConfig(
                    provider_type="sqlite",
                    parameters={"database_url": "sqlite:///test.db"},
                    enabled=True
                )
            }
        )
        
        # Создаем инфраструктурный контекст
        infra_context = InfrastructureContext(config=system_config)
        
        # Загружаем конфигурацию из реестра
        app_config = AppConfig.from_discovery(profile="prod", data_dir="data")
        
        # Проверяем конфигурацию sql_tool
        if 'sql_tool' in app_config.tool_configs:
            sql_tool_config = app_config.tool_configs['sql_tool']
        else:
            return False
        
        # Инициализируем инфраструктурный контекст
        await infra_context.initialize()

        # Создаем контекст приложения
        app_context = ApplicationContext(
            infrastructure_context=infra_context,
            config=app_config,
            profile="prod"
        )
        await app_context.initialize()
        
        # Получаем инструмент
        sql_tool = app_context.get_tool("sql_tool")
        if sql_tool is None:
            return False
            
        
        # Проверяем, что инструмент инициализирован
        if hasattr(sql_tool, '_initialized') and sql_tool._initialized:
        else:
            return False
            
        # Проверяем, что кэши пустые (что нормально для инструментов без промптов)
        cached_prompts = getattr(sql_tool, '_cached_prompts', {})
        cached_input_contracts = getattr(sql_tool, '_cached_input_contracts', {})
        cached_output_contracts = getattr(sql_tool, '_cached_output_contracts', {})
        
        if not cached_prompts and not cached_input_contracts and not cached_output_contracts:
        else:
        
        return True
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(test_sql_tool_initialization())
    if success:
        sys.exit(0)
    else:
        sys.exit(1)