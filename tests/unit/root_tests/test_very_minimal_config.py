"""
Тест с очень минимальной конфигурацией для проверки инициализации компонентов.
"""
import asyncio
import sys
import os

# Добавляем корневую директорию проекта в путь Python
sys.path.insert(0, os.path.abspath('.'))

async def test_very_minimal_config():
    """Тест с очень минимальной конфигурацией."""
    
    try:
        from core.config.app_config import AppConfig
        from core.application_context.application_context import ApplicationContext
        
        
        # Загружаем конфигурацию из очень минимального реестра
        app_config = AppConfig.from_discovery(profile="prod", data_dir="data")
        
        # Создаем инфраструктурный контекст с минимальной конфигурацией
        from core.infrastructure_context.infrastructure_context import InfrastructureContext
        
        # Создаем временную конфигурацию для тестирования
        class MockSystemConfig:
            def __init__(self):
                self.data_dir = "data"  # используем существующую директорию
                self.llm_providers = {}
                self.db_providers = {}
        
        infra_config = MockSystemConfig()
        infra_context = InfrastructureContext(config=infra_config)
        await infra_context.initialize()
        
        # Создаем и инициализируем прикладной контекст
        app_context = ApplicationContext(
            infrastructure_context=infra_context,
            config=app_config,
            profile="prod"
        )
        
        # Инициализируем прикладной контекст (все компоненты будут созданы и инициализированы)
        success = await app_context.initialize()
        
        # Проверим состояние компонентов
        prompt_service = app_context.get_service("prompt_service")
        contract_service = app_context.get_service("contract_service")
        
        
        book_skill = app_context.get_skill("book_library")
        planning_skill = app_context.get_skill("planning")
        
        if book_skill:
        
        if planning_skill:
        
        sql_tool = app_context.get_tool("sql_tool")
        file_tool = app_context.get_tool("file_tool")
        
        if sql_tool:
        
        if file_tool:
        
        # Проверим, что все компоненты инициализированы (теперь, когда нет требований к промптам)
        all_initialized = all([
            prompt_service and getattr(prompt_service, '_initialized', False),
            contract_service and getattr(contract_service, '_initialized', False),
            book_skill and getattr(book_skill, '_initialized', False),
            planning_skill and getattr(planning_skill, '_initialized', False),
            sql_tool and getattr(sql_tool, '_initialized', False),
            file_tool and getattr(file_tool, '_initialized', False)
        ])
        
        
        # Проверим, что кэши пусты (так как нет промптов для загрузки)
        if book_skill:
        
        if planning_skill:
        
        if sql_tool:
        
        if file_tool:
        
        
        return True
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(test_very_minimal_config())
    if success:
    else:
        sys.exit(1)