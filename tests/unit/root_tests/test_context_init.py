"""
Тест инициализации контекста для проверки исправления ошибки.
"""
import asyncio
import sys
import os

# Добавляем корневую директорию проекта в путь Python
sys.path.insert(0, os.path.abspath('.'))

async def test_context_initialization():
    """Тест инициализации контекста."""
    print("=== ТЕСТ ИНИЦИАЛИЗАЦИИ КОНТЕКСТА ===")
    
    try:
        from core.config.app_config import AppConfig
        from core.application.context.application_context import ApplicationContext
        
        print("[OK] Импорты выполнены успешно")
        
        # Загружаем конфигурацию из реестра
        app_config = AppConfig.from_discovery(profile="prod", data_dir="data")
        print("[OK] AppConfig успешно загружен из реестра")
        
        # Создаем инфраструктурный контекст с минимальной конфигурацией
        from core.infrastructure.context.infrastructure_context import InfrastructureContext
        from core.config.models import SystemConfig
        
        # Создаем временную конфигурацию для тестирования
        class MockSystemConfig:
            def __init__(self):
                self.data_dir = "data"  # используем существующую директорию
                self.llm_providers = {}
                self.db_providers = {}
        
        infra_config = MockSystemConfig()
        infra_context = InfrastructureContext(config=infra_config)
        await infra_context.initialize()
        print("[OK] Инфраструктурный контекст создан и инициализирован")
        
        # Создаем и инициализируем прикладной контекст
        app_context = ApplicationContext(
            infrastructure_context=infra_context,
            config=app_config,
            profile="prod"
        )
        print("[OK] ApplicationContext создан")
        
        # Инициализируем прикладной контекст (все компоненты будут созданы и инициализированы)
        success = await app_context.initialize()
        print(f"[OK] ApplicationContext инициализирован: {success}")
        
        if success:
            print("\n[SUCCESS] ИНИЦИАЛИЗАЦИЯ ПРОШЛА УСПЕШНО!")
            
            # Проверим, что компоненты созданы
            prompt_service = app_context.get_service("prompt_service")
            print(f"Prompt Service: {prompt_service is not None}")
            
            book_skill = app_context.get_skill("book_library")
            print(f"Book Library Skill: {book_skill is not None}")
            
            sql_tool = app_context.get_tool("sql_tool")
            print(f"SQL Tool: {sql_tool is not None}")
            
            return True
        else:
            print("\n[ERROR] ИНИЦИАЛИЗАЦИЯ НЕ УДАЛАСЬ!")
            return False
        
    except Exception as e:
        print(f"\n[ERROR] ОШИБКА ТЕСТИРОВАНИЯ: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(test_context_initialization())
    if success:
        print("\n[SUCCESS] Тестирование завершено успешно!")
    else:
        print("\n[ERROR] Тестирование завершилось с ошибками!")
        sys.exit(1)