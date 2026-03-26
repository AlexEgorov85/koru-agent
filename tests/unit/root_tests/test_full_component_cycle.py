"""
Тест полного цикла работы компонентов с автоматической инициализацией.
"""
import asyncio
import sys
import os

# Добавляем корневую директорию проекта в путь Python
sys.path.insert(0, os.path.abspath('.'))

async def test_full_component_cycle():
    """Тест полного цикла работы компонентов."""
    
    try:
        from core.config.app_config import AppConfig
        from core.application_context.application_context import ApplicationContext
        
        
        # Загружаем конфигурацию из реестра
        app_config = AppConfig.from_discovery(profile="prod", data_dir="data")
        
        # Создаем и инициализируем прикладной контекст напрямую из реестра
        # (это более простой способ для тестирования)
        from core.infrastructure_context.infrastructure_context import InfrastructureContext
        from core.config.models import SystemConfig
        import tempfile
        import os
        
        # Создаем временную конфигурацию для тестирования
        class MockSystemConfig:
            def __init__(self):
                self.data_dir = "data"  # используем существующую директорию
                self.llm_providers = {}
                self.db_providers = {}
        
        # Создаем инфраструктурный контекст с минимальной конфигурацией
        infra_config = MockSystemConfig()
        infra_context = InfrastructureContext(config=infra_config)
        await infra_context.initialize()
        
        # Создаем прикладной контекст
        app_context = ApplicationContext(
            infrastructure_context=infra_context,
            config=app_config,
            profile="prod"
        )
        
        # Инициализируем прикладной контекст (все компоненты будут созданы и инициализированы)
        await app_context.initialize()
        
        # Проверяем, что компоненты инициализированы
        
        # Проверяем сервисы
        prompt_service = app_context.get_service("prompt_service")
        contract_service = app_context.get_service("contract_service")
        
        
        # Проверяем навыки
        planning_skill = app_context.get_skill("planning")
        book_library_skill = app_context.get_skill("book_library")
        
        
        # Проверяем инструменты
        sql_tool = app_context.get_tool("sql_tool")
        file_tool = app_context.get_tool("file_tool")
        
        
        # Проверяем, что навыки имеют свои кэши
        if planning_skill and planning_skill._initialized:
        
        if book_library_skill and book_library_skill._initialized:
        
        # Проверяем, что инструменты не имеют промптов (если это так задумано)
        if sql_tool and sql_tool._initialized:
        
        # Проверяем, что компоненты могут предоставить свои ресурсы
        
        if book_library_skill and book_library_skill._initialized:
            try:
                prompt = book_library_skill.get_prompt("book_library.search_books")
            except Exception as e:
        
        if planning_skill and planning_skill._initialized:
            try:
                prompt = planning_skill.get_prompt("planning.create_plan")
            except Exception as e:
        
        
        return True
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(test_full_component_cycle())
    if success:
    else:
        sys.exit(1)